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

        self._date_key: str = ""
        self._sent_today: int = 0
        self._progress_today: int = 0

    # ---------- public ----------

    async def send_via_tool(self, text: str, *, reason: str = "tool", ignore_quiet: bool = True) -> str:
        """Tool entry point. Returns a status string for the agent.

        `ignore_quiet`: skip the quiet-window gate (default True) — when Sonya
        explicitly calls chat.tell_ivan from an agent session she's already
        actively talking to him. Daily cap still applies.
        """
        text = (text or "").strip()
        if not text:
            return "[ERROR] chat.tell_ivan: empty message"
        if _is_placeholder_text(text):
            return f"[BLOCKED] chat.tell_ivan: placeholder text leaked, no real content ({text[:60]!r})"
        ok, why = self._check_gates(ignore_quiet=ignore_quiet)
        if not ok:
            return f"[BLOCKED] initiative gate: {why}"
        return await self._dispatch(text, reason=reason)

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
        ok, why = self._check_gates(ignore_quiet=False)
        if not ok:
            self._stream.append(ContinuityEvent(
                kind="internal.initiative_blocked",
                payload={"reason": why, "preview": body[:200]},
            ))
            return f"[BLOCKED] {why}"
        return await self._dispatch(body, reason="idle_thought")

    # ---------- gates ----------

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
            return False, f"daily cap reached ({self._sent_today}/{self._max_per_day})"
        # Environment-status gate: Sonya may have observed Ivan is sleeping /
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
        return True, ""

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
        }
        for ev in reversed(events):
            if ev.kind in relevant_kinds and ev.created_at:
                try:
                    when = datetime.fromisoformat(ev.created_at)
                    return (_utc_now() - when).total_seconds()
                except Exception:
                    continue
        return None

    # ---------- dispatch ----------

    async def _dispatch(self, text: str, *, reason: str) -> str:
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
        self._stream.append(ContinuityEvent(
            kind="outgoing.telegram_initiative",
            payload={
                "reason": reason,
                "target": self._target,
                "text": text[:1000],
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

def call_outbound_sync(gate: OutboundGate, text: str) -> str:
    """Call OutboundGate.send_via_tool from sync code (the agent dispatcher).

    The dispatcher is sync and runs inside the same event loop as the channel
    runtime. We can't await here, and run_coroutine_threadsafe to the same
    thread deadlocks. Solution: fire-and-forget via create_task. The actual
    delivery + continuity event happens on the next loop turn. We do an
    immediate gate-check synchronously so the agent sees "BLOCKED" right away.

    Quiet-window is bypassed for explicit tool calls — Sonya is actively
    interacting (either in TG-session or active session). Daily cap still
    enforced. Idle-thought marker path still uses quiet-window gate.
    """
    text = (text or "").strip()
    if not text:
        return "[ERROR] chat.tell_ivan: empty message"
    ok, why = gate._check_gates(ignore_quiet=True)
    if not ok:
        return f"[BLOCKED] initiative gate: {why}"

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    coro = gate._dispatch(text, reason="tool")
    if loop is not None and loop.is_running():
        loop.create_task(coro)
        return "[QUEUED] message scheduled for delivery (continuity will record outcome)"
    # No running loop — synchronous path (e.g. unit tests).
    return asyncio.run(coro)
