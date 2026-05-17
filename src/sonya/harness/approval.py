from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sonya.state import Substrate


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalNotFoundError(KeyError):
    pass


class ApprovalAlreadyDecidedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    request_id: str
    principal_id: str
    action: str
    scope: str
    status: ApprovalStatus
    created_at: str
    decided_at: str | None = None
    decided_by_principal_id: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalManager:
    """Storage + lifecycle for human approval requests.

    Phase 2 scope: storage and decision API only. No UI or notification —
    real human gate appears in Phase 3+.
    """

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def create(
        self,
        *,
        principal_id: str,
        action: str,
        scope: str,
    ) -> ApprovalRequest:
        request_id = f"appr-{uuid4().hex}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO approval_requests"
            "(request_id, principal_id, action, scope, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (request_id, principal_id, action, scope, now),
        )
        self._sub.connection.commit()
        return ApprovalRequest(
            request_id=request_id,
            principal_id=principal_id,
            action=action,
            scope=scope,
            status=ApprovalStatus.PENDING,
            created_at=now,
        )

    def get(self, request_id: str) -> ApprovalRequest:
        row = self._sub.connection.execute(
            "SELECT request_id, principal_id, action, scope, status, "
            "created_at, decided_at, decided_by_principal_id "
            "FROM approval_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            raise ApprovalNotFoundError(request_id)
        return _row_to_request(row)

    def list_pending(self) -> list[ApprovalRequest]:
        cursor = self._sub.connection.execute(
            "SELECT request_id, principal_id, action, scope, status, "
            "created_at, decided_at, decided_by_principal_id "
            "FROM approval_requests WHERE status = 'pending' "
            "ORDER BY created_at ASC"
        )
        return [_row_to_request(row) for row in cursor.fetchall()]

    def find_by_action_pattern(self, pattern: str) -> list[ApprovalRequest]:
        """Find all requests whose action matches the given LIKE pattern.

        Pattern uses SQL LIKE syntax (`%` for wildcards). Used by
        GovernedChangeProtocol to find approval requests for a specific
        proposal_id without bypassing this manager's API.
        """
        cursor = self._sub.connection.execute(
            "SELECT request_id, principal_id, action, scope, status, "
            "created_at, decided_at, decided_by_principal_id "
            "FROM approval_requests WHERE action LIKE ? "
            "ORDER BY created_at ASC",
            (pattern,),
        )
        return [_row_to_request(row) for row in cursor.fetchall()]

    def approve(self, request_id: str, *, by_principal_id: str) -> ApprovalRequest:
        return self._decide(request_id, ApprovalStatus.APPROVED, by_principal_id)

    def deny(self, request_id: str, *, by_principal_id: str) -> ApprovalRequest:
        return self._decide(request_id, ApprovalStatus.DENIED, by_principal_id)

    def _decide(
        self,
        request_id: str,
        new_status: ApprovalStatus,
        by_principal_id: str,
    ) -> ApprovalRequest:
        current = self.get(request_id)
        if current.status is not ApprovalStatus.PENDING:
            raise ApprovalAlreadyDecidedError(
                f"approval {request_id} is already {current.status.value}"
            )
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE approval_requests "
            "SET status = ?, decided_at = ?, decided_by_principal_id = ? "
            "WHERE request_id = ?",
            (new_status.value, now, by_principal_id, request_id),
        )
        self._sub.connection.commit()
        return self.get(request_id)


def _row_to_request(row) -> ApprovalRequest:
    return ApprovalRequest(
        request_id=row[0],
        principal_id=row[1],
        action=row[2],
        scope=row[3],
        status=ApprovalStatus(row[4]),
        created_at=row[5],
        decided_at=row[6],
        decided_by_principal_id=row[7],
    )
