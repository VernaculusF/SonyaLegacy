"""Shared lifecycle control for disposable subagent workers."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any


_RUNNING: dict[str, asyncio.Task[Any]] = {}


def register_subagent_task(subagent_id: str, task: asyncio.Task[Any]) -> None:
    _RUNNING[subagent_id] = task
    task.add_done_callback(lambda _task: _RUNNING.pop(subagent_id, None))


def cancel_subagent(substrate: Any, subagent_id: str, *, reason: str) -> bool:
    row = substrate.connection.execute(
        "SELECT status FROM subagent_tasks WHERE subagent_id = ?",
        (subagent_id,),
    ).fetchone()
    if row is None or row[0] in ("done", "failed", "cancelled"):
        return False
    substrate.connection.execute(
        "UPDATE subagent_tasks SET status = 'cancelled', result = ?, completed_at = ? "
        "WHERE subagent_id = ?",
        (f"[CANCELLED] {reason}", datetime.now(timezone.utc).isoformat(), subagent_id),
    )
    substrate.connection.commit()
    running = _RUNNING.get(subagent_id)
    if running is not None and not running.done():
        running.cancel()
    return True


def subagent_cancel_requested(substrate: Any, subagent_id: str) -> bool:
    row = substrate.connection.execute(
        "SELECT status FROM subagent_tasks WHERE subagent_id = ?",
        (subagent_id,),
    ).fetchone()
    return bool(row and row[0] == "cancelled")
