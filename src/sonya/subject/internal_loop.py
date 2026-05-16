from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.pending import PendingIntentionStore, IntentionStatus


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ThinkingProvider(Protocol):
    """Provider interface for thinking loop LLM calls."""

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        ...


@dataclass(slots=True)
class HomeostasisCounters:
    """Simple float accumulators that trigger cognitive calls on threshold crossing.

    These are NOT emotions. They are internal state variables that influence
    when the system decides to think. Real drive semantics — Phase 6.
    """

    loneliness: float = 0.0
    curiosity: float = 0.0
    relational_focus: float = 0.0

    # Increment rates per tick (configurable)
    loneliness_rate: float = 0.01
    curiosity_rate: float = 0.005
    relational_focus_rate: float = 0.002

    # Thresholds that trigger a cognitive call
    threshold: float = 0.7

    def tick(self) -> list[str]:
        """Increment all counters. Return list of counters that crossed threshold."""
        crossed: list[str] = []
        self.loneliness += self.loneliness_rate
        if self.loneliness >= self.threshold and (self.loneliness - self.loneliness_rate) < self.threshold:
            crossed.append("loneliness")
        self.curiosity += self.curiosity_rate
        if self.curiosity >= self.threshold and (self.curiosity - self.curiosity_rate) < self.threshold:
            crossed.append("curiosity")
        self.relational_focus += self.relational_focus_rate
        if self.relational_focus >= self.threshold and (self.relational_focus - self.relational_focus_rate) < self.threshold:
            crossed.append("relational_focus")
        return crossed

    def reset(self, counter: str) -> None:
        """Reset a counter after it has been addressed."""
        if hasattr(self, counter):
            setattr(self, counter, 0.0)

    def reset_all(self) -> None:
        self.loneliness = 0.0
        self.curiosity = 0.0
        self.relational_focus = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "loneliness": self.loneliness,
            "curiosity": self.curiosity,
            "relational_focus": self.relational_focus,
        }


