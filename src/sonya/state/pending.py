from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sonya.state.substrate import Substrate


class IntentionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class IntentionNotFoundError(KeyError):
    pass


class IntentionAlreadyResolvedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PendingIntention:
    """First-class persistent intention: what Sonya promised to do.

    Linked to task_id (optional), has deadline (optional), survives restart.
    See: docs/cognition/COGNITION.md §7 (deferred work).
    """

    intention_id: str
    principal_id: str | None
    description: str
    task_id: str | None = None
    deadline: str | None = None
    status: IntentionStatus = IntentionStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingIntentionStore:
    """Persistent CRUD for PendingIntention objects in substrate."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def create(
        self,
        *,
        principal_id: str | None = None,
        description: str,
        task_id: str | None = None,
        deadline: str | None = None,
    ) -> PendingIntention:
        intention_id = f"intn-{uuid4().hex}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO pending_intentions"
            "(intention_id, principal_id, description, task_id, deadline, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
            (intention_id, principal_id, description, task_id, deadline, now, now),
        )
        self._sub.connection.commit()
        return PendingIntention(
            intention_id=intention_id,
            principal_id=principal_id,
            description=description,
            task_id=task_id,
            deadline=deadline,
            status=IntentionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def get(self, intention_id: str) -> PendingIntention:
        row = self._sub.connection.execute(
            "SELECT intention_id, principal_id, description, task_id, deadline, "
            "status, created_at, updated_at FROM pending_intentions WHERE intention_id = ?",
            (intention_id,),
        ).fetchone()
        if row is None:
            raise IntentionNotFoundError(intention_id)
        return _row_to_intention(row)

    def list_active(self) -> list[PendingIntention]:
        cursor = self._sub.connection.execute(
            "SELECT intention_id, principal_id, description, task_id, deadline, "
            "status, created_at, updated_at FROM pending_intentions "
            "WHERE status = 'active' ORDER BY created_at ASC"
        )
        return [_row_to_intention(row) for row in cursor.fetchall()]

    def complete(self, intention_id: str) -> PendingIntention:
        return self._transition(intention_id, IntentionStatus.COMPLETED)

    def cancel(self, intention_id: str) -> PendingIntention:
        return self._transition(intention_id, IntentionStatus.CANCELLED)

    def mark_overdue(self, intention_id: str) -> PendingIntention:
        return self._transition(intention_id, IntentionStatus.OVERDUE)

    def _transition(
        self, intention_id: str, new_status: IntentionStatus
    ) -> PendingIntention:
        current = self.get(intention_id)
        if current.status is not IntentionStatus.ACTIVE:
            raise IntentionAlreadyResolvedError(
                f"intention {intention_id} is already {current.status.value}"
            )
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE pending_intentions SET status = ?, updated_at = ? WHERE intention_id = ?",
            (new_status.value, now, intention_id),
        )
        self._sub.connection.commit()
        return self.get(intention_id)


def _row_to_intention(row) -> PendingIntention:
    return PendingIntention(
        intention_id=row[0],
        principal_id=row[1],
        description=row[2],
        task_id=row[3],
        deadline=row[4],
        status=IntentionStatus(row[5]),
        created_at=row[6],
        updated_at=row[7],
    )
