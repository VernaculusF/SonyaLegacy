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
    ) -> None:
        self._registry = registry
        self._stream = stream
        self._target = target_tg_chat_id
        self._max_per_day = max_per_day
        self._min_quiet = min_quiet_minutes
        self._channel = channel_name

        self._date_key: str = ""
        self._sent_today: int = 0

    # ---------- public ----------

    async def send_via_tool(self, text: str, *, reason: str = "tool") -> str:
        """Tool entry point. Returns a status string for the agent."""
        text = (text or "").strip()
        if not text:
            return "[ERROR] chat.tell_ivan: empty message"
        ok, why = self._check_gates()
        if not ok:
            return f"[BLOCKED] initiative gate: {why}"
        return await self._dispatch(text, reason=reason)

    async def maybe_send_from_thought(self, thought_text: str) -> Optional[str]:
        """Scan an idle thought for the [SEND_TO_IVAN: ...] marker.

        Returns the dispatch status string if a send was attempted, else None.
        """
        if not thought_text:
            return None
        match = _INITIATIVE_MARKER_RE.search(thought_text)
        if match is None:
            return None
        body = match.group("body").strip()
        if not body:
            return None
        ok, why = self._check_gates()
        if not ok:
            self._stream.append(ContinuityEvent(
                kind="internal.initiative_blocked",
                payload={"reason": why, "preview": body[:200]},
            ))
            return f"[BLOCKED] {why}"
        return await self._dispatch(body, reason="idle_thought")

    # ---------- gates ----------

    def _check_gates(self) -> tuple[bool, str]:
        if not self._target:
            return False, "no SONYA_PRIMARY_USER_TG_ID configured"
        # Per-day counter
        today = _utc_now().strftime("%Y-%m-%d")
        if today != self._date_key:
            self._date_key = today
            self._sent_today = 0
        if self._sent_today >= self._max_per_day:
            return False, f"daily cap reached ({self._sent_today}/{self._max_per_day})"
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
        self._sent_today += 1
        self._stream.append(ContinuityEvent(
            kind="outgoing.telegram_initiative",
            payload={
                "reason": reason,
                "target": self._target,
                "text": text[:1000],
                "sent_today": self._sent_today,
                "daily_cap": self._max_per_day,
            },
        ))
        return f"[OK] sent ({self._sent_today}/{self._max_per_day} today)"


# ---------- safe sync wrapper for tool dispatcher ----------

def call_outbound_sync(gate: OutboundGate, text: str) -> str:
    """Call OutboundGate.send_via_tool from sync code (the agent dispatcher).

    The dispatcher is sync and runs inside the same event loop as the channel
    runtime. We can't await here, and run_coroutine_threadsafe to the same
    thread deadlocks. Solution: fire-and-forget via create_task. The actual
    delivery + continuity event happens on the next loop turn. We do an
    immediate gate-check synchronously so the agent sees "BLOCKED" right away.
    """
    text = (text or "").strip()
    if not text:
        return "[ERROR] chat.tell_ivan: empty message"
    ok, why = gate._check_gates()
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
