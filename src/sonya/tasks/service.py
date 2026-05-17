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
    ) -> Task:
        if not title.strip():
            raise ValueError("title cannot be empty")
        task = self._store.create(
            title=title,
            description=description,
            principal_id=principal_id,
            parent_task_id=parent_task_id,
            deadline=deadline,
            plan_steps=plan_steps,
        )
        self._emit("task.created", task, extra={"title": task.title})
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
        """Move from in_progress back to pending (e.g. session ended without completion)."""
        task = self._store.get(task_id)
        if task.status is not TaskStatus.IN_PROGRESS:
            return task
        updated = self._store.update_status(task_id, TaskStatus.PENDING)
        self._emit("task.paused", updated)
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
