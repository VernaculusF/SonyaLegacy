"""Task domain models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


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

    def is_open(self) -> bool:
        return self.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED}

    def is_resolved(self) -> bool:
        return self.status in {TaskStatus.DONE, TaskStatus.FAILED}

    def remaining_steps(self) -> list[str]:
        done_idx = {entry.get("step_idx") for entry in self.completed_steps}
        return [step for i, step in enumerate(self.plan_steps) if i not in done_idx]
