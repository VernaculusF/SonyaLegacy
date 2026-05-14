from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ContinuityEvent:
    """One entry in the continuity stream. seq is assigned by the stream on append."""

    kind: str
    principal_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    created_at: str = ""


class ContinuityStream:
    """Append-only event log over substrate."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def append(self, event: ContinuityEvent) -> ContinuityEvent:
        now = _utc_now_iso()
        cursor = self._sub.connection.execute(
            "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                event.kind,
                event.principal_id,
                json.dumps(event.payload, ensure_ascii=False),
                now,
            ),
        )
        self._sub.connection.commit()
        seq = cursor.lastrowid or 0
        return ContinuityEvent(
            kind=event.kind,
            principal_id=event.principal_id,
            payload=event.payload,
            seq=int(seq),
            created_at=now,
        )

    def latest_seq(self) -> int:
        row = self._sub.connection.execute(
            "SELECT COALESCE(MAX(seq), 0) FROM continuity_events"
        ).fetchone()
        return int(row[0]) if row else 0

    def read_since(self, seq: int) -> Iterator[ContinuityEvent]:
        cursor = self._sub.connection.execute(
            "SELECT seq, kind, principal_id, payload_json, created_at "
            "FROM continuity_events WHERE seq > ? ORDER BY seq ASC",
            (seq,),
        )
        for row in cursor.fetchall():
            yield ContinuityEvent(
                seq=int(row[0]),
                kind=row[1],
                principal_id=row[2],
                payload=json.loads(row[3] or "{}"),
                created_at=row[4],
            )
