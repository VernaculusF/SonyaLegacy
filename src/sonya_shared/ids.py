from __future__ import annotations

from uuid import uuid4


def new_task_id() -> str:
    return f"task-{uuid4().hex}"
