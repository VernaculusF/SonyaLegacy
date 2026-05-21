"""Goal hierarchy — long-term objectives above tasks.

Goals are the "why" — tasks are the "what/how". Active sessions read
current goals to decide what to work on. Tasks can be linked to a goal
via parent_goal_id.

Substrate v16: goals table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class Goal:
    goal_id: str
    title: str
    description: str = ""
    status: str = "active"  # active | achieved | abandoned
    priority: int = 0
    created_at: str = ""
    updated_at: str = ""


class GoalStore:
    """CRUD over goals table."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def create(self, title: str, description: str = "", priority: int = 0) -> Goal:
        goal_id = f"goal-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO goals(goal_id, title, description, status, priority, "
            "created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?, ?)",
            (goal_id, title, description, priority, now, now),
        )
        self._sub.connection.commit()
        return Goal(
            goal_id=goal_id, title=title, description=description,
            status="active", priority=priority, created_at=now, updated_at=now,
        )

    def list_active(self) -> list[Goal]:
        cursor = self._sub.connection.execute(
            "SELECT goal_id, title, description, status, priority, created_at, updated_at "
            "FROM goals WHERE status = 'active' ORDER BY priority DESC, created_at ASC"
        )
        return [_row_to_goal(r) for r in cursor.fetchall()]

    def list_all(self) -> list[Goal]:
        cursor = self._sub.connection.execute(
            "SELECT goal_id, title, description, status, priority, created_at, updated_at "
            "FROM goals ORDER BY priority DESC, created_at ASC"
        )
        return [_row_to_goal(r) for r in cursor.fetchall()]

    def achieve(self, goal_id: str) -> Goal:
        return self._set_status(goal_id, "achieved")

    def abandon(self, goal_id: str) -> Goal:
        return self._set_status(goal_id, "abandoned")

    def _set_status(self, goal_id: str, status: str) -> Goal:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE goals SET status = ?, updated_at = ? WHERE goal_id = ?",
            (status, now, goal_id),
        )
        self._sub.connection.commit()
        row = self._sub.connection.execute(
            "SELECT goal_id, title, description, status, priority, created_at, updated_at "
            "FROM goals WHERE goal_id = ?", (goal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(goal_id)
        return _row_to_goal(row)


def _row_to_goal(row) -> Goal:
    return Goal(
        goal_id=row[0], title=row[1], description=row[2],
        status=row[3], priority=int(row[4]),
        created_at=row[5], updated_at=row[6],
    )