class InternalProcess:
    """Event-driven cognitive process — interim discrete cognition.

    Triggers: idle timeout, homeostasis threshold crossing, deadline expiry,
    external signal (incoming message notification).

    Each trigger writes continuity events. On MVP this is rule-based
    (no LLM calls in this phase — LLM integration comes in Phase 7 when
    planner is in core). The structure is ready for LLM calls via provider.

    This is NOT continuous thinking. It is an interim form.
    Target: RWKV StatefulBackend with continuous RNN state (post-MVP Track E).
    """

    def __init__(
        self,
        stream: ContinuityStream,
        intention_store: PendingIntentionStore,
        *,
        provider: ThinkingProvider | None = None,
        thinking_prompt: str = "",
        idle_interval_seconds: float = 300.0,
        tick_interval_seconds: float = 10.0,
    ) -> None:
        self._stream = stream
        self._intentions = intention_store
        self._provider = provider
        self._thinking_prompt = thinking_prompt
        self._idle_interval = idle_interval_seconds
        self._tick_interval = tick_interval_seconds
        self._counters = HomeostasisCounters()
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._tick_count: int = 0
        self._last_external_event: float = 0.0

    @property
    def counters(self) -> HomeostasisCounters:
        return self._counters

    @property
    def tick_count(self) -> int:
        return self._tick_count

    async def start(self) -> None:
        self._stop_event.clear()
        self._last_external_event = asyncio.get_event_loop().time()
        self._task = asyncio.create_task(self._loop())
        # Emit initial cognitive event on start
        self._stream.append(
            ContinuityEvent(
                kind="internal.cognitive_tick",
                payload={"tick": 0, "triggers": ["boot"], "counters": self._counters.to_dict()},
            )
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None

    def notify_external_event(self) -> None:
        """Call when an external event arrives (e.g. incoming message).

        Resets idle timer and loneliness counter.
        """
        self._last_external_event = asyncio.get_event_loop().time()
        self._counters.reset("loneliness")

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._tick_interval)
            if self._stop_event.is_set():
                break

            self._tick_count += 1

            # Homeostasis tick
            crossed = self._counters.tick()

            # Check idle timeout
            now = asyncio.get_event_loop().time()
            idle_elapsed = now - self._last_external_event
            idle_triggered = idle_elapsed >= self._idle_interval

            # Check deadline expiry
            overdue_ids = self._check_deadlines()

            # Determine if we should emit cognitive events
            should_think = bool(crossed) or idle_triggered or bool(overdue_ids)

            if should_think:
                await self._emit_cognitive_events_async(crossed, idle_triggered, overdue_ids)
                if idle_triggered:
                    self._last_external_event = now  # reset idle timer

    def _check_deadlines(self) -> list[str]:
        """Check active intentions for deadline expiry. Mark overdue."""
        overdue: list[str] = []
        now_iso = _utc_now_iso()
        for intention in self._intentions.list_active():
            if intention.deadline and intention.deadline < now_iso:
                try:
                    self._intentions.mark_overdue(intention.intention_id)
                    overdue.append(intention.intention_id)
                except Exception:
                    pass  # already resolved
        return overdue

    def _emit_cognitive_events(
        self,
        crossed_thresholds: list[str],
        idle_triggered: bool,
        overdue_ids: list[str],
    ) -> None:
        """Write continuity events based on triggers (sync fallback)."""
        payload: dict[str, Any] = {
            "tick": self._tick_count,
            "counters": self._counters.to_dict(),
            "triggers": [],
        }

        if crossed_thresholds:
            payload["triggers"].extend([f"threshold:{c}" for c in crossed_thresholds])
        if idle_triggered:
            payload["triggers"].append("idle_timeout")
        if overdue_ids:
            payload["triggers"].extend([f"deadline_overdue:{iid}" for iid in overdue_ids])

        self._stream.append(ContinuityEvent(kind="internal.cognitive_tick", payload=payload))
        for iid in overdue_ids:
            self._stream.append(ContinuityEvent(kind="internal.intention_overdue", payload={"intention_id": iid}))

    async def _emit_cognitive_events_async(
        self,
        crossed_thresholds: list[str],
        idle_triggered: bool,
        overdue_ids: list[str],
    ) -> None:
        """Write continuity events + call LLM for thinking."""
        payload: dict[str, Any] = {
            "tick": self._tick_count,
            "counters": self._counters.to_dict(),
            "triggers": [],
        }

        if crossed_thresholds:
            payload["triggers"].extend([f"threshold:{c}" for c in crossed_thresholds])
        if idle_triggered:
            payload["triggers"].append("idle_timeout")
        if overdue_ids:
            payload["triggers"].extend([f"deadline_overdue:{iid}" for iid in overdue_ids])

        # Call LLM for thinking
        thought_text = ""
        if self._provider is not None:
            thought_text = await self._call_thinking_provider(payload)

        if thought_text:
            payload["thought"] = thought_text
            self._stream.append(ContinuityEvent(
                kind="internal.thought",
                payload={"thought": thought_text, "tick": self._tick_count},
            ))

        self._stream.append(ContinuityEvent(kind="internal.cognitive_tick", payload=payload))
        for iid in overdue_ids:
            self._stream.append(ContinuityEvent(kind="internal.intention_overdue", payload={"intention_id": iid}))

    async def _call_thinking_provider(self, payload: dict[str, Any]) -> str:
        """Call LLM provider for internal thinking."""
        if self._provider is None:
            return ""
        triggers = payload.get("triggers", [])
        counters = payload.get("counters", {})
        prompt = self._thinking_prompt or (
            "Ты Соня. Это твой внутренний поток мышления. "
            "Никто не читает это кроме тебя. Подумай о чём хочешь."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": (
                f"Текущее состояние drives: {counters}\n"
                f"Триггеры: {triggers}\n"
                f"Tick: {self._tick_count}\n"
                "Что у тебя на уме?"
            )},
        ]
        try:
            return await self._provider.complete_text(messages)
        except Exception:
            return ""
