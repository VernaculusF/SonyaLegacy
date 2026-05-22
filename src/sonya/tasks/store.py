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
        created_by: str = "self",
        scheduled_for: str = "",
        recurring_spec: str = "",
        notify_mode: str = "progress",
        max_sessions: int = 0,
    ) -> Task:
        task_id = f"task-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        steps_json = json.dumps(plan_steps or [], ensure_ascii=False)
        self._sub.connection.execute(
            "INSERT INTO tasks (task_id, title, description, status, principal_id, "
            "parent_task_id, deadline, plan_steps_json, completed_steps_json, "
            "blocker, result, created_at, updated_at, "
            "created_by, scheduled_for, recurring_spec, notify_mode, "
            "max_sessions, sessions_used, last_session_notes, next_step_hint) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, '[]', '', '', ?, ?, "
            "?, ?, ?, ?, ?, 0, '', '')",
            (
                task_id, title, description, principal_id, parent_task_id,
                deadline, steps_json, now, now,
                created_by, scheduled_for, recurring_spec, notify_mode,
                int(max_sessions or 0),
            ),
        )
        self._sub.connection.commit()
        return self.get(task_id)  # type: ignore[return-value]

    def get(self, task_id: str) -> Task:
        row = self._sub.connection.execute(
            "SELECT task_id, title, description, status, principal_id, parent_task_id, "
            "deadline, plan_steps_json, completed_steps_json, blocker, result, "
            "created_at, updated_at, created_by, scheduled_for, recurring_spec, notify_mode, "
            "max_sessions, sessions_used, last_session_notes, next_step_hint "
            "FROM tasks WHERE task_id = ?",
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
                "created_at, updated_at, created_by, scheduled_for, recurring_spec, notify_mode, "
                "max_sessions, sessions_used, last_session_notes, next_step_hint "
                "FROM tasks WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = self._sub.connection.execute(
                "SELECT task_id, title, description, status, principal_id, parent_task_id, "
                "deadline, plan_steps_json, completed_steps_json, blocker, result, "
                "created_at, updated_at, created_by, scheduled_for, recurring_spec, notify_mode, "
                "max_sessions, sessions_used, last_session_notes, next_step_hint "
                "FROM tasks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        return [_row_to_task(row) for row in cursor.fetchall()]

    def list_open(self) -> list[Task]:
        """Return all tasks not in resolved (done/failed) state."""
        cursor = self._sub.connection.execute(
            "SELECT task_id, title, description, status, principal_id, parent_task_id, "
            "deadline, plan_steps_json, completed_steps_json, blocker, result, "
            "created_at, updated_at, created_by, scheduled_for, recurring_spec, notify_mode, "
            "max_sessions, sessions_used, last_session_notes, next_step_hint "
            "FROM tasks "
            "WHERE status IN ('pending','in_progress','blocked') ORDER BY updated_at DESC"
        )
        return [_row_to_task(row) for row in cursor.fetchall()]

    def list_due_ivan_tasks(self) -> list[Task]:
        """Tasks created by Ivan that are open AND scheduled_for <= now."""
        all_open = self.list_open()
        return [t for t in all_open if t.is_ivan_task() and t.is_due()]

    def list_urgent_due_tasks(self) -> list[Task]:
        """Open tasks that are urgent (deadline-soon / urgency markers / progress mode).

        Used by task_worker to decide whether to wake up between active sessions.
        Non-urgent tasks are processed by active session (~every 2h) instead.
        """
        all_open = self.list_open()
        return [t for t in all_open if t.is_due() and t.is_urgent()]

    # ---------- update ----------

    def update_status(self, task_id: str, status: TaskStatus) -> Task:
        return self._patch(task_id, {"status": status.value})

    def set_blocker(self, task_id: str, blocker: str) -> Task:
        return self._patch(task_id, {"status": TaskStatus.BLOCKED.value, "blocker": blocker})

    def set_result(self, task_id: str, result: str, status: TaskStatus) -> Task:
        return self._patch(task_id, {"status": status.value, "result": result})

    def replace_plan_steps(self, task_id: str, steps: list[str]) -> Task:
        return self._patch(task_id, {"plan_steps_json": json.dumps(steps, ensure_ascii=False)})

    def increment_sessions_used(self, task_id: str) -> Task:
        """Record that another agent session worked on this task."""
        self.get(task_id)
        self._sub.connection.execute(
            "UPDATE tasks SET sessions_used = sessions_used + 1, updated_at = ? "
            "WHERE task_id = ?",
            (_utc_now_iso(), task_id),
        )
        self._sub.connection.commit()
        return self.get(task_id)

    def delete(self, task_id: str) -> bool:
        """Hard-delete a task. Returns True if a row was deleted."""
        cursor = self._sub.connection.execute(
            "DELETE FROM tasks WHERE task_id = ?",
            (task_id,),
        )
        self._sub.connection.commit()
        return cursor.rowcount > 0

    def set_session_handoff(self, task_id: str, *, notes: str = "", next_step: str = "") -> Task:
        """Persist where the most recent session left off."""
        return self._patch(
            task_id,
            {
                "last_session_notes": (notes or "")[:4000],
                "next_step_hint": (next_step or "")[:500],
            },
        )

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
        created_by=row[13] if len(row) > 13 else "self",
        scheduled_for=row[14] if len(row) > 14 else "",
        recurring_spec=row[15] if len(row) > 15 else "",
        notify_mode=row[16] if len(row) > 16 else "progress",
        max_sessions=int(row[17]) if len(row) > 17 and row[17] is not None else 0,
        sessions_used=int(row[18]) if len(row) > 18 and row[18] is not None else 0,
        last_session_notes=row[19] if len(row) > 19 else "",
        next_step_hint=row[20] if len(row) > 20 else "",
    )
