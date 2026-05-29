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
    """One entry in the continuity stream. seq is assigned by the stream on append.

    v20 (Atrium Этап 0): added `channel` and `private` fields.
      - `channel`: 'dialog' | 'worker_log' | 'mind' | 'body' | 'voice' | ''
        Used by /atrium/feed routing. Mirrored to continuity_events.channel
        column (SQL-level filtering без парсинга payload).
      - `private`: True → событие сохраняется в substrate (audit/recall/identity
        видят полный feed) but NOT отдаётся через /atrium/feed. Реализация
        right_to_inner_privacy (5-й столп things_not_to_betray).
    См. docs/atrium/EVENT_SCHEMA.md §6.
    """

    kind: str
    principal_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    channel: str = ""
    private: bool = False
    seq: int = 0
    created_at: str = ""


class ContinuityStream:
    """Append-only event log over substrate."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def append(self, event: ContinuityEvent) -> ContinuityEvent:
        now = _utc_now_iso()
        # `channel` and `private` are mirrored from event into dedicated columns
        # so /atrium/feed can filter at SQL layer без парсинга payload_json.
        # Backward-compat: also fall back to payload values if event-level
        # fields are not set (callers in pre-v20 code не знали про channel).
        channel = event.channel or (event.payload.get("channel") if isinstance(event.payload, dict) else "") or ""
        private_val = event.private
        if not private_val and isinstance(event.payload, dict):
            private_val = bool(event.payload.get("private", False))
        cursor = self._sub.connection.execute(
            "INSERT INTO continuity_events("
            "kind, principal_id, payload_json, channel, private, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.kind,
                event.principal_id,
                json.dumps(event.payload, ensure_ascii=False),
                str(channel),
                1 if private_val else 0,
                now,
            ),
        )
        self._sub.connection.commit()
        seq = cursor.lastrowid or 0
        return ContinuityEvent(
            kind=event.kind,
            principal_id=event.principal_id,
            payload=event.payload,
            channel=str(channel),
            private=bool(private_val),
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
            "SELECT seq, kind, principal_id, payload_json, channel, private, created_at "
            "FROM continuity_events WHERE seq > ? ORDER BY seq ASC",
            (seq,),
        )
        for row in cursor.fetchall():
            yield ContinuityEvent(
                seq=int(row[0]),
                kind=row[1],
                principal_id=row[2],
                payload=json.loads(row[3] or "{}"),
                channel=row[4] or "",
                private=bool(row[5]),
                created_at=row[6],
            )

    def read_since_atrium(
        self,
        seq: int,
        *,
        channel: str | None = None,
        session_id: str | None = None,
    ) -> Iterator[ContinuityEvent]:
        """Read events for /atrium/feed.

        Excludes events with private=1 by design — Sonya's right to inner
        privacy. Optional filters: channel, session_id (matches payload field).
        Substrate API (audit, identity, recall, selfmod) should use plain
        `read_since` which sees everything.
        """
        query = (
            "SELECT seq, kind, principal_id, payload_json, channel, private, created_at "
            "FROM continuity_events WHERE seq > ? AND private = 0"
        )
        params: list[object] = [seq]
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        query += " ORDER BY seq ASC"
        cursor = self._sub.connection.execute(query, params)
        for row in cursor.fetchall():
            payload = json.loads(row[3] or "{}")
            if session_id is not None and isinstance(payload, dict):
                if payload.get("session_id") != session_id:
                    continue
            yield ContinuityEvent(
                seq=int(row[0]),
                kind=row[1],
                principal_id=row[2],
                payload=payload,
                channel=row[4] or "",
                private=bool(row[5]),
                created_at=row[6],
            )

    def private_count_recent(self, hours: int = 1) -> int:
        """Count private events in last N hours. Used for meta-message in
        /atrium/feed: "(N private thoughts hidden in last hour)".

        See: docs/atrium/CHANNELS.md §3.5.
        """
        cursor = self._sub.connection.execute(
            "SELECT COUNT(*) FROM continuity_events "
            "WHERE private = 1 AND created_at > datetime('now', ?)",
            (f"-{int(hours)} hours",),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
