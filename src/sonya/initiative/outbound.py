"""Outbound initiative: Sonya writes first to Ivan.

Two entry points:
- `OutboundGate.send_via_tool(text)` — called by `chat.tell_ivan` tool in active sessions.
- `OutboundGate.maybe_send_from_thought(thought_text)` — scans idle-thought text for
  a `[SEND_TO_IVAN: ...]` marker and sends if gates allow. Cheap — no extra LLM call.

Gates (all must pass):
- `min_quiet_minutes` since last incoming or outgoing telegram message
- `max_per_day` not exceeded
- A non-empty target chat_id in config (`SONYA_PRIMARY_USER_TG_ID`)
- Telegram channel registered and running

All sends emit `outgoing.telegram_initiative` continuity events.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional

from sonya.channels.base import OutgoingMessage
from sonya.channels.registry import ChannelRegistry
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream


_INITIATIVE_MARKER_RE = re.compile(
    r"\[SEND_TO_IVAN:\s*(?P<body>.+?)\s*\]",
    re.DOTALL | re.IGNORECASE,
)


# Patterns that look like the model echoed our prompt placeholder instead of
# substituting real text. Examples that should be blocked:
#   '<твой текст>', '<text>', '<your message>', 'ТУТ_ТВОЁ_СООБЩЕНИЕ',
#   '<...>', '<message>'.
_PLACEHOLDER_RE = re.compile(
    r"^[\s\W]*"  # optional leading punctuation
    r"(?:<[^>]*>"            # any <...>
    r"|тут[_\s]*тв[оё]+[_\s]*\w*"  # ТУТ_ТВОЁ_*
    r"|your[\s_]*(?:text|message|reply)"
    r"|твой[\s_]*(?:текст|ответ|message|сообщ\w*)"
    r"|placeholder|sample text"
    r")[\s\W]*$",
    re.IGNORECASE,
)


def _is_placeholder_text(s: str) -> bool:
    """Return True if `s` looks like the model echoed a prompt placeholder."""
    if not s:
        return True
    return bool(_PLACEHOLDER_RE.match(s.strip()))


def _normalize_for_dedup(text: str) -> str:
    """Normalize text for fuzzy duplicate comparison.

    Drops case, punctuation, asterisk-actions. Truncates each word to its
    first 6 chars so Russian morphology variants ("продолжаю / продолжу /
    продолжаем") collapse to one stem. The repeating-prefix pattern
    ("Продолжаю разведку X / Продолжаю по X / Продолжаю задачу X") is the
    SIGNAL we want to catch, so we deliberately do NOT strip those prefixes.

    Also keeps URLs/identifiers (sweetcow, xmlrpc) intact since 6-char trunc
    leaves them recognisable.
    """
    if not text:
        return ""
    s = text.lower()
    # Strip stage directions like *хмурюсь*
    s = re.sub(r"\*[^*]+\*", " ", s)
    # Drop punctuation
    s = re.sub(r"[^\w\s]", " ", s)
    # Truncate each word to its 6-char stem so morphology variants collapse
    tokens = s.split()
    stemmed = []
    for tok in tokens:
        if len(tok) >= 4:
            stemmed.append(tok[:6])
        elif len(tok) >= 2:
            # Keep short content words (com, tor, http, php, css)
            stemmed.append(tok)
        # Drop 1-char "stop" tokens (с, в, и) — they're noise for fuzzy match
    return " ".join(stemmed)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OutboundGate:
    """Throttle + dispatch for initiative messages.

    Gate state lives in memory for now (resets on soft-restart). Daily counter is
    keyed on UTC date; quiet-window check reads the latest tg events from the
    continuity stream so it survives restart.
    """

    def __init__(
        self,
        *,
        registry: ChannelRegistry,
        stream: ContinuityStream,
        target_tg_chat_id: str,
        max_per_day: int = 5,
        min_quiet_minutes: int = 90,
        channel_name: str = "telegram",
        progress_updates_max_per_day: int = 50,
        substrate: object = None,
        tg_emergency_mode: bool = False,
        tg_emergency_threshold_hours: float = 24.0,
    ) -> None:
        self._registry = registry
        self._stream = stream
        self._target = target_tg_chat_id
        self._max_per_day = max_per_day
        self._min_quiet = min_quiet_minutes
        self._channel = channel_name
        self._max_progress_per_day = progress_updates_max_per_day
        # Optional substrate for env-status checks. When provided, initiative
        # blocks if Sonya herself recorded ivan_status='спит' / 'занят' / etc.
        self._substrate = substrate
        # Atrium Этап 1.5 — TG emergency-only mode. When enabled, dialog to TG
        # is suppressed while Atrium is alive (seen within threshold).
        self._tg_emergency_mode = tg_emergency_mode
        self._tg_emergency_threshold_hours = tg_emergency_threshold_hours

        self._date_key: str = ""
        self._sent_today: int = 0
        self._progress_today: int = 0

    # ---------- public ----------

    async def send_via_tool(
        self,
        text: str,
        *,
        reason: str = "tool",
        ignore_quiet: bool = True,
        channel: str = "dialog",
        emergency_override: bool = False,
        workspace_id: str = "",
    ) -> str:
        """Tool entry point. Returns a status string for the agent.

        `ignore_quiet`: skip the quiet-window gate (default True) — when Sonya
        explicitly calls chat.tell_ivan from an agent session she's already
        actively talking to him. Daily cap still applies.

        `channel` (v20 / Atrium Этап 0): which surface this message belongs to.
        Only `dialog` goes through the full gate (caps / dedup / escalating
        quiet) — other channels (worker_log / mind / body / voice) get
        rate-limit only and are dispatched directly into substrate as
        `outgoing.<channel>` events without being routed to TG.
        См. docs/atrium/CHANNELS.md §2.

        `emergency_override` (Этап 1.5): when TG is in emergency-only mode,
        a True value forces the TG dispatch even if Atrium is live (for
        identity-critical alarms / real crises).
        """
        text = (text or "").strip()
        if not text:
            return f"[ERROR] {channel}: empty message"
        if _is_placeholder_text(text):
            return f"[BLOCKED] {channel}: placeholder text leaked, no real content ({text[:60]!r})"
        # Non-dialog channels: skip dialog-specific gates entirely. Just
        # apply rate-limit (TBD: real ratelimit, для Этапа 0 без него) и
        # dispatch event прямо в substrate. TG bridge их сам отфильтрует.
        if channel != "dialog":
            return await self._dispatch_non_dialog(text, channel=channel, reason=reason)
        # Этап 1.5 — TG emergency-only: if Atrium is the live primary surface,
        # record the dialog for Atrium to render but skip the TG mirror.
        suppress, why = self._suppress_tg_dialog(emergency_override=emergency_override)
        if suppress:
            return await self._dispatch_dialog_atrium_only(text, reason=reason, workspace_id=workspace_id)
        # Dialog channel: full original gate logic.
        # Cross-session dedup: refuse near-duplicate of any outbound sent in
        # the last 6 hours. Catches the "Продолжаю разведку sweetcow..." spam
        # where worker repeats intent each tick instead of new content.
        dup_reason = self._check_recent_duplicate(text, lookback_hours=6)
        if dup_reason:
            self._stream.append(ContinuityEvent(
                kind="internal.initiative_blocked",
                payload={"reason": dup_reason, "preview": text[:200]},
            ))
            return f"[BLOCKED] {dup_reason}"
        ok, why = self._check_gates(ignore_quiet=ignore_quiet)
        if not ok:
            return f"[BLOCKED] initiative gate: {why}"
        return await self._dispatch(text, reason=reason, workspace_id=workspace_id)

    async def maybe_send_from_thought(self, thought_text: str) -> Optional[str]:
        """Scan an idle thought for the [SEND_TO_IVAN: ...] marker.

        Returns the dispatch status string if a send was attempted, else None.
        Quiet-window IS enforced here (initiative from idle is anti-spam).
        """
        if not thought_text:
            return None
        match = _INITIATIVE_MARKER_RE.search(thought_text)
        if match is None:
            return None
        body = match.group("body").strip()
        if not body:
            return None
        # Guard: model sometimes copies the prompt placeholder verbatim
        # ('<твой текст>', '<text>', etc) instead of substituting real text.
        # Reject — that's a leak, not a real message.
        if _is_placeholder_text(body):
            self._stream.append(ContinuityEvent(
                kind="internal.initiative_blocked",
                payload={"reason": "placeholder_text_leaked", "preview": body[:200]},
            ))
            return f"[BLOCKED] placeholder text leaked: {body[:80]!r}"
        # Cross-session dedup
        dup_reason = self._check_recent_duplicate(body, lookback_hours=6)
        if dup_reason:
            self._stream.append(ContinuityEvent(
                kind="internal.initiative_blocked",
                payload={"reason": dup_reason, "preview": body[:200]},
            ))
            return f"[BLOCKED] {dup_reason}"
        ok, why = self._check_gates(ignore_quiet=False)
        if not ok:
            self._stream.append(ContinuityEvent(
                kind="internal.initiative_blocked",
                payload={"reason": why, "preview": body[:200]},
            ))
            return f"[BLOCKED] {why}"
        return await self._dispatch(body, reason="idle_thought")

    # ---------- gates ----------

    def _atrium_is_live(self) -> bool:
        """True if Atrium was seen within the emergency threshold.

        Reads `atrium_last_seen` from environment_state (written by the admin
        heartbeat / WS feed). When live and emergency-mode is on, TG dialog is
        suppressed — Atrium is the primary surface.
        """
        if self._substrate is None:
            return False
        try:
            from sonya.state.environment import EnvironmentStore
            rec = EnvironmentStore(self._substrate).get("atrium_last_seen")
            if not rec or not rec.get("value"):
                return False
            seen = datetime.fromisoformat(rec["value"])
            age_h = (_utc_now() - seen).total_seconds() / 3600.0
            return age_h <= self._tg_emergency_threshold_hours
        except Exception:
            return False

    def _suppress_tg_dialog(self, *, emergency_override: bool) -> tuple[bool, str]:
        """Decide whether to skip TG dispatch for a dialog message (T1.5).

        Returns (suppress, reason). Suppress only when:
          - emergency-mode is enabled, AND
          - this is NOT flagged as an emergency override, AND
          - Atrium was seen recently (still the live primary surface).
        The message is already recorded in substrate as outgoing.dialog, so
        Atrium renders it regardless; we only gate the TG mirror.
        """
        if not self._tg_emergency_mode:
            return False, ""
        if emergency_override:
            return False, "emergency_override"
        if self._atrium_is_live():
            return True, "atrium_live"
        return False, "atrium_offline_past_threshold"

    def _check_gates(self, *, ignore_quiet: bool = False) -> tuple[bool, str]:
        if not self._target:
            return False, "no SONYA_PRIMARY_USER_TG_ID configured"
        # Per-day counter (separate caps for initiative vs in-session progress)
        today = _utc_now().strftime("%Y-%m-%d")
        if today != self._date_key:
            self._date_key = today
            self._sent_today = 0
            self._progress_today = 0
        if ignore_quiet:
            # In-session progress message (chat.tell_ivan called from a tool dispatch)
            if self._progress_today >= self._max_progress_per_day:
                return False, f"progress cap reached ({self._progress_today}/{self._max_progress_per_day})"
            return True, ""
        # Initiative message (idle thoughts marker, unsolicited)
        if self._sent_today >= self._max_per_day:
            return False, f"daily cap reached ({self._sent_today}/{self._max_per_day})"        # Environment-status gate: Sonya may have observed Ivan is sleeping /
        # busy / unavailable and recorded it via env.set. Respect that.
        if self._substrate is not None:
            try:
                from sonya.state.environment import EnvironmentStore
                status = EnvironmentStore(self._substrate).get("ivan_status")
                if status:
                    val = status.get("value", "").lower()
                    blocking = ("спит", "сплю", "asleep", "sleeping",
                                "занят", "busy", "не беспокоить", "dnd")
                    if any(b in val for b in blocking):
                        return False, f"observed status: ivan_status={status['value']!r}"
            except Exception:
                pass
        # Quiet window — look for latest tg event in continuity
        last_tg = self._latest_tg_seconds_ago()
        if last_tg is not None and last_tg < self._min_quiet * 60:
            mins_left = self._min_quiet - int(last_tg / 60)
            return False, f"quiet window: {mins_left}min until next allowed"
        # Escalating quiet: if the last N events are all outgoing initiatives
        # without any incoming reply from Ivan, lengthen the quiet window
        # exponentially. Prevents night-spam when Ivan is asleep / not replying.
        unanswered = self._unanswered_initiatives_streak()
        if unanswered >= 1:
            # 1 unanswered → 2x quiet, 2 unanswered → 4x, 3+ → block until reply
            if unanswered >= 3:
                return False, (
                    f"escalating quiet: {unanswered} unanswered initiatives in a row, "
                    f"waiting for Ivan to reply before next initiative"
                )
            multiplier = 2 ** unanswered  # 2, 4
            required = self._min_quiet * multiplier * 60
            if last_tg is not None and last_tg < required:
                mins_left = int((required - last_tg) / 60)
                return False, (
                    f"escalating quiet (×{multiplier}): {unanswered} unanswered, "
                    f"{mins_left}min until next allowed"
                )
        return True, ""

    def _unanswered_initiatives_streak(self) -> int:
        """Count consecutive outgoing.telegram_initiative events with no
        incoming.telegram_message between them (most recent first).

        Only `outgoing.telegram_initiative` (real unsolicited messages)
        counts toward the streak — `outgoing.telegram_progress`
        (chat.tell_ivan from a tool, ack of an Ivan-task progress) is
        explicitly excluded. Mixing them caused the escalating quiet
        window to fire on legitimate progress messages.
        """
        latest_seq = self._stream.latest_seq()
        if latest_seq <= 0:
            return 0
        events = list(self._stream.read_since(max(0, latest_seq - 200)))
        count = 0
        for ev in reversed(events):
            if ev.kind == "incoming.telegram_message":
                break
            if ev.kind == "outgoing.telegram_initiative":
                count += 1
        return count

    def _latest_tg_seconds_ago(self) -> Optional[float]:
        """Return seconds since last incoming or outgoing telegram event in continuity, or None."""
        latest_seq = self._stream.latest_seq()
        if latest_seq <= 0:
            return None
        # Read last 100 events backwards-ish (read_since gives ascending; pick newest after)
        events = list(self._stream.read_since(max(0, latest_seq - 200)))
        relevant_kinds = {
            "incoming.telegram_message",
            "outgoing.response",
            "outgoing.telegram_response",
            "outgoing.telegram_initiative",
            "outgoing.telegram_progress",
        }
        for ev in reversed(events):
            if ev.kind in relevant_kinds and ev.created_at:
                try:
                    when = datetime.fromisoformat(ev.created_at)
                    return (_utc_now() - when).total_seconds()
                except Exception:
                    continue
        return None

    def _check_recent_duplicate(
        self, text: str, *, lookback_hours: int = 6, similarity: float = 0.80
    ) -> str:
        """Return a non-empty reason string if `text` is a near-duplicate of
        any outbound TG message sent in the last ``lookback_hours``.

        Two parallel checks (any positive → blocked):
          1. Jaccard on stem-token sets (catches near-exact repeats with
             different word order or filler).
          2. Identical first-6-stem-tokens prefix (catches "Продолжаю задачу
             по трейд-боту. Начну с..." pattern where Sonya repeats the
             same intent opening across worker ticks but elaborates
             differently each time, so Jaccard is low but the meta-content
             is identical).

        Threshold 0.80 for Jaccard tuned so:
          - identical text after stem normalization = block
          - paraphrase keeping >=80% of word stems = block
          - same-shape sentence with different content tokens
            ("Продолжаю с xmlrpc" vs "Продолжаю с sucuri") = pass

        Prefix check uses first 6 stems with tail-content-required: only
        blocks if the candidate's prefix matches AND the candidate's tail
        is short / non-substantive (no concrete tokens like URLs / versions
        that signal a real finding).

        Returns "" if not a duplicate.
        """
        norm_new = _normalize_for_dedup(text)
        if len(norm_new) < 10:
            return ""  # too short to fingerprint reliably
        new_token_list = norm_new.split()
        new_tokens = set(new_token_list)
        if len(new_tokens) < 3:
            return ""
        # Prefix used by the second (intent-opening) check below.
        new_prefix = " ".join(new_token_list[:6])

        try:
            latest_seq = self._stream.latest_seq()
            if latest_seq <= 0:
                return ""
            # Walk back ~300 events; usually covers many hours.
            events = list(self._stream.read_since(max(0, latest_seq - 300)))
            cutoff_seconds = lookback_hours * 3600.0
            now = _utc_now()
            outbound_kinds = {
                "outgoing.telegram_initiative",
                "outgoing.telegram_progress",
                "outgoing.telegram_response",
                "outgoing.response",
            }
            for ev in reversed(events):
                if ev.kind not in outbound_kinds:
                    continue
                if not ev.created_at:
                    continue
                try:
                    when = datetime.fromisoformat(ev.created_at)
                except Exception:
                    continue
                age = (now - when).total_seconds()
                if age > cutoff_seconds:
                    break  # older events only further back
                payload = ev.payload or {}
                prior_text = (
                    payload.get("text")
                    or payload.get("preview")
                    or payload.get("response_text")
                    or ""
                )
                if not prior_text:
                    continue
                norm_prior = _normalize_for_dedup(str(prior_text))
                if not norm_prior:
                    continue
                # Quick exact-match on normalized fingerprint
                if norm_new == norm_prior:
                    age_min = int(age / 60)
                    return f"duplicate of message sent {age_min}min ago"
                # Token-overlap (Jaccard) for fuzzy match
                prior_tokens = set(norm_prior.split())
                if not prior_tokens:
                    continue
                intersect = len(new_tokens & prior_tokens)
                union = len(new_tokens | prior_tokens)
                if union == 0:
                    continue
                jaccard = intersect / union
                if jaccard >= similarity:
                    age_min = int(age / 60)
                    return (
                        f"near-duplicate ({jaccard:.0%} overlap) of "
                        f"message sent {age_min}min ago"
                    )
                # Intent-opening check: if normalized first-6-stem prefix
                # matches AND the candidate has no concrete content tokens
                # that differ substantively, treat as intent-only repeat.
                # Concrete content = anything containing a digit (versions,
                # IDs) or matching url-shape (.com, .org, .net domains in
                # original text). We use the original (un-stemmed) text for
                # that check — stemming truncates URLs.
                prior_token_list = norm_prior.split()
                prior_prefix = " ".join(prior_token_list[:6])
                if prior_prefix and prior_prefix == new_prefix:
                    has_concrete_content = bool(
                        re.search(r"\d|\.(com|org|net|ru|io|ws|cc|biz)\b",
                                  text, re.IGNORECASE)
                    )
                    if not has_concrete_content:
                        age_min = int(age / 60)
                        return (
                            f"intent-only repeat (same opening) of "
                            f"message sent {age_min}min ago"
                        )
        except Exception:
            pass
        return ""

    # ---------- dispatch ----------

    async def _dispatch_dialog_atrium_only(self, text: str, *, reason: str, workspace_id: str = "") -> str:
        """Record a dialog message for Atrium only (T1.5 emergency-mode).

        TG is suppressed because Atrium is the live primary surface. The event
        is `outgoing.dialog` (channel=dialog) so the Atrium feed renders it in
        the Dialog pane, but it never reaches Telegram.
        """
        self._stream.append(ContinuityEvent(
            kind="outgoing.dialog",
            channel="dialog",
            payload={
                "text": text,
                "reason": reason,
                "tg_suppressed": True,
                "surface": "atrium",
                **({"workspace_id": workspace_id} if workspace_id else {}),
            },
        ))
        if self._substrate is not None:
            try:
                from sonya.planning.memory_wiring import record_initiative_as_memory
                record_initiative_as_memory(
                    self._substrate, text, reason=f"dialog:{reason}",
                    channel="atrium_dialog",
                )
            except Exception:
                pass
        return "[OK] dialog (Atrium-only, TG suppressed — emergency-mode)"

    async def _dispatch_non_dialog(
        self, text: str, *, channel: str, reason: str
    ) -> str:
        """Dispatch event for non-dialog channels (worker_log / mind / body / voice).

        These don't go through TG (TG bridge filters them out). They are
        recorded in substrate as `outgoing.<channel>` events для рендеринга
        в Atrium pane'ах через /atrium/feed. Никаких daily caps — рендеринг
        в reason-stream / mind pane не ограничен throttle'ом.

        Privacy: для `mind` channel — если text начинается с `[PRIVATE]`
        (case-insensitive, optional whitespace), префикс убирается из text
        и event помечается private=True. Substrate видит, /atrium/feed
        пропускает. См. docs/atrium/EVENT_SCHEMA.md §3.
        """
        is_private = False
        if channel == "mind":
            stripped = re.sub(
                r"^\s*\[PRIVATE\]\s*",
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )
            if stripped != text:
                is_private = True
                text = stripped
                if not text:
                    return "[ERROR] mind: empty message after [PRIVATE] prefix"

        kind = f"outgoing.{channel}_log" if channel == "worker" else f"outgoing.{channel}"
        # Map channel → stable kind:
        #   worker_log → outgoing.worker_log
        #   mind       → outgoing.mind_thought  (focus уходит через _h_mind_focus напрямую,
        #                                        а здесь — общий thought-канал)
        #   body       → outgoing.body_expression
        #   voice      → outgoing.voice_speak
        if channel == "worker_log":
            kind = "outgoing.worker_log"
        elif channel == "mind":
            kind = "outgoing.mind_thought"
        elif channel == "body":
            kind = "outgoing.body_expression"
        elif channel == "voice":
            kind = "outgoing.voice_speak"
        else:
            kind = f"outgoing.{channel}"

        self._stream.append(ContinuityEvent(
            kind=kind,
            channel=channel,
            private=is_private,
            payload={
                "text": text,
                "reason": reason,
                "private": is_private,
            },
        ))
        # Mirror в episodic memory только для НЕ-private событий (audit/recall
        # видит substrate напрямую, episodic — это long-term накопление).
        if not is_private and self._substrate is not None:
            try:
                from sonya.planning.memory_wiring import record_initiative_as_memory
                record_initiative_as_memory(
                    self._substrate, text,
                    reason=f"{channel}:{reason}",
                    channel=f"atrium_{channel}",
                )
            except Exception:
                pass
        suffix = " [private]" if is_private else ""
        return f"[OK] {channel}{suffix}"

    async def _dispatch(self, text: str, *, reason: str, workspace_id: str = "") -> str:
        try:
            ok = await self._registry.send(
                self._channel,
                self._target,
                OutgoingMessage(text=text),
            )
        except Exception as err:
            self._stream.append(ContinuityEvent(
                kind="outgoing.telegram_initiative_failed",
                payload={
                    "reason": reason,
                    "error": f"{type(err).__name__}: {err}",
                    "preview": text[:200],
                },
            ))
            return f"[ERROR] send failed: {type(err).__name__}: {err}"
        if not ok:
            return "[ERROR] channel rejected message (channel not registered or stopped)"
        # Bump correct counter — tool calls go to progress bucket, idle/initiative
        # to the strict daily cap.
        is_progress = reason in ("tool", "task_worker", "task_progress")
        if is_progress:
            self._progress_today += 1
        else:
            self._sent_today += 1
        # Distinguish event kinds so downstream consumers (escalating quiet,
        # cross-session dedup, _unanswered_initiatives_streak) can tell
        # an ack/progress chat.tell_ivan from a real unsolicited initiative.
        # Earlier ALL outbound got kind=outgoing.telegram_initiative which
        # caused tool progress messages to inflate the unanswered counter
        # and trigger 2× / 4× quiet windows for Sonya even when she was
        # only sending requested progress updates.
        event_kind = (
            "outgoing.telegram_progress" if is_progress
            else "outgoing.telegram_initiative"
        )
        self._stream.append(ContinuityEvent(
            kind=event_kind,
            payload={
                    "reason": reason,
                    "target": self._target,
                    "text": text[:20000],
                    **({"workspace_id": workspace_id} if workspace_id else {}),
                    "sent_today": self._sent_today,
                    "daily_cap": self._max_per_day,
                    "progress_today": self._progress_today,
                "progress_cap": self._max_progress_per_day,
            },
        ))
        # Mirror into episodic memory so memory.recall finds Sonya's own
        # initiative messages later. Skip in-session progress updates —
        # those are already captured by record_response_as_memory in the
        # parent session.
        if not is_progress and self._substrate is not None:
            try:
                from sonya.planning.memory_wiring import record_initiative_as_memory
                record_initiative_as_memory(
                    self._substrate, text, reason=reason,
                    channel=f"{self._channel}_initiative",
                )
            except Exception:
                pass
        return f"[OK] sent ({self._sent_today}/{self._max_per_day} initiative, {self._progress_today}/{self._max_progress_per_day} progress)"


# ---------- safe sync wrapper for tool dispatcher ----------

def call_outbound_sync(
    gate: OutboundGate, text: str, *, channel: str = "dialog",
    emergency_override: bool = False,
    workspace_id: str = "",
) -> str:
    """Call OutboundGate.send_via_tool from sync code (the agent dispatcher).

    The dispatcher is sync and runs inside the same event loop as the channel
    runtime. We can't await here, and run_coroutine_threadsafe to the same
    thread deadlocks. Solution: fire-and-forget via create_task. The actual
    delivery + continuity event happens on the next loop turn. We do an
    immediate gate-check synchronously so the agent sees "BLOCKED" right away.

    Quiet-window is bypassed for explicit tool calls — Sonya is actively
    interacting (either in TG-session or active session). Daily cap still
    enforced. Idle-thought marker path still uses quiet-window gate.

    `channel` (v20 / Atrium Этап 0): non-dialog channels skip TG and dialog
    gates entirely; dispatched directly through `_dispatch_non_dialog`.
    """
    text = (text or "").strip()
    if not text:
        return f"[ERROR] {channel}: empty message"

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if channel != "dialog":
        # Non-dialog: skip dialog-only gates, dispatch through Atrium-only path.
        coro = gate._dispatch_non_dialog(text, channel=channel, reason="tool")
    else:
        # Этап 1.5 — emergency-only TG: suppress TG mirror if Atrium is live,
        # unless this is an explicit emergency override (identity-critical /
        # real crisis) which forces the TG dispatch.
        suppress, _why = gate._suppress_tg_dialog(emergency_override=emergency_override)
        if suppress:
            coro = gate._dispatch_dialog_atrium_only(text, reason="tool", workspace_id=workspace_id)
        else:
            ok, why = gate._check_gates(ignore_quiet=True)
            if not ok:
                return f"[BLOCKED] initiative gate: {why}"
            coro = gate._dispatch(text, reason="tool", workspace_id=workspace_id)

    if loop is not None and loop.is_running():
        loop.create_task(coro)
        if channel != "dialog":
            return f"[QUEUED] {channel} event recorded"
        return "[QUEUED] message scheduled for delivery (continuity will record outcome)"
    # No running loop — synchronous path (e.g. unit tests).
    return asyncio.run(coro)
