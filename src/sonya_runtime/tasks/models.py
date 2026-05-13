from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


TaskStatus = Literal["pending", "running", "done", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    kind: str
    goal: str
    context_summary: str
    source_message: str
    status: TaskStatus
    priority: int
    created_at: str
    updated_at: str
    requested_by_principal: str
    origin_channel: str
    origin_chat_id: str
    result_summary: str = ""
    result_payload: dict[str, Any] = field(default_factory=dict)
    error_text: str = ""
    claimed_actions: tuple[str, ...] = field(default_factory=tuple)
    followup_required: bool = False
    followup_prompt: str = ""
    worker_id: str = ""
    suggested_steps: tuple[str, ...] = field(default_factory=tuple)


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
