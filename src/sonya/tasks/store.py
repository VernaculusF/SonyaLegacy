"""TaskStore: persistent CRUD for Task objects."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.state.substrate import Substrate
from sonya.tasks.models import Task, TaskNotFoundError, TaskStatus


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    """SQLite-backed CRUD for tasks. No business logic — that lives in TaskService."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    # ---------- create / read ----------

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
        task_id = f"task-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        steps_json = json.dumps(plan_steps or [], ensure_ascii=False)
        self._sub.connection.execute(
            "INSERT INTO tasks (task_id, title, description, status, principal_id, "
            "parent_task_id, deadline, plan_steps_json, completed_steps_json, "
            "blocker, result, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, '[]', '', '', ?, ?)",
            (
                task_id, title, description, principal_id, parent_task_id,
                deadline, steps_json, now, now,
            ),
        )
        self._sub.connection.commit()
        return self.get(task_id)

    def get(self, task_id: str) -> Task:
        row = self._sub.connection.execute(
            "SELECT task_id, title, description, status, principal_id, parent_task_id, "
            "deadline, plan_steps_json, completed_steps_json, blocker, result, "
            "created_at, updated_at FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise TaskNotFoundError(task_id)
        return _row_to_task(row)

    def list_all(self, *, status: str | None = None, limit: int = 100) -> list[Task]:
        if status is not None:
            cursor = self._sub.connection.execute(
                "SELECT task_id, title, description, status, principal_id, parent_task_id, "
                "deadline, plan_steps_json, completed_steps_json, blocker, result, "
                "created_at, updated_at FROM tasks "
                "WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = self._sub.connection.execute(
                "SELECT task_id, title, description, status, principal_id, parent_task_id, "
                "deadline, plan_steps_json, completed_steps_json, blocker, result, "
                "created_at, updated_at FROM tasks "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        return [_row_to_task(row) for row in cursor.fetchall()]

    def list_open(self) -> list[Task]:
        """Return all tasks not in resolved (done/failed) state."""
        cursor = self._sub.connection.execute(
            "SELECT task_id, title, description, status, principal_id, parent_task_id, "
            "deadline, plan_steps_json, completed_steps_json, blocker, result, "
            "created_at, updated_at FROM tasks "
            "WHERE status IN ('pending','in_progress','blocked') ORDER BY updated_at DESC"
        )
        return [_row_to_task(row) for row in cursor.fetchall()]

    # ---------- update ----------

    def update_status(self, task_id: str, status: TaskStatus) -> Task:
        return self._patch(task_id, {"status": status.value})

    def set_blocker(self, task_id: str, blocker: str) -> Task:
        return self._patch(task_id, {"status": TaskStatus.BLOCKED.value, "blocker": blocker})

    def set_result(self, task_id: str, result: str, status: TaskStatus) -> Task:
        return self._patch(task_id, {"status": status.value, "result": result})

    def replace_plan_steps(self, task_id: str, steps: list[str]) -> Task:
        return self._patch(task_id, {"plan_steps_json": json.dumps(steps, ensure_ascii=False)})

    def append_completed_step(
        self, task_id: str, *, step_idx: int, summary: str
    ) -> Task:
        task = self.get(task_id)
        completed = list(task.completed_steps)
        completed.append({
            "step_idx": step_idx,
            "summary": summary,
            "at": _utc_now_iso(),
        })
        return self._patch(task_id, {"completed_steps_json": json.dumps(completed, ensure_ascii=False)})

    def _patch(self, task_id: str, fields: dict[str, Any]) -> Task:
        if not fields:
            return self.get(task_id)
        # Ensure task exists first.
        self.get(task_id)
        cols = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [_utc_now_iso(), task_id]
        self._sub.connection.execute(
            f"UPDATE tasks SET {cols}, updated_at = ? WHERE task_id = ?",
            params,
        )
        self._sub.connection.commit()
        return self.get(task_id)


def _row_to_task(row) -> Task:
    return Task(
        task_id=row[0],
        title=row[1],
        description=row[2],
        status=TaskStatus(row[3]),
        principal_id=row[4],
        parent_task_id=row[5],
        deadline=row[6],
        plan_steps=json.loads(row[7] or "[]"),
        completed_steps=json.loads(row[8] or "[]"),
        blocker=row[9],
        result=row[10],
        created_at=row[11],
        updated_at=row[12],
    )
