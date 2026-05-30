"""TaskService: business logic on top of TaskStore.

Enforces transitions and emits continuity events when stream is provided.
"""
from __future__ import annotations

from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.tasks.models import Task, TaskNotFoundError, TaskStatus, TaskTransitionError
from sonya.tasks.store import TaskStore


class TaskService:
    def __init__(
        self,
        store: TaskStore,
        *,
        stream: ContinuityStream | None = None,
    ) -> None:
        self._store = store
        self._stream = stream

    # ---------- create ----------

    def create(
        self,
        *,
        title: str,
        description: str = "",
        principal_id: str | None = None,
        parent_task_id: str | None = None,
        deadline: str | None = None,
        plan_steps: list[str] | None = None,
        created_by: str = "self",
        scheduled_for: str = "",
        recurring_spec: str = "",
        notify_mode: str = "progress",
        max_sessions: int = 0,
        urgency: str | None = None,
    ) -> Task:
        if not title.strip():
            raise ValueError("title cannot be empty")
        if created_by not in ("ivan", "self"):
            raise ValueError(f"created_by must be 'ivan' or 'self', got {created_by!r}")
        if notify_mode not in ("progress", "final", "silent"):
            raise ValueError(f"notify_mode must be progress/final/silent, got {notify_mode!r}")
        if max_sessions < 0:
            raise ValueError("max_sessions cannot be negative (0 = unlimited)")
        # Sane default for ivan-tasks: cap unlimited budgets at 20 sessions.
        if max_sessions == 0 and created_by == "ivan":
            max_sessions = 20
        # Resolve urgency. Ivan-tasks default to 'normal'; self-tasks default
        # to 'background' (slow burn — picked up by active session, not by the
        # 3-min worker that would burn tokens on her own recreational ideas).
        # Explicit urgency arg wins.
        if urgency is None:
            urgency = "normal" if created_by == "ivan" else "background"
        if urgency not in ("urgent", "normal", "background"):
            raise ValueError(f"urgency must be urgent|normal|background, got {urgency!r}")
        task = self._store.create(
            title=title,
            description=description,
            principal_id=principal_id,
            parent_task_id=parent_task_id,
            deadline=deadline,
            plan_steps=plan_steps,
            created_by=created_by,
            scheduled_for=scheduled_for,
            recurring_spec=recurring_spec,
            notify_mode=notify_mode,
            max_sessions=max_sessions,
            urgency=urgency,
        )
        self._emit("task.created", task, extra={
            "title": task.title,
            "created_by": created_by,
            "scheduled_for": scheduled_for,
            "notify_mode": notify_mode,
            "max_sessions": max_sessions,
            "urgency": urgency,
        })
        return task

    def record_session_handoff(
        self,
        task_id: str,
        *,
        notes: str = "",
        next_step: str = "",
    ) -> Task:
        """End-of-session handoff: bump sessions_used + persist notes/next_step.

        Auto-fails the task if max_sessions reached.
        """
        task = self._store.increment_sessions_used(task_id)
        if notes or next_step:
            task = self._store.set_session_handoff(task_id, notes=notes, next_step=next_step)

        # --- stuck-loop early detection ---
        # Compare this next_step against the last 5 handoffs. If the same
        # instruction appears 2+ times (including this one), the worker is
        # spinning in place. Block immediately — don't wait for the
        # internal_loop detector which needs 3 ticks and burns extra sessions.
        if next_step and not task.is_resolved():
            recent = self._store.get_last_handoffs(task_id, n=5)
            # Count how many recent handoffs have the same next_step as this one.
            # Use stem-normalized first-6-tokens for fuzzy matching (same logic
            # as _detect_stuck_loop in internal_loop.py).
            import re as _re
            def _stem(s: str) -> str:
                s = _re.sub(r"^\s*(?:\[no-progress retry(?:\s+#\d+)?\]\s*)+", "", s, flags=_re.IGNORECASE)
                s = _re.sub(r"[^a-zа-яё0-9]+", " ", s.lower().strip())
                tokens = s.split()[:6]
                return " ".join(tokens)
            this_stem = _stem(next_step)
            repeat_count = sum(1 for h in recent if _stem(h) == this_stem)
            # +1 for this handoff itself (not yet in continuity_events, but
            # it's being written right now). If we have 2+ total, block.
            if repeat_count >= 1:  # 1 in history + this one = 2 total
                task = self._store.increment_stuck_loop_count(task_id)
                blocker = (
                    f"stuck loop detected: last {repeat_count + 1} handoffs all wrote the "
                    f"same next_step ('{next_step[:120]}'). Worker tried this approach "
                    f"{repeat_count + 1}x in a row without progress. Change approach "
                    f"or fail the task."
                )
                task = self._store.set_blocker(task_id, blocker)
                self._emit("task.stuck_loop_blocked", task, extra={
                    "blocker": blocker[:200],
                    "repeat_count": repeat_count + 1,
                    "next_step": next_step[:200],
                })
                return task

        if task.session_budget_exhausted() and task.status not in (TaskStatus.DONE, TaskStatus.FAILED):
            failed = self._store.set_result(
                task_id,
                f"session budget exhausted ({task.sessions_used}/{task.max_sessions}); "
                f"last_notes: {task.last_session_notes[:300]}",
                TaskStatus.FAILED,
            )
            self._emit("task.session_budget_exhausted", failed, extra={
                "sessions_used": failed.sessions_used,
                "max_sessions": failed.max_sessions,
            })
            return failed
        self._emit("task.session_handoff", task, extra={
            "sessions_used": task.sessions_used,
            "max_sessions": task.max_sessions,
            "next_step": next_step[:200],
        })
        return task

    # ---------- pickup / pause ----------

    def set_in_progress(self, task_id: str) -> Task:
        task = self._store.get(task_id)
        if task.status is TaskStatus.DONE or task.status is TaskStatus.FAILED:
            raise TaskTransitionError(
                f"task {task_id} is {task.status.value}; cannot resume"
            )
        if task.status is TaskStatus.IN_PROGRESS:
            return task
        updated = self._store.update_status(task_id, TaskStatus.IN_PROGRESS)
        self._emit("task.picked_up", updated)
        return updated

    def pause(self, task_id: str) -> Task:
        """Move task → PAUSED. Resumable via unblock/resume.

        v23: previously routed to PENDING (legacy); now uses the dedicated
        PAUSED status so paused tasks are visible separately and pick_next
        skips them (only pending/in_progress get auto-resumed).
        """
        task = self._store.get(task_id)
        if task.status in (TaskStatus.DONE, TaskStatus.FAILED):
            return task  # idempotent on terminal
        if task.status is TaskStatus.PAUSED:
            return task
        updated = self._store.update_status(task_id, TaskStatus.PAUSED)
        self._emit("task.paused", updated)
        return updated

    def resume(self, task_id: str) -> Task:
        """Move PAUSED task back to IN_PROGRESS."""
        task = self._store.get(task_id)
        if task.status is not TaskStatus.PAUSED:
            return task
        updated = self._store.update_status(task_id, TaskStatus.IN_PROGRESS)
        self._emit("task.resumed", updated)
        return updated

    # ---------- planning ----------

    def set_plan(self, task_id: str, steps: list[str]) -> Task:
        if not steps:
            raise ValueError("plan must have at least one step")
        updated = self._store.replace_plan_steps(task_id, steps)
        self._emit("task.plan_set", updated, extra={"step_count": len(steps)})
        return updated

    def mark_step_done(self, task_id: str, step_idx: int, summary: str) -> Task:
        task = self._store.get(task_id)
        if step_idx < 0 or step_idx >= len(task.plan_steps):
            raise ValueError(
                f"step_idx {step_idx} out of range (task has {len(task.plan_steps)} steps)"
            )
        if any(c.get("step_idx") == step_idx for c in task.completed_steps):
            return task  # idempotent
        updated = self._store.append_completed_step(
            task_id, step_idx=step_idx, summary=summary
        )
        self._emit(
            "task.step_done",
            updated,
            extra={"step_idx": step_idx, "summary": summary[:200]},
        )
        return updated

    # ---------- terminal ----------

    def complete(self, task_id: str, result: str = "") -> Task:
        task = self._store.get(task_id)
        if task.is_resolved():
            raise TaskTransitionError(
                f"task {task_id} already {task.status.value}"
            )
        updated = self._store.set_result(task_id, result, TaskStatus.DONE)
        self._emit("task.completed", updated, extra={"result": result[:300]})
        return updated

    def fail(self, task_id: str, reason: str) -> Task:
        task = self._store.get(task_id)
        if task.is_resolved():
            raise TaskTransitionError(
                f"task {task_id} already {task.status.value}"
            )
        updated = self._store.set_result(task_id, reason, TaskStatus.FAILED)
        self._emit("task.failed", updated, extra={"reason": reason[:300]})
        return updated

    def block(self, task_id: str, blocker: str) -> Task:
        task = self._store.get(task_id)
        if task.is_resolved():
            raise TaskTransitionError(
                f"task {task_id} already {task.status.value}; cannot block"
            )
        updated = self._store.set_blocker(task_id, blocker)
        self._emit("task.blocked", updated, extra={"blocker": blocker[:200]})
        return updated

    def unblock(self, task_id: str) -> Task:
        task = self._store.get(task_id)
        if task.status is not TaskStatus.BLOCKED:
            return task
        updated = self._store.update_status(task_id, TaskStatus.IN_PROGRESS)
        self._emit("task.unblocked", updated)
        return updated

    # ---------- queries ----------

    def get(self, task_id: str) -> Task:
        return self._store.get(task_id)

    def list(self, *, status: str | None = None, limit: int = 50) -> list[Task]:
        return self._store.list_all(status=status, limit=limit)

    def list_open(self) -> list[Task]:
        return self._store.list_open()

    def list_due_ivan_tasks(self) -> list[Task]:
        """Ivan-issued tasks that are open AND scheduled_for <= now."""
        return self._store.list_due_ivan_tasks()

    def list_urgent_due_tasks(self) -> list[Task]:
        """Tasks the task_worker should pick up between active sessions."""
        return self._store.list_urgent_due_tasks()

    def pick_next(self) -> Task | None:
        """Pick the next task to work on:

        1. Any task currently in_progress (resume it).
        2. Otherwise the oldest pending task.
        Returns None if all open tasks are blocked or there are none.
        """
        open_tasks = self._store.list_open()
        in_progress = [t for t in open_tasks if t.status is TaskStatus.IN_PROGRESS]
        if in_progress:
            # Most recently updated in_progress task wins (single-stream mental model).
            return in_progress[0]
        pending = sorted(
            (t for t in open_tasks if t.status is TaskStatus.PENDING),
            key=lambda t: t.created_at,
        )
        if pending:
            return pending[0]
        return None

    # ---------- internals ----------

    def _emit(self, kind: str, task: Task, *, extra: dict | None = None) -> None:
        if self._stream is None:
            return
        payload: dict = {
            "task_id": task.task_id,
            "status": task.status.value,
        }
        if extra:
            payload.update(extra)
        try:
            self._stream.append(ContinuityEvent(
                kind=kind,
                principal_id=task.principal_id,
                payload=payload,
            ))
        except Exception:
            pass
