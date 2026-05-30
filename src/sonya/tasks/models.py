"""Task domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class TaskUrgency(str, Enum):
    """How fast the system reacts to this task between sessions.

    URGENT     — wake up every 3 min, 8 ReAct steps / 90 s budget per tick.
                 Use for deadline-bound or "Ivan is watching" work.
    NORMAL     — picked up by active session every 2h, 20 steps / 5 min.
                 Default for typical Ivan tasks.
    BACKGROUND — picked up only when active session has nothing else, 30 steps
                 / 15 min. Long-running research / ideas Sonya generated herself.

    Urgency is a soft signal — Task.is_urgent() (legacy) still computes it
    heuristically when the field is missing on old tasks.
    """
    URGENT = "urgent"
    NORMAL = "normal"
    BACKGROUND = "background"


class TaskNotFoundError(KeyError):
    """Raised when a task_id is not found in the store."""


class TaskTransitionError(RuntimeError):
    """Raised when a task transition is illegal (e.g. completing a done task)."""


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    principal_id: str | None = None
    parent_task_id: str | None = None
    deadline: str | None = None
    plan_steps: list[str] = field(default_factory=list)
    completed_steps: list[dict] = field(default_factory=list)
    blocker: str = ""
    result: str = ""
    created_at: str = ""
    updated_at: str = ""
    # v9 additions
    created_by: str = "self"          # 'ivan' or 'self'
    scheduled_for: str = ""           # ISO; empty = run immediately
    recurring_spec: str = ""          # JSON; empty = one-off
    notify_mode: str = "progress"     # 'progress' | 'final' | 'silent'
    # v12 additions: session budget + cross-session continuity
    max_sessions: int = 0              # 0 = unlimited
    sessions_used: int = 0
    last_session_notes: str = ""       # model writes summary at end of each session
    next_step_hint: str = ""           # one-line "where to start next time"
    stuck_loop_count: int = 0          # incremented when next_step repeats; reset on change
    # v23 (2026-05-30): explicit urgency typed field. Heuristic legacy
    # is_urgent() still works when column not populated. Stored as string.
    urgency: str = "normal"            # 'urgent' | 'normal' | 'background'

    def is_open(self) -> bool:
        return self.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.PAUSED}

    def is_resolved(self) -> bool:
        return self.status in {TaskStatus.DONE, TaskStatus.FAILED}

    def remaining_steps(self) -> list[str]:
        done_idx = {entry.get("step_idx") for entry in self.completed_steps}
        return [step for i, step in enumerate(self.plan_steps) if i not in done_idx]

    def is_due(self) -> bool:
        """Whether this task is ready to start now (scheduled_for <= now)."""
        if not self.scheduled_for:
            return True
        try:
            from datetime import datetime, timezone
            sched = datetime.fromisoformat(self.scheduled_for.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) >= sched
        except Exception:
            return True

    def is_ivan_task(self) -> bool:
        return self.created_by == "ivan"

    def is_urgent(self) -> bool:
        """Should the task_worker process this task between active sessions?

        v23: explicit `urgency` field takes precedence. Heuristic fallback
        kept so old rows (no field) still classify reasonably.
        """
        # 1. Explicit field (new tasks set this; old rows default to 'normal')
        if self.urgency == TaskUrgency.URGENT.value:
            return True
        if self.urgency == TaskUrgency.BACKGROUND.value:
            return False
        # 2. Legacy heuristic — old rows without urgency
        if self.deadline:
            try:
                from datetime import datetime, timezone, timedelta
                dl = datetime.fromisoformat(self.deadline.replace("Z", "+00:00"))
                if dl - datetime.now(timezone.utc) <= timedelta(hours=6):
                    return True
            except Exception:
                pass
        haystack = f"{self.title} {self.description}".lower()
        urgent_markers = ("срочно", "urgent", "asap", "немедленно", "быстро")
        if any(m in haystack for m in urgent_markers):
            return True
        if self.is_ivan_task() and self.notify_mode == "progress":
            return True
        return False

    def is_background(self) -> bool:
        """True for slow self-tasks that should only run when nothing else is queued."""
        return self.urgency == TaskUrgency.BACKGROUND.value

    def session_budget_exhausted(self) -> bool:
        """True if max_sessions > 0 and we've burned them all."""
        return self.max_sessions > 0 and self.sessions_used >= self.max_sessions
