from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sonya.state import Substrate


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One row in `audit_events`. Append-only.

    Semantically distinct from ContinuityStream:
      - ContinuityStream = биография субъекта (что Соня пережила/сделала);
      - AuditLog = решения harness'а (что harness разрешил/запретил, кому, когда).

    `seq` is assigned by the substrate AUTOINCREMENT; pre-append events
    carry seq=0 as a marker.
    """

    seq: int
    timestamp: str
    principal_id: str | None
    action: str
    decision: str
    scope: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    """Append-only audit log backed by substrate `audit_events`.

    Append assigns a monotonic `seq` (sqlite AUTOINCREMENT). Query supports
    filtering by principal_id, scope, and ISO-8601 time range.
    """

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def append(
        self,
        *,
        principal_id: str | None,
        action: str,
        decision: str,
        scope: str,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> AuditEvent:
        ts = timestamp or _utc_now_iso()
        meta = metadata or {}
        cursor = self._sub.connection.execute(
            "INSERT INTO audit_events"
            "(timestamp, principal_id, action, decision, scope, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, principal_id, action, decision, scope, json.dumps(meta)),
        )
        self._sub.connection.commit()
        return AuditEvent(
            seq=cursor.lastrowid or 0,
            timestamp=ts,
            principal_id=principal_id,
            action=action,
            decision=decision,
            scope=scope,
            metadata=meta,
        )

    def query(
        self,
        *,
        principal_id: str | None = None,
        scope: str | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> list[AuditEvent]:
        clauses: list[str] = []
        params: list[Any] = []
        if principal_id is not None:
            clauses.append("principal_id = ?")
            params.append(principal_id)
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        sql = (
            "SELECT seq, timestamp, principal_id, action, decision, scope, "
            "metadata_json FROM audit_events "
            f"{where}ORDER BY seq ASC"
        )
        cursor = self._sub.connection.execute(sql, params)
        return [_row_to_event(row) for row in cursor.fetchall()]


def _row_to_event(row) -> AuditEvent:
    return AuditEvent(
        seq=row[0],
        timestamp=row[1],
        principal_id=row[2],
        action=row[3],
        decision=row[4],
        scope=row[5],
        metadata=json.loads(row[6]) if row[6] else {},
    )
