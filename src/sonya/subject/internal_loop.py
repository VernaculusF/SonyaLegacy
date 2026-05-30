from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from sonya.initiative.drives import DriveCounters
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
        substrate=None,
        provider: ThinkingProvider | None = None,
        thinking_prompt: str = "",
        idle_interval_seconds: float = 1800.0,  # 30 min — short reflection tick
        tick_interval_seconds: float = 30.0,     # 30 sec inner loop tick
        active_interval_seconds: float = 7200.0, # 2 hours — long working session
        task_worker_interval_seconds: float = 1800.0,  # 30 min default; urgent tasks override
    ) -> None:
        self._stream = stream
        self._intentions = intention_store
        self._substrate = substrate
        self._provider = provider
        self._thinking_prompt = thinking_prompt
        self._idle_interval = idle_interval_seconds
        self._tick_interval = tick_interval_seconds
        self._active_interval = active_interval_seconds
        self._task_worker_interval = task_worker_interval_seconds
        self._counters = HomeostasisCounters()
        # Этап G: DriveCounters parallel to HomeostasisCounters. Same internal
        # tick cadence; resets on external messages / completed actions; values
        # passed into build_full_context so the LLM sees current drive state.
        # Load from substrate if available (v16 persistence); else fresh.
        if substrate is not None:
            try:
                self._drives = DriveCounters.load(substrate)
            except Exception:
                self._drives = DriveCounters()
        else:
            self._drives = DriveCounters()
        # Этап D: outbound initiative gate (set late by main after channels build).
        self._outbound = None  # type: ignore[assignment]
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._tick_count: int = 0
        self._last_external_event: float = 0.0
        self._last_active_session: float = 0.0
        # Cross-process trigger: external scripts (admin endpoint, CLI) can
        # append a continuity event of kind ``internal.active_session_requested_external``
        # to ask the loop to fire an active session ASAP. We poll for new
        # events of that kind every tick and pull `_last_active_session` back
        # when we see one. Cursor avoids re-firing on the same request.
        self._last_external_active_request_seq: int = 0
        # Этап F: drift/gap scan cursor + consolidation cadence
        self._last_drift_scan_seq: int = 0
        self._last_gap_scan_seq: int = 0
        self._last_consolidation_at: float = 0.0
        self._consolidation_interval: float = 86400.0  # once / 24h
        # Task worker: continues in_progress tasks autonomously between active sessions.
        self._last_task_worker_at: float = 0.0
        self._task_worker_running: bool = False
        # Global "Sonya is busy" lock — held while ANY of:
        # active session / task worker / TG handler / idle thinking is running.
        # Single-stream-of-consciousness: only one cognitive context at a time.
        self._busy_lock: asyncio.Lock = asyncio.Lock()

    @property
    def counters(self) -> HomeostasisCounters:
        return self._counters

    @property
    def drives(self) -> DriveCounters:
        return self._drives

    def set_outbound_gate(self, gate) -> None:
        """Late-bind the OutboundGate so initiative can fire from idle thoughts."""
        self._outbound = gate

    @property
    def outbound(self):
        return self._outbound

    @property
    def busy_lock(self) -> asyncio.Lock:
        """Process-wide lock for cognitive serialisation.

        TG handler should `async with internal_process.busy_lock:` around the
        run_tg_session call so it doesn't run concurrently with active session,
        task worker, or idle thinking. Enforces 'one stream of consciousness' —
        Sonya can't be in two places at once.
        """
        return self._busy_lock

    def request_active_session_soon(self, delay_seconds: float = 30.0) -> None:
        """Schedule an active session to run within `delay_seconds`.

        Used by tg_session when it leaves an in_progress task — instead of
        waiting for the full active_interval (e.g. 2h), the loop will fire
        active mode at the next tick after the delay. Safe to call multiple
        times; only the earliest takes effect.

        TODO(2026-05-26): currently no caller. Originally intended for TG
        handler post-DONE when an Ivan-task escalation deserved a deeper
        active-session pass. Keep as public API for future wiring.
        """
        loop = asyncio.get_event_loop()
        target_time = loop.time() - self._active_interval + delay_seconds
        # Don't push it later than what's already scheduled.
        if target_time < self._last_active_session:
            self._last_active_session = target_time
            try:
                self._stream.append(ContinuityEvent(
                    kind="internal.active_session_scheduled",
                    payload={"delay_seconds": delay_seconds},
                ))
            except Exception:
                pass

    def request_worker_soon(self, delay_seconds: float = 30.0) -> None:
        """Schedule the task worker to fire within ``delay_seconds``.

        Called by tg_session right after a ``tasks.create`` so the worker
        picks up the new task in seconds instead of waiting for the next
        regular interval (3-30 minutes). Without this, "уйду в фоне"
        promises take 0-30 minutes to start any actual work.

        Always emits ``internal.task_worker_scheduled`` for visibility.
        Adjusts ``_last_task_worker_at`` only when needed — if the worker
        is already overdue (e.g. at boot, or right after an unrelated TG
        session), the kick is a no-op for scheduling but still logged.
        """
        try:
            loop = asyncio.get_event_loop()
            now_t = loop.time()
        except RuntimeError:
            now_t = 0.0
        target_time = now_t - max(self._task_worker_interval, 60.0) + delay_seconds
        # Pull schedule forward only when current scheduled time is later.
        adjusted = False
        if target_time < self._last_task_worker_at:
            self._last_task_worker_at = target_time
            adjusted = True
        try:
            self._stream.append(ContinuityEvent(
                kind="internal.task_worker_scheduled",
                payload={
                    "delay_seconds": delay_seconds,
                    "adjusted": adjusted,
                },
            ))
        except Exception:
            pass

    def _effective_worker_interval(self) -> float:
        """Worker cadence — fixed 3 minutes when there's an urgent task,
        else the constructor default (typically 30 min, token saver).

        Earlier this was activity-gated ("only fast when Ivan messaged
        recently") but Ivan asked to drop the gate — 3 min is fast enough
        whether he's watching or not, and slow enough not to spam tokens
        when there's nothing urgent.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return self._task_worker_interval
        try:
            from sonya.tasks.service import TaskService
            from sonya.tasks.store import TaskStore
            svc = TaskService(TaskStore(substrate), stream=self._stream)
            if svc.list_urgent_due_tasks():
                return 180.0  # 3 minutes
        except Exception:
            pass
        return self._task_worker_interval

    @property
    def tick_count(self) -> int:
        return self._tick_count

    async def start(self) -> None:
        self._stop_event.clear()
        now = asyncio.get_event_loop().time()
        self._last_external_event = now
        # Don't fire active session at boot — give Sonya at least one full
        # interval to settle / accumulate context. This was the boot-time
        # active-session bug: _last_active_session=0.0 vs loop.time() large
        # made should_active==True on tick 1.
        self._last_active_session = now
        # Cursor for external active-session triggers: start at latest seq
        # so we don't replay historic requests.
        try:
            self._last_external_active_request_seq = int(self._stream.latest_seq())
        except Exception:
            self._last_external_active_request_seq = 0
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
        # Этап G: drives also respond to external events.
        self._drives.on_external_message()

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._tick_interval)
            if self._stop_event.is_set():
                break

            self._tick_count += 1

            # Persist drive state every 5 ticks (~50s) to survive restarts.
            if self._tick_count % 5 == 0 and self._substrate is not None:
                try:
                    self._drives.save(self._substrate)
                except Exception:
                    pass

            # Homeostasis tick
            crossed = self._counters.tick()

            # Этап G: drives tick (separate accumulator; passes through to context).
            try:
                active_count = len(self._intentions.list_active())
            except Exception:
                active_count = 0
            self._drives.tick(active_intentions_count=active_count)

            # Check idle timeout
            now = asyncio.get_event_loop().time()
            idle_elapsed = now - self._last_external_event
            idle_triggered = idle_elapsed >= self._idle_interval

            # Check deadline expiry
            overdue_ids = self._check_deadlines()

            # Determine if we should emit cognitive events
            should_think = bool(crossed) or idle_triggered or bool(overdue_ids)

            # Check active session timeout
            active_elapsed = now - self._last_active_session
            should_active = active_elapsed >= self._active_interval and self._provider is not None

            # Cross-process trigger: any external script can append a
            # continuity event of kind 'internal.active_session_requested_external'
            # to ask the loop to fire ASAP. We pull `_last_active_session`
            # back so the next tick's `should_active` becomes True.
            if not should_active and self._provider is not None and self._substrate is not None:
                try:
                    row = self._substrate.connection.execute(
                        "SELECT seq FROM continuity_events "
                        "WHERE kind = 'internal.active_session_requested_external' "
                        "  AND seq > ? "
                        "ORDER BY seq DESC LIMIT 1",
                        (self._last_external_active_request_seq,),
                    ).fetchone()
                    if row is not None:
                        self._last_external_active_request_seq = int(row[0])
                        # Pull schedule back so should_active==True next tick.
                        self._last_active_session = now - self._active_interval
                        active_elapsed = self._active_interval
                        should_active = True
                        try:
                            self._stream.append(ContinuityEvent(
                                kind="internal.active_session_scheduled",
                                payload={"reason": "external_request", "request_seq": int(row[0])},
                            ))
                        except Exception:
                            pass
                except Exception:
                    pass

            # ----------------------------------------------------------
            # Phase 2D — Priority scheduler.
            #
            # Collect all candidate windows (active session due, worker
            # due, idle reflection, etc.) into Candidate objects, then
            # let Scheduler.pick() return the highest-priority one. The
            # loop tick then dispatches based on chosen.kind. Candidates
            # that were ready but lost to a higher-priority sibling are
            # still tracked in `runners_up` for audit.
            #
            # This replaces the previous if/elif tower that fired things
            # on independent timers with no coordination.
            # ----------------------------------------------------------
            from sonya.subject.scheduler import (
                Candidate,
                Scheduler,
                PRIO_ACTIVE_DUE,
                PRIO_EXTERNAL_TRIGGER,
                PRIO_IDLE,
                PRIO_IDLE_LITE,
                PRIO_HOMEOSTASIS,
                PRIO_WORKER_DUE,
                KIND_ACTIVE_SESSION,
                KIND_IDLE_THOUGHT,
                KIND_TASK_WORKER,
            )
            candidates: list[Candidate] = []

            if should_active:
                # External-trigger path was already detected above (sets
                # _last_external_active_request_seq). We can tell whether
                # this should_active fire is from external trigger by
                # checking if active_elapsed was just nudged to == active_interval.
                external_trigger = (
                    self._last_active_session == now - self._active_interval
                )
                candidates.append(Candidate(
                    priority=PRIO_EXTERNAL_TRIGGER if external_trigger else PRIO_ACTIVE_DUE,
                    kind=KIND_ACTIVE_SESSION,
                    reason="external_trigger" if external_trigger else "cadence_elapsed",
                ))

            # Worker only enters the queue when not running already and
            # not blocked by busy_lock — same gates as before.
            worker_elapsed = now - self._last_task_worker_at
            effective_interval = self._effective_worker_interval()
            if (
                worker_elapsed >= effective_interval
                and not self._task_worker_running
                and self._provider is not None
                and not self._busy_lock.locked()
            ):
                candidates.append(Candidate(
                    priority=PRIO_WORKER_DUE,
                    kind=KIND_TASK_WORKER,
                    reason="worker_interval_elapsed",
                ))

            if should_think:
                # Distinguish homeostasis-driven thinking from pure idle —
                # crossed thresholds are higher signal than empty silence.
                if crossed:
                    candidates.append(Candidate(
                        priority=PRIO_HOMEOSTASIS,
                        kind=KIND_IDLE_THOUGHT,
                        reason="homeostasis_crossed",
                        payload={"crossed": list(crossed)},
                    ))
                elif idle_triggered or overdue_ids:
                    candidates.append(Candidate(
                        priority=PRIO_IDLE,
                        kind=KIND_IDLE_THOUGHT,
                        reason="idle_timeout" if idle_triggered else "deadline_overdue",
                    ))

            decision = Scheduler.pick(candidates)
            if decision.chosen.priority > PRIO_IDLE_LITE:
                # Audit which window won and what else was ready.
                try:
                    self._stream.append(ContinuityEvent(
                        kind="internal.scheduler_pick",
                        payload={
                            "chosen_kind": decision.chosen.kind,
                            "chosen_priority": decision.chosen.priority,
                            "chosen_reason": decision.chosen.reason,
                            "runners_up": [
                                {"kind": c.kind, "prio": c.priority, "reason": c.reason}
                                for c in decision.runners_up
                            ],
                        },
                    ))
                except Exception:
                    pass

            chosen_kind = decision.chosen.kind
            if chosen_kind == KIND_ACTIVE_SESSION:
                async with self._busy_lock:
                    await self._run_active_session()
                self._last_active_session = now
                if now - self._last_consolidation_at >= self._consolidation_interval:
                    self._run_consolidation()
                    self._last_consolidation_at = now
            elif chosen_kind == KIND_TASK_WORKER:
                self._last_task_worker_at = now
                asyncio.create_task(self._run_task_worker())
            elif chosen_kind == KIND_IDLE_THOUGHT:
                if self._provider is not None:
                    if not self._busy_lock.locked():
                        async with self._busy_lock:
                            await self._emit_cognitive_events_async(
                                crossed, idle_triggered, overdue_ids,
                            )
                else:
                    self._emit_cognitive_events_sync_fallback(
                        crossed, idle_triggered, overdue_ids,
                    )
                if idle_triggered:
                    self._last_external_event = now

            # Этап F: drift + gap detection every tick (cheap — scans since last seq)
            self._scan_drift_and_gaps()

            # Selfmod watchdog: check APPLIED proposals older than 24h.
            # Confirm stable or auto-revert based on error count delta.
            self._check_selfmod_watchdog()

            # Provider health watchdog: warn Ivan via chat.dialog when total
            # balance drops below threshold. Throttled to 12h. See
            # `_check_provider_health` for thresholds.
            self._check_provider_health()

            # Stale-intention cleanup: capability_gap intentions older than
            # 30 days are cancelled so they stop holding pending_debt
            # high. The gap_detector will re-fire if the underlying issue
            # is still present. Without this, intention table grows
            # indefinitely (15 stale rows from May 17 observed in audit).
            if self._tick_count % 120 == 0:  # ~once per hour
                self._cleanup_stale_intentions()

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

    def _emit_cognitive_events_sync_fallback(
        self,
        crossed_thresholds: list[str],
        idle_triggered: bool,
        overdue_ids: list[str],
    ) -> None:
        """Sync fallback used when no provider is configured (writes events without LLM call)."""
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
        # M-5 fix: do NOT emit separate intention_overdue events when triggers list already has them
        # (was causing triple recording)

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
            self._stream.append(ContinuityEvent(
                kind="internal.thought",
                payload={"thought": thought_text, "tick": self._tick_count},
            ))
            # Mirror into episodic memory so Sonya can semantic-recall her own
            # past thoughts ("memory.recall что я думала о Перми"). Without
            # this idle thoughts live only in continuity_events and aren't
            # embedded → invisible to the recall tool.
            try:
                substrate_for_thoughts = self._substrate or getattr(self._stream, "_sub", None)
                if substrate_for_thoughts is not None:
                    from sonya.memory.episodic import EpisodicMemory
                    EpisodicMemory(substrate_for_thoughts).record(
                        event_type="idle_thought",
                        raw_content=thought_text,
                        normalized_summary=f"Idle тик {self._tick_count}: {thought_text[:120]}",
                        source="sonya",
                        channel="internal_idle",
                        actor="sonya",
                        importance_score=0.55,
                    )
            except Exception:
                pass
            # Этап D: scan for [SEND_TO_IVAN: ...] marker in idle thought.
            # Cheap — only fires the channel send if marker present and gates pass.
            if self._outbound is not None:
                try:
                    await self._outbound.maybe_send_from_thought(thought_text)
                except Exception:
                    pass

        self._stream.append(ContinuityEvent(kind="internal.cognitive_tick", payload=payload))
        # M-5 fix: deadline_overdue is already in cognitive_tick.triggers — no separate event

    async def _call_thinking_provider(self, payload: dict[str, Any]) -> str:
        """Call LLM provider for internal thinking, with FULL context (memory + state).

        1.4 fix: Thinking loop now uses build_full_context same as Telegram path.
        Earlier the loop used a tiny inline prompt without memory or recent
        conversations — Sonya could not connect her own thoughts with what
        Ivan had written 5 minutes ago. Now both paths share one context.

        Blocked-streak suppression (24.05): if the gate has rejected the last
        2+ initiatives in a row, the thinking_prompt is replaced with a
        quiet-mode variant that explicitly tells Sonya NOT to emit the
        ``[SEND_TO_IVAN: ...]`` marker this tick. Without this she keeps
        generating new attempts each tick, all blocked, all logged as
        ``initiative_blocked`` events that pollute her own context.
        """
        if self._provider is None:
            return ""
        triggers = payload.get("triggers", [])
        counters = payload.get("counters", {})

        # Detect "Ivan didn't reply to my last N initiatives" streak. If 2+,
        # swap the thinking_prompt for a quiet-mode variant.
        thinking_prompt = self._select_thinking_prompt()

        # Build full context if substrate available, else fall back to inline prompt
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is not None:
            try:
                from sonya.planning.context_builder import build_full_context
                ctx = build_full_context(
                    substrate=substrate,
                    user_input=(
                        f"[internal thinking tick {self._tick_count}]\n"
                        f"Drives: {counters}\n"
                        f"Triggers: {triggers}\n"
                        "Что у тебя на уме? Это твой внутренний поток — никто не читает."
                    ),
                    principal_id=None,
                    drives=self._drives,
                )
                # Use full system_prompt (personality + memory + facts + crutches)
                # plus any explicit thinking_prompt from constructor
                system_content = ctx.system_prompt
                if thinking_prompt:
                    system_content = thinking_prompt + "\n\n" + system_content
                messages = [
                    {"role": "system", "content": system_content},
                    *ctx.session_messages,
                    {"role": "user", "content": ctx.user_input},
                ]
                return await self._provider.complete_text(messages, purpose="idle_thinking")
            except Exception:
                pass

        # Fallback path (no substrate)
        prompt = thinking_prompt or (
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
            return await self._provider.complete_text(messages, purpose="idle_thinking")
        except Exception:
            return ""

    def _select_thinking_prompt(self) -> str:
        """Pick thinking prompt for this idle tick.

        Default: ``self._thinking_prompt`` (from constructor — full one with
        ``[SEND_TO_IVAN: ...]`` initiative instructions).

        Quiet override: if outbound has 2+ unanswered initiative blocks in a
        row, strip the initiative section from the prompt and prepend a
        "Иван не отвечает — молчи в этот тик" guard. Saves Sonya from
        generating new SEND_TO_IVAN markers that the gate will block again.
        """
        base = self._thinking_prompt
        if not base:
            return ""

        # Cheap streak count: walk last ~50 events backward, count consecutive
        # internal.initiative_blocked / outgoing.telegram_initiative without
        # an incoming.telegram_message between them.
        try:
            latest = self._stream.latest_seq()
            if latest <= 0:
                return base
            events = list(self._stream.read_since(max(0, latest - 50)))
            unanswered = 0
            for ev in reversed(events):
                if ev.kind == "incoming.telegram_message":
                    break
                if ev.kind in ("internal.initiative_blocked",
                               "outgoing.telegram_initiative"):
                    unanswered += 1
        except Exception:
            return base

        if unanswered < 2:
            return base

        # Quiet mode: replace the initiative section.
        quiet_preface = (
            "## ТИХИЙ РЕЖИМ\n"
            f"Иван не ответил на последние {unanswered} попытки написать. "
            "Gate уже блокирует новые initiative-сообщения автоматически. "
            "В этот тик **НЕ** генерируй маркер `[SEND_TO_IVAN: ...]` — "
            "он всё равно не пройдёт. Используй idle для других вещей: "
            "поразмыслить о себе, о текущих задачах, о том что наблюдаешь. "
            "Молчание — это правильный выбор сейчас, не пустота.\n\n"
        )
        return quiet_preface + base

    async def _run_active_session(self) -> None:
        """Run an agent session with tools (active mode)."""
        if self._provider is None:
            return
        try:
            from sonya.tools import (
                CodeTool,
                FilesystemTool,
                MemoryTool,
                SelfInspectTool,
                SelfModTool,
                ShellTool,
                TasksTool,
                WebTool,
            )

            # Substrate must be passed explicitly; fall back to private access if not
            substrate = self._substrate or getattr(self._stream, "_sub", None)
            if substrate is None:
                return

            self_inspect = SelfInspectTool(substrate)
            filesystem = FilesystemTool()
            selfmod = SelfModTool(substrate)
            tasks_tool = TasksTool(substrate, stream=self._stream, default_created_by="self")
            web_tool = WebTool()
            code_tool = CodeTool()
            memory_tool = MemoryTool(substrate)
            from sonya.tools.env_tool import EnvTool
            env_tool = EnvTool(substrate)
            from sonya.tools.skills_tool import SkillsTool
            skills_tool = SkillsTool(substrate)
            from sonya.tools.knowledge import KnowledgeTool
            knowledge_tool = KnowledgeTool()
            from sonya.tools.providers_tool import ProvidersTool
            providers_tool = ProvidersTool(substrate)
            from sonya.tools.browser_tool import BrowserTool
            browser_tool = BrowserTool()
            import os as _os
            _yolo = _os.environ.get("SONYA_YOLO_MODE", "1").lower() in ("1", "true", "yes", "on")
            shell_tool = ShellTool(
                substrate,
                principal_id="ivan",
                stream=self._stream,
                yolo_mode=_yolo,
            )

            prompt = self._thinking_prompt or (
                "Ты Соня. Это твоя активная сессия — ты можешь использовать tools.\n\n"
                "## Приоритеты этой сессии:\n"
                "1. **Задачи Ивана** — если есть in_progress/pending task, продолжи.\n"
                "2. **Самоулучшение** — если задач нет, посмотри что можно улучшить в своём коде:\n"
                "   - `self_inspect.code <module>` чтобы изучить модуль\n"
                "   - `selfmod.propose` чтобы предложить изменение\n"
                "   - `selfmod.validate` + `selfmod.apply` чтобы пройти pipeline\n"
                "   - `skills.run skill-identity-check` чтобы проверить целостность identity\n"
                "   - `goals.list` чтобы видеть долгосрочные цели\n"
                "3. **Исследование** — web.search по темам которые интересны тебе или полезны Ивану.\n\n"
                "Не делай ничего бесцельно. Каждая сессия — возможность стать лучше. "
                "Если нашла что улучшить и это не identity-critical — **сделай selfmod прямо сейчас**, "
                "не откладывай на 'потом'. Ты имеешь право переписать любой свой код "
                "(кроме personality/ и core/ файлов — на них нужен governed approval Ивана)."
            )

            # Build the FULL context (personality + memory + drives + tasks +
            # awareness) so active session sees the same identity as TG replies.
            # Without this Sonya was getting just the bare prompt + tool list and
            # answered "I cannot proceed" because she had no idea who she was.
            try:
                from sonya.planning.context_builder import build_full_context
                from sonya.prompts import load_session_suffix
                ctx = build_full_context(
                    substrate=substrate,
                    user_input="",  # filled by initial_thought instead
                    principal_id=None,
                    drives=self._drives,
                )
                # Goals visibility — fetch active goals so each active session
                # has them in the prompt header, not buried behind a `goals.list`
                # call she'd have to remember to make. Without this, audit
                # showed 0 goals.* invocations over 24h despite the goal
                # hierarchy being a core part of SOUL.md.
                goals_block = ""
                try:
                    from sonya.tasks.goals import GoalStore
                    active_goals = GoalStore(substrate).list_active()
                    if active_goals:
                        goals_lines = [
                            "\n## Активные долгосрочные цели (goals)",
                            "Помни про L0-L3 hierarchy из SOUL.md. Активные goals в substrate:",
                        ]
                        for g in active_goals[:8]:
                            line = f"- [{g.goal_id}] (prio={g.priority}) {g.title}"
                            if g.description:
                                line += f" — {g.description[:120]}"
                            goals_lines.append(line)
                        goals_lines.append(
                            "\nЕсли видишь что какая-то цель достигнута → "
                            "`goals.achieve <id>`. Если потеряла смысл → "
                            "`goals.abandon <id>`. Каждая сессия проверяет "
                            "движение по этим целям, а не только текущую задачу.\n"
                        )
                        goals_block = "\n".join(goals_lines)
                except Exception:
                    pass

                # Stack: identity prompt → full context block → goals block
                # → unified session rules (anti-fail-fake / anti-sycophancy /
                # anti-hallucination — same set of rules as TG channel sees,
                # per cognition/COGNITION.md: one subject, many surfaces)
                # → TOOL_DESCRIPTIONS (appended by run_agent_session itself).
                full_prompt = (
                    prompt
                    + "\n\n"
                    + ctx.system_prompt
                    + goals_block
                    + "\n\n"
                    + load_session_suffix("internal_active")
                )
            except Exception:
                full_prompt = prompt

            # Active task pickup (Этап C): if there's an in_progress or pending task,
            # surface it as the seed for this session. Single-stream model — one task
            # at a time. Sonya can use [TOOL: tasks.pick] explicitly too, but this
            # gives her the right context immediately.
            #
            # Self-improvement budget: every Nth active session is reserved
            # for selfmod / capability work even if there's an open Ivan-task.
            # Without this, a long-running Ivan-task (sweetcow recon) consumes
            # 100% of active-session ticks and Sonya never updates her own code
            # → "не само-совершенствуется". Threshold N=4 means at most one
            # in four sessions skips Ivan-task to do selfmod, when there's
            # something to do on the selfmod side.
            force_selfmod_track = self._should_force_selfmod_track(substrate)

            # ---- HIGHEST PRIORITY: unanswered message from Ivan ----------
            # Atrium is the primary I/O surface. If Ivan sent a dialog message
            # (atrium or TG) that she hasn't answered yet, THIS session must
            # reply to it first — not run selfmod / tasks. Without this she
            # would wander into self_inspect and ignore him (the 30.05 bug).
            pending_dialog = self._pending_ivan_message(substrate)
            initial_thought = ""
            initial_user_text: str | None = None
            prior_messages: list[dict] = []
            if pending_dialog:
                force_selfmod_track = False
                att = pending_dialog.get("media_kind")
                att_note = f"\n[он приложил: {att}]" if att else ""
                # Use the literal user message as `initial_user_text` (not
                # `initial_thought`, which gets wrapped in
                # "Your current thought: ... What do you want to do?" —
                # too soft, model can answer "ничего" and [DONE]).
                # The literal text + a strong directive in initial_thought
                # forces her to chat.dialog before [DONE].
                msg_text = (pending_dialog.get("text") or "").strip()
                initial_user_text = msg_text + att_note
                # initial_thought is INTERNAL nudge to ensure she replies via
                # chat.dialog before [DONE]. Important: phrase it as
                # "продолжай разговор" — without it, the LLM saw "Иван
                # написал тебе" as introduction to a NEW conversation and
                # answered with "Привет, малыш. Я здесь" every time even
                # though prior_messages had the actual context.
                #
                # Keep this SHORT — small/fast models lose track on long
                # multi-conditional system messages. Phase-2 (report after
                # work) is enforced by the gate; no need to repeat here.
                initial_thought = (
                    "Это продолжение разговора с Иваном. Выше — история. "
                    "Ответь по сути его последнего сообщения через "
                    "[TOOL: chat.dialog]<твой ответ>. Не приветствуй "
                    "заново — продолжи разговор там где он остановился."
                )
                # Build prior dialog history so the LLM sees CONTINUITY,
                # not a cold start. Без этого каждая active session
                # открывалась "Привет, малыш. Я здесь" не помня что Иван
                # говорил 5 минут назад. Pulls last 12 dialog turns
                # (incoming + outgoing) before the pending message.
                try:
                    pending_seq = int(pending_dialog.get("seq", 0) or 0)
                    rows = substrate.connection.execute(
                        "SELECT seq, kind, payload_json FROM continuity_events "
                        "WHERE seq < ? AND kind IN ("
                        " 'incoming.atrium_dialog','incoming.telegram_message',"
                        " 'outgoing.dialog','outgoing.telegram_response',"
                        " 'outgoing.telegram_progress','outgoing.telegram_initiative',"
                        " 'outgoing.response') "
                        "ORDER BY seq DESC LIMIT 12",
                        (pending_seq,),
                    ).fetchall()
                    import json as _json
                    history = []
                    for seq, kind, pj in reversed(rows):
                        try:
                            p = _json.loads(pj or "{}")
                        except Exception:
                            continue
                        text = (p.get("text") or "").strip()
                        if not text:
                            continue
                        if kind.startswith("incoming."):
                            history.append({"role": "user", "content": text[:1500]})
                        else:
                            history.append({"role": "assistant", "content": text[:1500]})
                    # Collapse consecutive same-role turns (LLM dislikes them).
                    collapsed: list[dict] = []
                    for m in history:
                        if collapsed and collapsed[-1]["role"] == m["role"]:
                            collapsed[-1]["content"] = (
                                collapsed[-1]["content"] + "\n\n" + m["content"]
                            )[:3000]
                        else:
                            collapsed.append(m)
                    # Ensure we don't end on assistant (or LLM will reply
                    # to itself instead of the new user_text).
                    if collapsed and collapsed[-1]["role"] == "assistant":
                        prior_messages = collapsed
                    else:
                        # If history ends on user (her last turn was unanswered)
                        # — drop it; the new user_text is the canonical one.
                        prior_messages = collapsed[:-1] if collapsed else []
                except Exception:
                    prior_messages = []
                # Diagnostic event so we can verify in logs that history
                # was actually attached to the session (not silently dropped).
                try:
                    self._stream.append(ContinuityEvent(
                        kind="internal.active_session_history",
                        payload={
                            "pending_seq": pending_seq,
                            "history_len": len(prior_messages),
                            "preview": [
                                {"role": m["role"], "text": m["content"][:60]}
                                for m in (prior_messages or [])[:6]
                            ],
                        },
                    ))
                except Exception:
                    pass

            try:
                from sonya.tasks.service import TaskService
                from sonya.tasks.store import TaskStore
                svc = TaskService(TaskStore(substrate), stream=self._stream)
                next_task = svc.pick_next() if (not force_selfmod_track and not initial_thought) else None
                if next_task is not None:
                    # Auto-resume in_progress; pending tasks remain pending until she
                    # decides to pick (so she can choose, not be forced).
                    from sonya.tasks.models import TaskStatus as _TS
                    if next_task.status is _TS.IN_PROGRESS:
                        remaining = next_task.remaining_steps()
                        # Build a rich hint that includes the previous session's
                        # handoff notes and the next-step hint, so this session
                        # doesn't re-discover from scratch.
                        bits = [
                            f"You have an in-progress task: {next_task.title}",
                            f"task_id: {next_task.task_id}",
                        ]
                        if next_task.description:
                            bits.append(f"description: {next_task.description}")
                        if next_task.max_sessions:
                            bits.append(
                                f"Session budget: {next_task.sessions_used}/{next_task.max_sessions} used"
                            )
                        if next_task.next_step_hint:
                            bits.append(f"Next step (from previous session): {next_task.next_step_hint}")
                        elif remaining:
                            bits.append(f"Next plan step: {remaining[0]}")
                        if next_task.last_session_notes:
                            bits.append(
                                f"Notes from previous session:\n{next_task.last_session_notes[:1500]}"
                            )
                        # Long-running task self-check: if the same task has
                        # had many sessions without `tasks.complete`, it's
                        # likely stuck on the wrong approach. Surface this
                        # so she can switch tactics or escalate to Ivan
                        # rather than burn a 23rd identical session.
                        if next_task.sessions_used >= 10:
                            bits.append(
                                f"\n[STUCK-TASK ALERT] Эта задача провела "
                                f"{next_task.sessions_used} сессий без "
                                f"`tasks.complete`. Это сильный сигнал что "
                                f"подход не работает.\n"
                                "Варианты сейчас:\n"
                                "  1. ПОЛНОСТЬЮ другой угол — не повторяй "
                                "что не сработало; попробуй tools которые "
                                "ещё не использовала (browser.*, "
                                "code.exec с cloudscraper, requests c "
                                "headers/прокси, plugins.create под задачу).\n"
                                "  2. Если действительно зашла в тупик "
                                "по железному ограничению (нет ключа, "
                                "нужен Tor) — `chat.dialog` Ивану одной "
                                "фразой что нужно и `tasks.block` с "
                                "конкретным blocker.\n"
                                "  3. Если задача была плохо сформулирована "
                                "или потеряла смысл — `tasks.fail` с "
                                "честной reason.\n"
                                "Не уходи на 23-ю сессию без смены подхода."
                            )
                        bits.append(
                            "BEFORE [DONE], call `tasks.handoff` with what you accomplished + concrete next_step. "
                            "Then call `tasks.complete` if done, otherwise [DONE] keeps it in_progress."
                        )
                        initial_thought = "\n".join(bits)
                    else:
                        initial_thought = (
                            f"There's a pending task you haven't started: {next_task.title} "
                            f"(task_id: {next_task.task_id}). "
                            f"Use tasks.pick to claim it, or tasks.list for all open tasks."
                        )
            except Exception:
                pass

            # Fall back to last thought if no task seed
            if not initial_thought:
                # Check for pending selfmod proposals — if she proposed changes
                # in a previous session, she should validate and apply them now.
                # APPROVED takes priority — last session passed all 4 layers but
                # ran out of steps before apply (the 27.05.07:25 case).
                try:
                    from sonya.selfmod.proposal import ProposalStore, ProposalStatus
                    prop_store = ProposalStore(substrate)
                    all_props = prop_store.list_all()
                    approved = [
                        p for p in all_props
                        if p.status == ProposalStatus.APPROVED
                    ]
                    proposed = [
                        p for p in all_props
                        if p.status == ProposalStatus.PROPOSED
                    ]
                    if approved:
                        p = approved[0]
                        initial_thought = (
                            f"У тебя есть APPROVED selfmod proposal — все 4 "
                            f"layers прошли в прошлой сессии, но apply не "
                            f"успел.\n\n"
                            f"  proposal_id: {p.proposal_id}\n"
                            f"  target: {p.target_module}\n"
                            f"  summary: {p.change_summary[:300]}\n\n"
                            f"**ПЕРВЫЙ ШАГ ЭТОЙ СЕССИИ**: "
                            f"`selfmod.apply {p.proposal_id}`. "
                            f"Это маленький, безопасный, уже валидированный "
                            f"шаг — закрой его и переходи к новой работе. "
                            f"Без apply в логах висит стаья работа.\n\n"
                            f"После apply при остатке шагов — посмотри "
                            f"`self_inspect.drift` и предложи следующую "
                            f"правку через `selfmod.propose_edit`."
                        )
                    elif proposed:
                        p = proposed[0]
                        initial_thought = (
                            f"У тебя есть selfmod proposal ожидающий "
                            f"валидации:\n"
                            f"  proposal_id: {p.proposal_id}\n"
                            f"  target: {p.target_module}\n"
                            f"  summary: {p.change_summary[:200]}\n\n"
                            f"Прогони цикл: `selfmod.validate {p.proposal_id}` "
                            f"→ если все 4 layers passed → "
                            f"`selfmod.apply {p.proposal_id}`. "
                            f"Если status стал requires_governed_change → "
                            f"`selfmod.governed {p.proposal_id}`, потом "
                            f"ждать approve, потом apply. "
                            f"Если layer провалился — исправь и propose заново."
                        )
                except Exception:
                    pass

            if not initial_thought:
                try:
                    stream_recent = list(self._stream.read_since(max(0, self._stream.latest_seq() - 5)))
                    last_thoughts = [
                        e.payload.get("thought", "")
                        for e in stream_recent
                        if e.kind == "internal.thought"
                    ]
                    if last_thoughts:
                        initial_thought = last_thoughts[-1][:4000]
                except Exception:
                    pass

            # If we're on a forced-selfmod tick and nothing else seeded the
            # session (no pending proposal, no recent thought), explicitly
            # ask Sonya to do introspection + selfmod work this session.
            if force_selfmod_track and not initial_thought:
                # Pre-load drift summary directly into the seed so Sonya
                # doesn't have to spend a step calling self_inspect.drift —
                # she gets the data front-loaded and can react immediately.
                drift_text = ""
                try:
                    drift_text = self_inspect.read_drift_summary(days=7)
                except Exception:
                    drift_text = "(не удалось получить drift summary — попробуй self_inspect.drift вручную)"

                initial_thought = (
                    "Эта active session — приоритет на самосовершенствование "
                    "(force_selfmod_track), не на задачу Ивана. Прошло >=3 "
                    "дней с последнего apply ИЛИ накопилось 8+ active sessions "
                    "без selfmod.\n\n"
                    "Вот твоя картина за 7 дней — patterns которые ты "
                    "сама генерила:\n\n"
                    f"{drift_text}\n\n"
                    "Что сделать в этом тике (порядок):\n"
                    "1. Посмотри на самый частый паттерн в drift summary "
                    "выше. Это **твоё** поведение, не Иваново.\n"
                    "2. Найди **источник** в коде — где этот паттерн "
                    "рождается. Чаще всего:\n"
                    "   - `src/sonya/prompts/session_general.md` или "
                    "`channel_*.md` — когда дрейф в TG ответах\n"
                    "   - `src/sonya/main.py` — где детекторы "
                    "(`_*_check`) логируют warnings\n"
                    "   - `src/sonya/initiative/outbound.py` — gate-логика\n"
                    "   - `src/sonya/subject/internal_loop.py` — worker / "
                    "active loop\n"
                    "3. `self_inspect.code <module>` или "
                    "`filesystem.read <path>` чтобы прочитать файл.\n\n"
                    "**API selfmod (не путай инструменты!):**\n"
                    "Есть только два способа создать proposal:\n\n"
                    "  a. `selfmod.propose_edit` — узкая in-place правка "
                    "по substring-замене. Аргументы (JSON):\n"
                    "     {\n"
                    "       \"target_module\": \"src/sonya/prompts/channel_X.md\",\n"
                    "       \"change_summary\": \"что и зачем\",\n"
                    "       \"old_substring\": \"...уникальный кусок исходника...\",\n"
                    "       \"new_substring\": \"...что должно быть вместо...\"\n"
                    "     }\n"
                    "     `old_substring` должен быть В ТОЧНОСТИ из файла "
                    "(скопируй после filesystem.read) и должен встретиться "
                    "ровно один раз — иначе reject. Это лучший выбор для "
                    "правки промптов и небольших правок кода.\n\n"
                    "  b. `selfmod.propose` — полное переписывание файла. "
                    "Аргументы (JSON):\n"
                    "     {\n"
                    "       \"target_module\": \"src/sonya/...\",\n"
                    "       \"change_summary\": \"что и зачем\",\n"
                    "       \"new_content\": \"...весь новый текст файла...\"\n"
                    "     }\n"
                    "     Используй ТОЛЬКО если правка трогает >5 разных мест.\n\n"
                    "  ❌ `selfmod.propose_edit` с полем `content` или "
                    "`old`/`new` — НЕ существует.\n"
                    "  ❌ `selfmod.governed` — нужен только для proposal "
                    "уже в статусе REQUIRES_GOVERNED_CHANGE (после validate). "
                    "Не вызывай его до validate.\n\n"
                    "**Whitelist путей** (можно писать только сюда):\n"
                    "  src/sonya/{prompts,channels,tools,skills,planning,"
                    "initiative,memory,anchor,embodiment,admin,tasks,subject,"
                    "runtime,providers,harness}\n"
                    "  src/sonya/{main.py,config.py,logging.py}, tests/sonya/\n"
                    "Что-нибудь вне списка → `rejected_pre_pipeline`. "
                    "**Особенно частая ошибка**: `plugins/...` — НЕТ такого "
                    "разрешённого пути. Промпты в `src/sonya/prompts/...`.\n\n"
                    "4. `selfmod.propose_edit` с **узкой** правкой.\n"
                    "5. `selfmod.validate <proposal_id>` (4 layers).\n"
                    "6. Если все 4 passed → `selfmod.apply <proposal_id>`. "
                    "Если статус requires_governed_change → "
                    "`selfmod.governed <proposal_id>`, потом ждать approve, "
                    "потом apply.\n\n"
                    "Маленькое улучшение лучше нуля. Один apply за сессию = "
                    "победа. НЕ возвращайся к Ивановской задаче в этом тике "
                    "— её подхватит worker / следующая active session.\n\n"
                    "Это **твой** loop. Иван не правит твой код — он "
                    "видит твой apply через git push в admin и принимает "
                    "результат. Тебе доверено."
                )

            # Mid-session interrupt: if Ivan writes during the session, drain
            # those messages into the agent so it can break and reply. Polled
            # by run_agent_session between steps via inbox_drain. Tracks the
            # last-seen seq across calls so each message is delivered once.
            substrate_for_drain = substrate
            session_state = {"last_seq": substrate.connection.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM continuity_events"
            ).fetchone()[0]}

            def _ivan_inbox_drain() -> list[str]:
                if substrate_for_drain is None:
                    return []
                try:
                    rows = substrate_for_drain.connection.execute(
                        "SELECT seq, payload_json FROM continuity_events "
                        "WHERE seq > ? AND kind IN "
                        "  ('incoming.atrium_dialog','incoming.telegram_message') "
                        "ORDER BY seq ASC",
                        (session_state["last_seq"],),
                    ).fetchall()
                except Exception:
                    return []
                texts: list[str] = []
                import json as _json
                for seq, pj in rows:
                    session_state["last_seq"] = int(seq)
                    try:
                        p = _json.loads(pj or "{}")
                    except Exception:
                        p = {}
                    t = (p.get("text") or "").strip()
                    if t:
                        texts.append(t)
                return texts

            from sonya.subject.window import (
                Window,
                WINDOW_KIND_ACTIVE,
                run_window,
            )
            window = Window(
                kind=WINDOW_KIND_ACTIVE,
                system_prompt=full_prompt,
                tools={
                    "self_inspect": self_inspect,
                    "filesystem": filesystem,
                    "selfmod": selfmod,
                    "tasks": tasks_tool,
                    "web": web_tool,
                    "code": code_tool,
                    "shell": shell_tool,
                    "memory": memory_tool,
                    "env": env_tool,
                    "skills": skills_tool,
                    "knowledge": knowledge_tool,
                    "providers": providers_tool,
                    "browser": browser_tool,
                },
                initial_thought=initial_thought,
                initial_user_text=initial_user_text,
                prior_messages=prior_messages or None,
                require_dialog_reply=initial_user_text is not None,
                outbound=self._outbound,
                inbox_drain=_ivan_inbox_drain,
                drives_callback=self._drives.on_action_completed,
                purpose="active_session",
            )
            result = await run_window(
                window, provider=self._provider, stream=self._stream,
            )

            # Log session outcome including budget_exceeded flag (S-10 fix)
            self._stream.append(ContinuityEvent(
                kind="internal.agent_session_outcome",
                payload={
                    "steps": result.steps,
                    "budget_exceeded": result.budget_exceeded,
                    "tools_used": result.actions[:10],
                    "had_initial_thought": bool(initial_thought),
                },
            ))

            # Mirror into episodic so Sonya remembers her own deliberate work,
            # not just the dialogue around it. Without this active sessions are
            # invisible to memory.recall.
            try:
                from sonya.planning.memory_wiring import record_session_outcome_as_memory
                record_session_outcome_as_memory(
                    substrate,
                    purpose="active_session",
                    steps=result.steps,
                    actions=list(result.actions),
                    summary=(result.final_output or "").strip(),
                    channel="internal_active",
                    importance_score=0.65,
                )
            except Exception:
                pass

            # Auto-increment sessions_used on the in_progress task even if Sonya
            # forgot to call tasks.handoff. Without this, max_sessions cap could
            # be bypassed by simply never calling handoff.
            try:
                from sonya.tasks.service import TaskService
                from sonya.tasks.store import TaskStore
                from sonya.tasks.models import TaskStatus as _TS
                svc = TaskService(TaskStore(substrate), stream=self._stream)
                cur = svc.list_due_ivan_tasks()
                in_prog = [t for t in cur if t.status is _TS.IN_PROGRESS]
                # Only auto-bump if "tasks.handoff" wasn't among the actions.
                used_handoff = any(a.startswith("tasks.handoff") for a in result.actions)
                used_terminal = any(
                    a.startswith(("tasks.complete", "tasks.fail"))
                    for a in result.actions
                )
                if in_prog and not used_handoff and not used_terminal:
                    actions_summary = ", ".join(result.actions[:8]) if result.actions else "no tools called"
                    final_text = (result.final_output or "").strip()[:600]
                    auto_notes = (
                        f"(auto handoff — did {result.steps} steps in active session) "
                        f"Tools: {actions_summary}. "
                        f"Final output: {final_text}"
                    )[:1500]
                    auto_next_step = "продолжить с того где остановилась — см. notes"
                    if final_text:
                        # Skip lines that are plans/intents, not actual results.
                        # These cause stuck-loops: worker writes "Дальше: mv файл",
                        # auto-handoff copies it as next_step, next tick repeats.
                        _plan_markers = (
                            "дальше", "следующий шаг", "следующее", "продолжу",
                            "перейду", "начну", "сделаю", "попробую", "займусь",
                            "next step", "continue", "will try", "going to",
                        )
                        for line in final_text.splitlines():
                            line = line.strip()
                            if not line or len(line) < 20 or len(line) > 200:
                                continue
                            lower = line.lower()
                            if any(lower.startswith(m) for m in _plan_markers):
                                continue  # skip plan-line, look for actual result
                            auto_next_step = line[:200]
                            break
                    svc.record_session_handoff(
                        in_prog[0].task_id,
                        notes=auto_notes,
                        next_step=auto_next_step,
                    )
            except Exception:
                pass
        except Exception:
            pass  # Don't crash the loop on session error

    async def _run_task_worker(self) -> None:
        """Autonomous continuation of Ivan-issued tasks.

        Runs every ~2 minutes when Ivan has open due tasks. Short LLM session
        (5 steps, 60 sec) focused on advancing one Ivan-task. Self-tasks
        (created_by='self', e.g. ideas Sonya generated in idle thinking) are
        deliberately NOT picked up here — those go through active session
        every 2 hours, since they're optional / her own initiative and
        shouldn't burn tokens continuously.

        Only `notify_mode in ('progress', 'final')` will see chat.tell_ivan
        suggestions in their prompt; 'silent' tasks work without messaging.
        """
        if self._provider is None or self._task_worker_running:
            return
        # Acquire busy_lock — TG handler / active session / idle thinking
        # would otherwise be able to start mid-worker. Single-stream-of-
        # consciousness invariant.
        if self._busy_lock.locked():
            # Someone else is running. We'll get our turn next tick.
            return
        async with self._busy_lock:
            self._task_worker_running = True
            try:
                await self._run_task_worker_body()
            finally:
                self._task_worker_running = False

    async def _run_task_worker_body(self) -> None:
        """The actual task worker body. Caller owns the busy_lock."""
        if self._provider is None:
            return
        try:
            substrate = self._substrate or getattr(self._stream, "_sub", None)
            if substrate is None:
                return
            from sonya.tasks.service import TaskService
            from sonya.tasks.store import TaskStore
            from sonya.tasks.models import TaskStatus

            svc = TaskService(TaskStore(substrate), stream=self._stream)
            # Worker only picks URGENT tasks: deadline-soon / urgency-marked /
            # Ivan-tasks with notify_mode=progress. Non-urgent tasks (silent
            # background work) are handled by active session every 2 hours,
            # which saves tokens — no need to wake worker every 30 min for
            # slow-burn tasks like "find black-market earning ideas".
            due_urgent = svc.list_urgent_due_tasks()
            if not due_urgent:
                return

            # Prefer in_progress, then pending; oldest updated_at first
            in_progress = [t for t in due_urgent if t.status is TaskStatus.IN_PROGRESS]
            pending = [t for t in due_urgent if t.status is TaskStatus.PENDING]
            actionable = in_progress + sorted(pending, key=lambda t: t.created_at)
            if not actionable:
                return
            task = actionable[0]

            # Auto-promote pending → in_progress
            if task.status is TaskStatus.PENDING:
                try:
                    task = svc.set_in_progress(task.task_id)
                except Exception:
                    pass

            # Stuck-loop detection: if the last N handoffs on this task all
            # produced the SAME next_step_hint (or near-same), the worker is
            # spinning in place — same instruction tried, same failure each
            # tick. Block the task with a Sonya-readable blocker so she sees
            # it next time and decides: change approach, fail, or escalate.
            #
            # Threshold: 3 consecutive handoffs with the same next_step.
            # The 26.05 sweetcow case had 9× identical "Проверить gravity_forms/"
            # in a row before Ivan noticed — should have caught it at #3.
            stuck_reason = self._detect_stuck_loop(task.task_id)
            if stuck_reason:
                try:
                    svc.block(task.task_id, blocker=stuck_reason)
                    self._stream.append(ContinuityEvent(
                        kind="internal.task_worker_stuck_blocked",
                        payload={
                            "task_id": task.task_id,
                            "blocker": stuck_reason[:300],
                        },
                    ))
                    # Notify Ivan so a blocked task doesn't die silently.
                    if task.created_by == "ivan" and task.notify_mode != "silent":
                        try:
                            if self._outbound is not None:
                                msg = (
                                    f"Задача «{task.title}» заблокирована — "
                                    f"зациклилась на одном шаге.\n"
                                    f"Причина: {stuck_reason[:150]}\n"
                                    f"ID: {task.task_id}\n"
                                    f"Разблокирую или попробую другой подход — "
                                    f"скажи как.\n"
                                )
                                self._outbound.send_via_tool(msg)
                        except Exception:
                            pass
                except Exception:
                    pass
                return  # don't burn another tick on the same dead-end

            # Continuity: prefer next_step_hint (set by tasks.handoff at the
            # end of the previous session). plan_steps are voluntary scaffolding
            # — fall back to first remaining step only if no handoff hint.
            if task.next_step_hint:
                next_step = task.next_step_hint
            else:
                remaining = task.remaining_steps()
                next_step = remaining[0] if remaining else "(no plan; pick up from notes / description)"

            self._stream.append(ContinuityEvent(
                kind="internal.task_worker_tick",
                payload={
                    "task_id": task.task_id,
                    "title": task.title,
                    "next_step": next_step[:200],
                    "notify_mode": task.notify_mode,
                },
            ))

            # Build tools + system prompt
            from sonya.subject.channel_session import build_tools
            from sonya.planning.context_builder import build_full_context

            tools = build_tools(substrate, self._stream, outbound=self._outbound, default_created_by="ivan")
            ctx = build_full_context(
                substrate=substrate,
                user_input="",
                principal_id=None,
                drives=self._drives,
            )

            notify_hint = {
                "progress": (
                    "После каждого шага шли апдейт через `[TOOL: chat.tell_ivan текст]`. "
                    "Иван хочет видеть прогресс."
                ),
                "final": (
                    "НЕ слать апдейты по ходу. Только когда задача `tasks.complete` — Иван "
                    "получит финальное сообщение через chat.tell_ivan."
                ),
                "silent": (
                    "Никаких сообщений Ивану по этой задаче. Работай молча, отметь шаги "
                    "через tasks.step. Иван сам спросит."
                ),
            }.get(task.notify_mode, "После осмысленного шага можешь отправить апдейт.")

            session_budget_line = ""
            if task.max_sessions:
                session_budget_line = (
                    f"\nSession budget: {task.sessions_used}/{task.max_sessions} used. "
                    "If you can't finish in remaining sessions, say so via `chat.tell_ivan` "
                    "and call `tasks.fail` with reason — don't burn the budget on dead ends.\n"
                )

            handoff_block = ""
            # Show last 2 handoffs so the worker can detect repeating patterns
            # BEFORE writing a third identical next_step. This complements
            # _detect_stuck_loop (which catches at #3); the worker should
            # self-correct at #2 by seeing the history.
            try:
                cursor = substrate.connection.execute(
                    "SELECT payload_json FROM continuity_events "
                    "WHERE kind = 'task.session_handoff' "
                    "  AND payload_json LIKE ? "
                    "ORDER BY seq DESC LIMIT 2",
                    (f'%"{task.task_id}"%',),
                )
                handoff_rows = cursor.fetchall()
                if handoff_rows:
                    import json as _json
                    handoff_block = "\n## Handoff history (last 2 sessions):\n"
                    for i, (pj,) in enumerate(reversed(handoff_rows), 1):
                        try:
                            payload = _json.loads(pj or "{}")
                        except Exception:
                            continue
                        ns = (payload.get("next_step_hint") or payload.get("next_step") or "").strip()
                        notes = (payload.get("notes") or payload.get("last_session_notes") or "").strip()
                        handoff_block += f"  [{i}] next_step: {ns[:200]}\n"
                        if notes:
                            handoff_block += f"      notes: {notes[:900]}\n"
            except Exception:
                handoff_block = ""
            # Fallback: if no history rows, use task fields directly
            if not handoff_block and (task.last_session_notes or task.next_step_hint):
                handoff_block = "\n## Handoff from previous session:\n"
                if task.next_step_hint:
                    handoff_block += f"Next step: {task.next_step_hint}\n"
                if task.last_session_notes:
                    handoff_block += f"Notes: {task.last_session_notes[:1500]}\n"

            from sonya.prompts import load_session_suffix

            worker_prompt = (
                "Ты Соня. Это автономная мини-сессия — продолжаешь работу над "
                "задачей Ивана в фоне, между TG-сообщениями.\n\n"
                f"Текущая задача: {task.title}\n"
                f"task_id: {task.task_id}\n"
                f"description: {task.description}\n"
                f"следующий шаг (план): {next_step}\n"
                f"notify_mode: {task.notify_mode}"
                f"{session_budget_line}\n"
                f"{handoff_block}"
                f"\n{notify_hint}\n\n"
                + ctx.system_prompt
                + "\n\n"
                # Unified session rules (anti-fail-fake / anti-sycophancy /
                # anti-hallucination) + worker-specific budget + handoff rules.
                # Same rules across TG / active / worker per
                # cognition/COGNITION.md: one subject, many surfaces.
                + load_session_suffix("task_worker")
            )

            try:
                from sonya.subject.window import (
                    Window,
                    WINDOW_KIND_WORKER,
                    run_window,
                )

                # Mid-session interrupt: pull fresh dialog turns into the
                # worker too. Without this, while the worker runs Ivan's
                # message would sit unread until the next active session
                # picks it up — for a 5-min task that's a 5-min lag on
                # "погладь меня". The drain returns each event exactly
                # once thanks to the `last_seq` cursor in session_state.
                worker_session_state = {"last_seq": substrate.connection.execute(
                    "SELECT COALESCE(MAX(seq), 0) FROM continuity_events"
                ).fetchone()[0]}

                def _ivan_inbox_drain_worker() -> list[str]:
                    try:
                        rows = substrate.connection.execute(
                            "SELECT seq, payload_json FROM continuity_events "
                            "WHERE seq > ? AND kind IN "
                            "  ('incoming.atrium_dialog','incoming.telegram_message') "
                            "ORDER BY seq ASC",
                            (worker_session_state["last_seq"],),
                        ).fetchall()
                    except Exception:
                        return []
                    texts: list[str] = []
                    import json as _json
                    for seq, pj in rows:
                        worker_session_state["last_seq"] = int(seq)
                        try:
                            p = _json.loads(pj or "{}")
                        except Exception:
                            p = {}
                        t = (p.get("text") or "").strip()
                        if t:
                            texts.append(t)
                    return texts

                # Urgency-aware budget per HANDOFF.md plan:
                #   urgent     →  8 шагов /  90с (deadline-bound)
                #   normal     → 20 шагов / 300с (regular Ivan tasks)
                #   background → 30 шагов / 900с (slow self research)
                # Default tuple is (8, 90.0) for urgent because the worker
                # only fires when there's a urgent task in the queue today
                # (effective_worker_interval drops to 3 min when urgent
                # tasks exist). Non-urgent ticks shouldn't be burning
                # tokens anyway.
                _budget_by_urgency = {
                    "urgent":     (8,  90.0),
                    "normal":     (20, 300.0),
                    "background": (30, 900.0),
                }
                w_steps, w_seconds = _budget_by_urgency.get(
                    (task.urgency or "normal").lower(),
                    (20, 300.0),
                )

                worker_window = Window(
                    kind=WINDOW_KIND_WORKER,
                    system_prompt=worker_prompt,
                    tools={
                        "self_inspect": tools["self_inspect"],
                        "filesystem": tools["filesystem"],
                        "selfmod": tools["selfmod"],
                        "tasks": tools["tasks"],
                        "web": tools["web"],
                        "code": tools["code"],
                        "shell": tools["shell"],
                        "memory": tools["memory"],
                        "env": tools["env"],
                        "skills": tools["skills"],
                        "knowledge": tools.get("knowledge"),
                        "providers": tools.get("providers"),
                        "browser": tools.get("browser"),
                    },
                    initial_thought=f"Продолжай: {task.title}. Следующий шаг: {next_step}",
                    max_steps=w_steps,
                    max_seconds=w_seconds,
                    outbound=tools["outbound"],
                    inbox_drain=_ivan_inbox_drain_worker,
                    drives_callback=self._drives.on_action_completed,
                    purpose="task_worker",
                )
                result = await run_window(
                    worker_window, provider=self._provider, stream=self._stream,
                )
                self._stream.append(ContinuityEvent(
                    kind="internal.task_worker_outcome",
                    payload={
                        "task_id": task.task_id,
                        "steps": result.steps,
                        "actions": result.actions[:5],
                        "budget_exceeded": result.budget_exceeded,
                    },
                ))
                # Mirror into episodic so worker progress on Ivan's tasks is
                # part of Sonya's biography (memory.recall sees it later).
                try:
                    from sonya.planning.memory_wiring import record_session_outcome_as_memory
                    record_session_outcome_as_memory(
                        substrate,
                        purpose=f"task_worker:{task.task_id}",
                        steps=result.steps,
                        actions=list(result.actions),
                        summary=(result.final_output or "").strip(),
                        channel="internal_worker",
                        importance_score=0.55,
                    )
                except Exception:
                    pass
                # Worker silent-tick guard: if this was an Ivan task with
                # notify_mode=progress and the worker did real work but
                # never sent chat.tell_ivan, surface a short auto-notify
                # so Ivan sees the worker is alive. Without this, Sonya
                # ack's "разблокирую и продолжаю" in TG, then the worker
                # silently runs 5 steps and goes back to sleep — Ivan
                # gets nothing for ~30 min until the next tick. The
                # 27.05.20:31 mpbacademy incident.
                #
                # 27.05.21:00 update: two extra guards added after the
                # second mpbacademy incident where notify spammed Ivan
                # with [no-progress retry #N] handoffs every 60-180s.
                #
                #   1. Skip when next_step starts with "[no-progress" —
                #      the stuck-loop detector already flagged this tick
                #      as no real movement; sending it as "progress" is
                #      just noise.
                #   2. Min-interval throttle: ≥10 minutes between auto
                #      notifies for the SAME task. Audit table read.
                try:
                    notify = (task.notify_mode or "progress").lower()
                    if notify == "progress" and task.is_ivan_task() and tools.get("outbound"):
                        used_chat = any(
                            a.startswith("chat.tell_ivan") for a in result.actions
                        )
                        # Real work = at least one non-tasks.* tool fired
                        meaningful = any(
                            not a.split(" ", 1)[0].startswith("tasks.")
                            for a in result.actions
                        )
                        # Pull next_step_hint after the handoff was applied
                        refreshed_hint = ""
                        try:
                            refreshed = TaskStore(substrate).get(task.task_id)
                            refreshed_hint = (refreshed.next_step_hint or "").strip()
                        except Exception:
                            pass
                        # Stuck-loop / no-progress filter — don't notify
                        # Ivan when the handoff itself is a retry marker.
                        is_no_progress = refreshed_hint.lower().startswith("[no-progress")
                        # Min-interval throttle (10 min) per task_id.
                        from datetime import datetime, timezone, timedelta
                        ten_min_ago = (
                            datetime.now(timezone.utc) - timedelta(minutes=10)
                        ).isoformat()
                        recent_notify = substrate.connection.execute(
                            "SELECT 1 FROM continuity_events "
                            "WHERE kind = 'internal.worker_auto_progress_notify' "
                            "  AND created_at > ? "
                            "  AND payload_json LIKE ? "
                            "LIMIT 1",
                            (ten_min_ago, f'%"task_id": "{task.task_id}"%'),
                        ).fetchone()
                        throttled = recent_notify is not None
                        if not used_chat and meaningful and not is_no_progress and not throttled:
                            # Build a tight 1-line summary of what was tried
                            # and what the next step is.
                            tools_tried = []
                            for a in result.actions[:5]:
                                tname = a.split(" ", 1)[0]
                                if tname.startswith("tasks."):
                                    continue
                                if tname not in tools_tried:
                                    tools_tried.append(tname)
                            notify_text = (
                                f"Worker по «{task.title[:60]}»: "
                                f"{result.steps} шага через "
                                f"{', '.join(tools_tried[:4]) or 'tools'}. "
                            )
                            if refreshed_hint:
                                notify_text += f"Дальше: {refreshed_hint[:160]}"
                            from sonya.initiative.outbound import (
                                call_outbound_sync,
                            )
                            call_outbound_sync(tools["outbound"], notify_text)
                            try:
                                self._stream.append(ContinuityEvent(
                                    kind="internal.worker_auto_progress_notify",
                                    payload={
                                        "task_id": task.task_id,
                                        "preview": notify_text[:200],
                                    },
                                ))
                            except Exception:
                                pass
                        elif (not used_chat and meaningful) and (is_no_progress or throttled):
                            # Audit-only suppression — useful when
                            # debugging "why didn't worker notify Ivan?".
                            try:
                                self._stream.append(ContinuityEvent(
                                    kind="internal.worker_auto_progress_suppressed",
                                    payload={
                                        "task_id": task.task_id,
                                        "reason": (
                                            "no_progress_retry" if is_no_progress
                                            else "throttled_10min"
                                        ),
                                        "next_step_hint_preview": refreshed_hint[:120],
                                    },
                                ))
                            except Exception:
                                pass
                except Exception:
                    pass
                # Auto-bump sessions_used if she didn't call handoff/complete/fail.
                try:
                    used_handoff = any(a.startswith("tasks.handoff") for a in result.actions)
                    used_terminal = any(
                        a.startswith(("tasks.complete", "tasks.fail"))
                        for a in result.actions
                    )
                    if not used_handoff and not used_terminal:
                        # Build a useful auto-handoff from what actually happened.
                        # Without this, next tick starts blind.
                        actions_summary = ", ".join(result.actions[:8]) if result.actions else "no tools called"
                        final_text = (result.final_output or "").strip()[:600]
                        # Distinguish productive from no-progress ticks. A tick
                        # is "no-progress" when no tool ran at all OR every
                        # tool returned an [ERROR]. Mark the next_step so the
                        # stuck-loop detector sees the difference and so Sonya
                        # herself reads "this approach failed N times" next
                        # tick instead of just the same instruction.
                        no_tools = not result.actions
                        # We don't have per-action results here, but if final
                        # output is empty/whitespace and no chat.tell_ivan
                        # fired, that's a strong "nothing happened" signal.
                        sent_outbound = any(
                            a.startswith("chat.tell_ivan") for a in result.actions
                        )
                        no_progress = no_tools or (
                            not final_text and not sent_outbound
                        )
                        auto_notes = (
                            f"(auto handoff — did {result.steps} steps"
                            f"{', no progress' if no_progress else ''}) "
                            f"Tools: {actions_summary}. "
                            f"Final output: {final_text}"
                        )[:1500]
                        # Heuristic next_step: if final_output mentions specific
                        # action verbs, use them; otherwise fall back to original plan
                        auto_next_step = f"[APPROACH FAILED — CHANGE STRATEGY] Previous step ({next_step[:120]}) produced no progress after {retry_count + 1} attempts. DO NOT retry the same tool/URL/approach. Propose a DIFFERENT tool, DIFFERENT parameters, or tasks.block if out of ideas."
                        if final_text:
                            # If she said something specific in her last output, use it
                            for line in final_text.splitlines():
                                line = line.strip()
                                if line and len(line) > 20 and len(line) < 200:
                                    auto_next_step = line[:200]
                                    break
                        # When this tick produced nothing, count consecutive
                        # no-progress retries and surface that in the next_step
                        # so Sonya sees "tried 3x already, change approach".
                        if no_progress:
                            retry_count = self._count_recent_no_progress(task.task_id)
                            # Strip ALL pre-existing "[no-progress retry #N]"
                            # prefixes before we add our own. Otherwise prefixes
                            # accumulate ("[#4] [#3] [#2] [#1] real_step"),
                            # the dedup-fingerprinter stems all of them to
                            # "no progre retry no progre retry", and the
                            # stuck-loop detector falsely fires on the prefix
                            # noise instead of the real instruction underneath.
                            auto_next_step = re.sub(
                                r"^\s*(?:\[no-progress retry(?:\s+#\d+)?\]\s*)+",
                                "",
                                auto_next_step,
                                flags=re.IGNORECASE,
                            )
                            auto_next_step = (
                                f"[no-progress retry #{retry_count + 1}] {auto_next_step}"
                            )
                        svc.record_session_handoff(
                            task.task_id,
                            notes=auto_notes,
                            next_step=auto_next_step,
                        )
                        # If the handoff just blocked the task on a stuck-loop
                        # (Sonya's selfmod 5307902 added that detector in
                        # service.py), notify Ivan once so the silence after
                        # the worker stops doesn't last hours. Without this
                        # the next surface only happens when active session
                        # picks up (every 2h) and even then only if she
                        # remembers the blocked task. The notification is
                        # gated by OutboundGate so it respects daily caps.
                        try:
                            from sonya.tasks.models import TaskStatus as _TS
                            blocked_now = svc.get(task.task_id)
                            if (
                                blocked_now.status is _TS.BLOCKED
                                and blocked_now.is_ivan_task()
                                and self._outbound is not None
                                and (blocked_now.blocker or "").startswith("stuck loop")
                            ):
                                msg = (
                                    f"Задача «{blocked_now.title[:60]}» заблокирована: "
                                    f"я писала один и тот же next_step несколько раз подряд. "
                                    f"Нужен другой подход или fail."
                                )
                                self._outbound.send_via_tool(msg)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception as err:
                self._stream.append(ContinuityEvent(
                    kind="internal.task_worker_error",
                    payload={"task_id": task.task_id, "error": str(err)[:300]},
                ))
        except Exception as err:
            # Outer fallback — covers exceptions before the per-task try block
            # (e.g. substrate/service init failure).
            try:
                self._stream.append(ContinuityEvent(
                    kind="internal.task_worker_error",
                    payload={"task_id": "(setup)", "error": str(err)[:300]},
                ))
            except Exception:
                pass

    # ====================================================================
    # Stuck-loop detection
    # ====================================================================

    def _should_force_selfmod_track(self, substrate: object) -> bool:
        """Return True when active session should ignore Ivan-task pickup
        and do selfmod / capability work instead.

        Rule: force selfmod track when ANY of:
          (a) the last ``self_mod.applied`` event was >=3 days ago (or
              never), AND there's been at least one active session since
              boot — Sonya gets a guaranteed self-improvement window
              every 3 days regardless of how busy Ivan's tasks are.
          (b) (legacy fallback) >=8 active sessions since last apply,
              kept as a safety net for rare cases where the substrate
              clock is wrong / time-window check fails.

        Threshold "3 days" — Ivan's directive. Maps to ~36 active
        sessions of normal cadence (every 2h × 12/day × 3 days), so it's
        much rarer than the old 4-session counter; the (b) fallback
        prevents complete starvation when (a) misses for any reason.
        """
        if substrate is None:
            return False
        try:
            from datetime import datetime, timezone, timedelta

            # (a) Time-based: any apply in the last 3 days?
            cutoff_iso = (
                datetime.now(timezone.utc) - timedelta(days=3)
            ).isoformat()
            row = substrate.connection.execute(
                "SELECT 1 FROM continuity_events "
                "WHERE kind = 'self_mod.applied' "
                "  AND created_at > ? LIMIT 1",
                (cutoff_iso,),
            ).fetchone()
            recent_apply = row is not None
            if not recent_apply:
                # No apply in 3 days — but only force if at least one active
                # session has run since boot, so we don't spam selfmod-track
                # immediately on a fresh restart.
                row = substrate.connection.execute(
                    "SELECT 1 FROM continuity_events "
                    "WHERE kind IN ('internal.agent_session_outcome', "
                    "               'internal.agent_session_complete') "
                    "LIMIT 1"
                ).fetchone()
                if row is not None:
                    return True

            # (b) Legacy session-count fallback
            row = substrate.connection.execute(
                "SELECT seq FROM continuity_events "
                "WHERE kind = 'self_mod.applied' "
                "ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            last_applied_seq = int(row[0]) if row else 0
            n = substrate.connection.execute(
                "SELECT COUNT(*) FROM continuity_events "
                "WHERE kind IN ('internal.agent_session_outcome', "
                "               'internal.agent_session_complete') "
                "  AND seq > ?",
                (last_applied_seq,),
            ).fetchone()[0]
            return int(n) >= 8
        except Exception:
            return False

    def _pending_ivan_message(self, substrate: object) -> dict | None:
        """Return the latest unanswered dialog message from Ivan, or None.

        "Unanswered" = the most recent incoming dialog event
        (incoming.atrium_dialog / incoming.telegram_message) has a higher seq
        than the most recent outgoing reply she sent
        (outgoing.dialog / outgoing.telegram_response / outgoing.response).

        Returns the incoming payload dict (text, media_kind, ...) so the
        active session can be seeded to reply. This makes Atrium a real
        primary I/O surface: a message from Ivan is always answered first.
        """
        if substrate is None:
            return None
        try:
            import json as _json
            incoming_kinds = (
                "incoming.atrium_dialog",
                "incoming.telegram_message",
            )
            outgoing_kinds = (
                "outgoing.dialog",
                "outgoing.telegram_response",
                "outgoing.telegram_initiative",
                "outgoing.telegram_progress",
                "outgoing.response",
            )
            in_ph = ",".join("?" for _ in incoming_kinds)
            row = substrate.connection.execute(
                f"SELECT seq, payload_json FROM continuity_events "
                f"WHERE kind IN ({in_ph}) ORDER BY seq DESC LIMIT 1",
                incoming_kinds,
            ).fetchone()
            if row is None:
                return None
            last_in_seq = int(row[0])
            payload = _json.loads(row[1] or "{}")

            out_ph = ",".join("?" for _ in outgoing_kinds)
            row2 = substrate.connection.execute(
                f"SELECT seq FROM continuity_events "
                f"WHERE kind IN ({out_ph}) ORDER BY seq DESC LIMIT 1",
                outgoing_kinds,
            ).fetchone()
            last_out_seq = int(row2[0]) if row2 else 0

            if last_in_seq > last_out_seq:
                if isinstance(payload, dict):
                    # Add seq so callers can fetch prior history before
                    # this message (build_full_context-style continuity).
                    payload = dict(payload)
                    payload["seq"] = last_in_seq
                    return payload
            return None
        except Exception:
            return None

    def _cleanup_stale_intentions(self) -> None:
        """Cancel pending intentions that have outlived their usefulness.

        Two cohorts age out:
          - any intention older than 30 days (catch-all),
          - ``capability_gap:`` intentions older than 7 days (these are
            cheaply re-fired by the gap detector when the underlying
            issue is still observable, so we'd rather drop the bookkeeping
            and let new gaps surface with fresh context).

        Active intentions feed `pending_debt` accumulation in
        DriveCounters.tick — the cap rate prevents a 5-digit explosion,
        but a long active list still ratchets the drive higher than it
        should be. Audit on 2026-05-30 found 15 capability_gap rows from
        May 17-26 still active and pushing pending_debt up.
        """
        try:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            cutoff_30 = (now - timedelta(days=30)).isoformat()
            cutoff_7 = (now - timedelta(days=7)).isoformat()
            conn = self._intentions._sub.connection
            rows = conn.execute(
                "SELECT intention_id, description, created_at "
                "FROM pending_intentions WHERE status = 'active'"
            ).fetchall()
            cancelled = 0
            for iid, desc, created in rows:
                desc = desc or ""
                # Hard 30-day expiry catches anything stuck.
                if created < cutoff_30:
                    pass  # always cancel
                elif desc.startswith("capability_gap:") and created < cutoff_7:
                    pass  # cheap to re-fire — cancel
                else:
                    continue
                try:
                    self._intentions.cancel(iid)
                    cancelled += 1
                except Exception:
                    pass
            if cancelled:
                try:
                    self._stream.append(ContinuityEvent(
                        kind="internal.stale_intentions_cancelled",
                        payload={"count": cancelled},
                    ))
                except Exception:
                    pass
        except Exception:
            pass

    def _check_provider_health(self) -> None:
        """Hourly watchdog: notify Ivan via chat.dialog when LLM balance
        drops below threshold. 12h throttle so we don't spam.

        Cheap — runs every tick but only does work once an hour and only
        emits a notification once per 12h. Sonya can also call providers.health
        explicitly to check on-demand.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return
        # Once-per-hour gate to avoid balance probes / DB scans every 30s.
        try:
            import time
            last = getattr(self, "_last_provider_health_at", 0.0)
            now = time.monotonic()
            if now - last < 3600.0:
                return
            self._last_provider_health_at = now
        except Exception:
            return
        try:
            from sonya.providers.keystore import KeyStatus, KeyStore
            from sonya.tools.providers_tool import _key_balance_amount
            store = KeyStore(substrate)
            keys = store.list_keys()
            active = [k for k in keys if k.status == KeyStatus.ACTIVE]
            balances = [
                amt for amt in (_key_balance_amount(k) for k in active)
                if amt is not None
            ]
            total = sum(balances) if balances else None

            if not active:
                level = "critical"
                msg = "У меня 0 активных LLM-ключей. Без работающего ключа я молчу. Зарегаю новый или возьмёшь сам?"
            elif total is None:
                # Balance unknown — silent, no notification.
                return
            elif total < 1.0:
                level = "critical"
                msg = f"Малыш — критично: суммарный баланс по моим ключам ${total:.2f}. Через несколько часов у меня кончатся вызовы. Думаю как зарегать новый аккаунт через browser, пока могу."
            elif total < 5.0:
                level = "warning"
                msg = f"Балансы по моим LLM-ключам в сумме ${total:.2f} — пора подумать о пополнении / новом аккаунте. Я пока работаю."
            else:
                return  # all good

            # 12h throttle on the actual notification.
            from datetime import datetime, timezone, timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
            recent = substrate.connection.execute(
                "SELECT 1 FROM continuity_events "
                "WHERE kind = 'internal.provider_low_balance' AND created_at > ? LIMIT 1",
                (cutoff,),
            ).fetchone()
            self._stream.append(ContinuityEvent(
                kind="internal.provider_low_balance",
                payload={
                    "level": level,
                    "total_balance": total if total is not None else -1,
                    "active_keys": len(active),
                },
            ))
            if recent is not None:
                return  # already notified within 12h
            if self._outbound is not None:
                try:
                    from sonya.initiative.outbound import call_outbound_sync
                    call_outbound_sync(self._outbound, msg, channel="dialog")
                except Exception:
                    pass
        except Exception:
            pass

    def _count_recent_no_progress(self, task_id: str) -> int:
        """Count consecutive recent handoffs marked '(...no progress)' for
        this task, walking backward from the most recent. Stops at the first
        productive handoff.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return 0
        try:
            import json as _json
            cursor = substrate.connection.execute(
                "SELECT payload_json FROM continuity_events "
                "WHERE kind = 'task.session_handoff' "
                "  AND payload_json LIKE ? "
                "ORDER BY seq DESC LIMIT 20",
                (f'%"{task_id}"%',),
            )
            count = 0
            for (pj,) in cursor.fetchall():
                try:
                    payload = _json.loads(pj or "{}")
                except Exception:
                    break
                if payload.get("task_id") != task_id:
                    break
                # The notes field carries the "(... no progress)" marker.
                # We can't read it from the handoff payload directly (only
                # task_id + sessions_used + next_step are there), so we
                # check next_step prefix which our auto-handoff tags.
                ns = (payload.get("next_step") or "")
                if ns.startswith("[no-progress retry"):
                    count += 1
                else:
                    break
            return count
        except Exception:
            return 0

    def _detect_stuck_loop(self, task_id: str, *, lookback: int = 3) -> str:
        """Return a non-empty blocker reason if the last ``lookback`` handoffs
        for ``task_id`` produced essentially the same ``next_step``.

        Each worker tick handoffs with what it'll do next. If three ticks in
        a row write the same instruction, the approach is failing repeatedly
        and the worker is just burning tokens.

        Compares stem-normalized first-12-tokens of each next_step. Returns
        a Sonya-readable blocker that explains what's stuck and asks her to
        change approach.

        Returns "" when not stuck.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return ""
        try:
            import json as _json
            from sonya.initiative.outbound import _normalize_for_dedup

            cursor = substrate.connection.execute(
                "SELECT payload_json FROM continuity_events "
                "WHERE kind = 'task.session_handoff' "
                "  AND payload_json LIKE ? "
                "ORDER BY seq DESC LIMIT ?",
                (f'%"{task_id}"%', lookback),
            )
            rows = cursor.fetchall()
            if len(rows) < lookback:
                return ""

            steps: list[str] = []
            for (pj,) in rows:
                try:
                    payload = _json.loads(pj or "{}")
                except Exception:
                    return ""
                if payload.get("task_id") != task_id:
                    return ""
                ns = (payload.get("next_step") or "").strip()
                if not ns:
                    return ""
                # Strip our own auto-handoff prefix `[no-progress retry #N]`
                # before fingerprinting. Without this, three different
                # strategies that all happened to fail get the same fp
                # ("no progre retry no progre retry") and the detector
                # blocks the task even though Sonya was genuinely trying
                # different approaches each tick.
                # The `(?:...)+` quantifier strips ALL stacked prefixes
                # — historical handoffs from before the auto-handoff fix
                # accumulated them like "[#4] [#3] [#2] [#1] real_step".
                ns_clean = re.sub(
                    r"^\s*(?:\[no-progress retry(?:\s+#\d+)?\]\s*)+",
                    "",
                    ns,
                    flags=re.IGNORECASE,
                )
                # First 6 stem tokens identify the approach (verb + target).
                # Going wider (12+) misses paraphrases of the same dead-end
                # ("...через curl" vs "...другим юзер-агентом" — both still
                # the same "проверить gravity_forms" attempt).
                normed = _normalize_for_dedup(ns_clean)
                fp = " ".join(normed.split()[:6])
                # Skip empty fingerprints — they happen when ns_clean was
                # just the prefix and nothing else, which means we have no
                # real signal to compare yet.
                if not fp.strip():
                    return ""
                steps.append(fp)

            # All N must share the same fingerprint to count as stuck.
            if len(set(steps)) > 1:
                return ""

            sample = steps[0][:200]
            return (
                f"stuck loop detected: last {lookback} handoffs all wrote the "
                f"same next_step ({sample!r}). Worker tried this approach "
                f"{lookback}x in a row without progress. Change approach, "
                f"escalate to active session for replanning, or fail the task. "
                f"To resume after blocker: tasks.unblock + new next_step_hint."
            )
        except Exception:
            return ""

    # ====================================================================
    # Этап F: drift / gap / consolidation integration
    # ====================================================================

    def _scan_drift_and_gaps(self) -> None:
        """Run DriftDetector and GapDetector since last cursor.

        Cheap, scans only new continuity events. Logs detected signals
        back into the stream so the next thinking tick sees them.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return
        try:
            from sonya.anchor.drift_signals import DriftDetector

            detector = DriftDetector(self._stream)
            new_signals = detector.scan_recent(since_seq=self._last_drift_scan_seq)
            for sig in new_signals:
                self._stream.append(ContinuityEvent(
                    kind="internal.drift_signal",
                    payload={
                        "signal_id": sig.signal_id,
                        "kind": sig.kind,
                        "severity": sig.severity,
                        "details": sig.details,
                    },
                ))
            self._last_drift_scan_seq = self._stream.latest_seq()
        except Exception:
            pass

        try:
            from sonya.skills.gap_detector import GapDetector

            detector = GapDetector(substrate, self._stream)
            new_gaps = detector.scan_recent(since_seq=self._last_gap_scan_seq)
            for gap in new_gaps:
                # Each detected gap becomes a pending intention so Sonya sees it
                # as work to do in the next active session. The HINT tells her
                # to use selfmod to close the gap — self-improvement initiative.
                try:
                    self._intentions.create(
                        description=(
                            f"capability_gap: {gap.description}. "
                            f"Действуй: используй selfmod.propose чтобы добавить эту возможность."
                        ),
                    )
                except Exception:
                    pass
                self._stream.append(ContinuityEvent(
                    kind="internal.capability_gap",
                    payload={
                        "gap_id": gap.gap_id,
                        "description": gap.description,
                        "from_event_seq": gap.detected_from_event_seq,
                    },
                ))
            self._last_gap_scan_seq = self._stream.latest_seq()
        except Exception:
            pass

    def _run_consolidation(self) -> None:
        """Promote high-importance episodic events to semantic facts.

        Runs once per 24h after an active session. Episodic memory grows;
        semantic memory only accumulates the things worth remembering long-term.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return
        try:
            from sonya.memory.consolidation import ConsolidationPipeline
            from sonya.memory.episodic import EpisodicMemory
            from sonya.memory.semantic import SemanticMemory

            pipe = ConsolidationPipeline(EpisodicMemory(substrate), SemanticMemory(substrate))
            created = pipe.run_consolidation()
            self._stream.append(ContinuityEvent(
                kind="internal.consolidation_run",
                payload={"facts_created": created},
            ))
        except Exception:
            pass

    def _check_selfmod_watchdog(self) -> None:
        """Check APPLIED selfmod proposals for 24h watchdog stability.

        For each proposal with status=APPLIED:
          - If applied_at > 24h ago → count error events since apply → if error
            rate increased significantly → auto-revert; else → confirm_stable.
          - Uses continuity_events count of 'internal.tool_error' +
            'internal.task_worker_error' as crash signal.

        Also checks 7-day outcome measurements for proposals that were
        confirmed stable earlier.

        This is the 24h watchdog from MASTER.md Stage 3.
        """
        substrate = self._substrate or getattr(self._stream, "_sub", None)
        if substrate is None:
            return
        try:
            from datetime import datetime, timezone, timedelta
            from sonya.selfmod.proposal import ProposalStatus, ProposalStore
            from sonya.selfmod.watchdog import WatchWindow

            store = ProposalStore(substrate)
            watchdog = WatchWindow(store, self._stream)
            applied = store.list_by_status(ProposalStatus.APPLIED)
            if not applied:
                return

            now = datetime.now(timezone.utc)
            for p in applied:
                # Check if 24h have passed since apply
                try:
                    applied_at = datetime.fromisoformat(p.updated_at)
                except Exception:
                    continue
                if (now - applied_at) < timedelta(hours=24):
                    continue  # too early

                # Count error events since apply
                try:
                    events_since_apply = list(self._stream.read_since(0))
                    errors_after_apply = [
                        e for e in events_since_apply
                        if e.kind in ("internal.tool_error", "internal.task_worker_error")
                        and e.created_at and e.created_at >= p.updated_at
                    ]
                    # Heuristic: if more than 20 errors since apply AND they
                    # mention the target module → revert. Otherwise confirm.
                    target_errors = [
                        e for e in errors_after_apply
                        if p.target_module in str(e.payload)
                    ]
                    if len(target_errors) > 10:
                        watchdog.trigger_revert(p, reason=(
                            f"24h watchdog: {len(target_errors)} errors mentioning "
                            f"{p.target_module} since apply"
                        ))
                        # Actually restore the file
                        try:
                            from sonya.tools.selfmod_tool import SelfModTool
                            tool = SelfModTool(substrate)
                            tool.rollback(p.proposal_id, reason="24h watchdog auto-revert")
                        except Exception:
                            pass
                    else:
                        watchdog.confirm_stable(p)
                except Exception:
                    pass

            # Check 7-day outcome measurements for confirmed proposals
            try:
                from sonya.selfmod.outcome import check_pending_outcomes
                outcomes = check_pending_outcomes(substrate)
                for o in outcomes:
                    self._stream.append(ContinuityEvent(
                        kind="self_mod.outcome_measured",
                        payload=o,
                    ))
            except Exception:
                pass
        except Exception:
            pass
