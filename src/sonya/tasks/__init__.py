"""Task runtime — long-running multi-session work.

A Task survives across active sessions and restarts. Sonya can:
- create a task with title + description
- break it into plan_steps
- mark steps done one at a time across sessions
- block on Ivan / external dependency
- fail/complete with result

See: docs/MASTER.md task runtime section.
"""
from __future__ import annotations

from sonya.tasks.models import Task, TaskStatus, TaskNotFoundError
from sonya.tasks.store import TaskStore
from sonya.tasks.service import TaskService

__all__ = [
    "Task",
    "TaskStatus",
    "TaskNotFoundError",
    "TaskStore",
    "TaskService",
]
