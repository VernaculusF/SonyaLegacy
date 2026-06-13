"""WorkItem domain models.

Replaces the old Task and Goal models with a unified lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WorkItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"
    ARCHIVED = "archived"
    ABANDONED = "abandoned"


class WorkItemUrgency(str, Enum):
    """How fast the system reacts to this item between sessions."""
    URGENT = "urgent"
    NORMAL = "normal"
    BACKGROUND = "background"


class WorkItemNotFoundError(KeyError):
    """Raised when an item_id is not found in the store."""


class WorkItemTransitionError(RuntimeError):
    """Raised when a status transition is illegal."""


@dataclass(frozen=True, slots=True)
class WorkItem:
    item_id: str
    item_type: str = "task"            # 'task' | 'goal' | 'project'
    title: str = ""
    description: str = ""
    status: WorkItemStatus = WorkItemStatus.PENDING
    owner_principal_id: str | None = None
    origin: str = "self"               # 'ivan' | 'self' | 'external'
    parent_item_id: str | None = None
    deadline: str | None = None
    
    dependencies_json: list[str] = field(default_factory=list)
    progress_json: list[dict] = field(default_factory=list)
    context_anchors_json: list[str] = field(default_factory=list)
    validation_evidence_json: list[str] = field(default_factory=list)
    
    urgency: str = "normal"
    max_sessions: int = 0
    sessions_used: int = 0
    last_session_notes: str = ""
    next_step_hint: str = ""
    stuck_loop_count: int = 0
    archive_manifest: str = "{}"
    archive_checksum: str = ""
    
    created_at: str = ""
    updated_at: str = ""
    last_activity_at: str = ""

    def is_open(self) -> bool:
        return self.status in {WorkItemStatus.PENDING, WorkItemStatus.IN_PROGRESS, WorkItemStatus.BLOCKED, WorkItemStatus.PAUSED}

    def is_resolved(self) -> bool:
        return self.status in {WorkItemStatus.DONE, WorkItemStatus.FAILED, WorkItemStatus.ARCHIVED}

    def is_urgent(self) -> bool:
        if self.urgency == WorkItemUrgency.URGENT.value:
            return True
        if self.urgency == WorkItemUrgency.BACKGROUND.value:
            return False
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
        if self.origin == "ivan":
            return True
        return False

    def is_background(self) -> bool:
        return self.urgency == WorkItemUrgency.BACKGROUND.value

    def session_budget_exhausted(self) -> bool:
        return self.max_sessions > 0 and self.sessions_used >= self.max_sessions
