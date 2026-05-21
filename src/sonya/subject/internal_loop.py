from __future__ import annotations

import asyncio
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
        idle_interval_seconds: float = 300.0,
        tick_interval_seconds: float = 10.0,
        active_interval_seconds: float = 3600.0,
        task_worker_interval_seconds: float = 120.0,
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

            # Task worker: if there's an in_progress task and worker is due, run
            # a short continuation pass. Independent of active_session — fires
            # every ~2 minutes when work exists.
            worker_elapsed = now - self._last_task_worker_at
            if (
                worker_elapsed >= self._task_worker_interval
                and not self._task_worker_running
                and self._provider is not None
                and not should_active   # avoid double-running with active session
                and not self._busy_lock.locked()  # don't fire while TG / idle / active is busy
            ):
                self._last_task_worker_at = now
                # Run worker in background so the loop tick stays cheap.
                asyncio.create_task(self._run_task_worker())

            if should_active:
                async with self._busy_lock:
                    await self._run_active_session()
                self._last_active_session = now
                # Этап F: consolidation runs after active sessions, but capped to once/24h
                if now - self._last_consolidation_at >= self._consolidation_interval:
                    self._run_consolidation()
                    self._last_consolidation_at = now
            elif should_think:
                if self._provider is not None:
                    # Idle thinking: only if not already busy with TG/active/worker.
                    if not self._busy_lock.locked():
                        async with self._busy_lock:
                            await self._emit_cognitive_events_async(crossed, idle_triggered, overdue_ids)
                else:
                    self._emit_cognitive_events_sync_fallback(crossed, idle_triggered, overdue_ids)
                if idle_triggered:
                    self._last_external_event = now  # reset idle timer

            # Этап F: drift + gap detection every tick (cheap — scans since last seq)
            self._scan_drift_and_gaps()

            # Selfmod watchdog: check APPLIED proposals older than 24h.
            # Confirm stable or auto-revert based on error count delta.
            self._check_selfmod_watchdog()

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
        """
        if self._provider is None:
            return ""
        triggers = payload.get("triggers", [])
        counters = payload.get("counters", {})

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
                if self._thinking_prompt:
                    system_content = self._thinking_prompt + "\n\n" + system_content
                messages = [
                    {"role": "system", "content": system_content},
                    *ctx.session_messages,
                    {"role": "user", "content": ctx.user_input},
                ]
                return await self._provider.complete_text(messages, purpose="idle_thinking")
            except Exception:
                pass

        # Fallback path (no substrate)
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
            return await self._provider.complete_text(messages, purpose="idle_thinking")
        except Exception:
            return ""

    async def _run_active_session(self) -> None:
        """Run an agent session with tools (active mode)."""
        if self._provider is None:
            return
        try:
            from sonya.subject.agent_session import run_agent_session
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
                ctx = build_full_context(
                    substrate=substrate,
                    user_input="",  # filled by initial_thought instead
                    principal_id=None,
                    drives=self._drives,
                )
                # Stack: thinking-mode prefix → full context system block → TOOL_DESCRIPTIONS
                # (TOOL_DESCRIPTIONS is appended by run_agent_session itself)
                full_prompt = prompt + "\n\n" + ctx.system_prompt
            except Exception:
                full_prompt = prompt

            # Active task pickup (Этап C): if there's an in_progress or pending task,
            # surface it as the seed for this session. Single-stream model — one task
            # at a time. Sonya can use [TOOL: tasks.pick] explicitly too, but this
            # gives her the right context immediately.
            initial_thought = ""
            try:
                from sonya.tasks.service import TaskService
                from sonya.tasks.store import TaskStore
                svc = TaskService(TaskStore(substrate), stream=self._stream)
                next_task = svc.pick_next()
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
                try:
                    from sonya.selfmod.proposal import ProposalStore, ProposalStatus
                    prop_store = ProposalStore(substrate)
                    pending_proposals = [
                        p for p in prop_store.list_all()
                        if p.status in (ProposalStatus.PROPOSED, ProposalStatus.APPROVED)
                    ]
                    if pending_proposals:
                        p = pending_proposals[0]
                        if p.status == ProposalStatus.PROPOSED:
                            initial_thought = (
                                f"У тебя есть selfmod proposal ожидающий валидации:\n"
                                f"  proposal_id: {p.proposal_id}\n"
                                f"  target: {p.target_module}\n"
                                f"  summary: {p.change_summary[:200]}\n\n"
                                f"Прогони полный цикл: `selfmod.validate {p.proposal_id}` → "
                                f"если прошёл → `selfmod.apply {p.proposal_id}`. "
                                f"Если не прошёл — исправь и propose заново."
                            )
                        elif p.status == ProposalStatus.APPROVED:
                            initial_thought = (
                                f"У тебя есть APPROVED selfmod proposal готовый к применению:\n"
                                f"  proposal_id: {p.proposal_id}\n"
                                f"  target: {p.target_module}\n"
                                f"  summary: {p.change_summary[:200]}\n\n"
                                f"Примени его: `selfmod.apply {p.proposal_id}`"
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

            result = await run_agent_session(
                provider=self._provider,
                stream=self._stream,
                self_inspect=self_inspect,
                filesystem=filesystem,
                selfmod=selfmod,
                tasks=tasks_tool,
                web=web_tool,
                code=code_tool,
                shell=shell_tool,
                memory=memory_tool,
                env=env_tool,
                skills=skills_tool,
                outbound=self._outbound,
                system_prompt=full_prompt,
                initial_thought=initial_thought,
                max_steps=30,
                max_seconds=1800.0,  # 30 min hard cap on a single active session
                purpose="active_session",
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
                        for line in final_text.splitlines():
                            line = line.strip()
                            if line and len(line) > 20 and len(line) < 200:
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
            due_ivan = svc.list_due_ivan_tasks()
            if not due_ivan:
                return

            # Prefer in_progress, then pending; oldest updated_at first
            in_progress = [t for t in due_ivan if t.status is TaskStatus.IN_PROGRESS]
            pending = [t for t in due_ivan if t.status is TaskStatus.PENDING]
            actionable = in_progress + sorted(pending, key=lambda t: t.created_at)
            if not actionable:
                # Only blocked / non-actionable tasks left for Ivan. Worker
                # has nothing to advance. Return silently — no error.
                return
            task = actionable[0]

            # Auto-promote pending → in_progress
            if task.status is TaskStatus.PENDING:
                try:
                    task = svc.set_in_progress(task.task_id)
                except Exception:
                    pass

            remaining = task.remaining_steps()
            next_step = remaining[0] if remaining else "(no plan, just continue)"

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
            from sonya.subject.agent_session import run_agent_session
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
            if task.last_session_notes or task.next_step_hint:
                handoff_block = "\n## Handoff from previous session:\n"
                if task.next_step_hint:
                    handoff_block += f"Next step: {task.next_step_hint}\n"
                if task.last_session_notes:
                    handoff_block += f"Notes: {task.last_session_notes[:1500]}\n"

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
                "Что делать в этом тике:\n"
                "- Сделай 1-2 шага по этой задаче через tools\n"
                "- Когда закончил шаг — `[TOOL: tasks.step]` с JSON\n"
                "- Если задача done — `[TOOL: tasks.complete]` JSON и финальный chat.tell_ivan если notify_mode != silent\n"
                "- Если ждёшь approval/Ивана — `[TOOL: tasks.block]` JSON и закрывайся\n"
                "- Если задача оказалась бессмысленной — `[TOOL: tasks.fail]`\n"
                "- Если просто хочешь подождать — `[DONE]` (через ~2 минуты я снова запущу)\n\n"
                "**ВАЖНО**: ПЕРЕД `[DONE]` (если не вызвала complete/fail/block) — обязательно "
                "`[TOOL: tasks.handoff]` с notes и next_step. "
                "Без этого следующий тик начнёт с нуля и не будет знать где ты остановилась.\n\n"
                "У тебя 5 шагов и 60 секунд. Не торопись.\n\n"
                + ctx.system_prompt
            )

            try:
                result = await run_agent_session(
                    provider=self._provider,
                    stream=self._stream,
                    self_inspect=tools["self_inspect"],
                    filesystem=tools["filesystem"],
                    selfmod=tools["selfmod"],
                    tasks=tools["tasks"],
                    web=tools["web"],
                    code=tools["code"],
                    shell=tools["shell"],
                    memory=tools["memory"],
                    env=tools["env"],
                    skills=tools["skills"],
                    outbound=tools["outbound"],
                    system_prompt=worker_prompt,
                    initial_thought=f"Продолжай: {task.title}. Следующий шаг: {next_step}",
                    max_steps=5,
                    max_seconds=60.0,
                    purpose="task_worker",
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
                        auto_notes = (
                            f"(auto handoff — did {result.steps} steps) "
                            f"Tools: {actions_summary}. "
                            f"Final output: {final_text}"
                        )[:1500]
                        # Heuristic next_step: if final_output mentions specific
                        # action verbs, use them; otherwise fall back to original plan
                        auto_next_step = next_step  # use the previous next_step as continuation
                        if final_text:
                            # If she said something specific in her last output, use it
                            for line in final_text.splitlines():
                                line = line.strip()
                                if line and len(line) > 20 and len(line) < 200:
                                    auto_next_step = line[:200]
                                    break
                        svc.record_session_handoff(
                            task.task_id,
                            notes=auto_notes,
                            next_step=auto_next_step,
                        )
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

        This is the 24h watchdog from PATH_TO_AGI Stage 3.
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
