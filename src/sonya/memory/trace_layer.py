from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.memory.types import RecordType, Scope, RetentionPolicy, MemoryRecordMeta
from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class TraceEntry:
    trace_id: str
    record_type: RecordType
    scope: Scope
    source: str
    raw_content: str
    normalized_summary: str = ""
    importance: float = 0.3
    stability: float = 0.2
    project_id: str = ""
    retention_policy: RetentionPolicy = RetentionPolicy.archive_only
    tags: tuple[str, ...] = field(default_factory=tuple)
    session_type: str = ""
    metadata_json: str = ""
    created_at: str = ""


class TraceLayer:
    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def record(
        self,
        *,
        record_type: RecordType,
        raw_content: str,
        normalized_summary: str = "",
        source: str = "",
        scope: Scope | None = None,
        importance: float | None = None,
        stability: float | None = None,
        project_id: str = "",
        retention_policy: RetentionPolicy | None = None,
        tags: tuple[str, ...] = (),
        session_type: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TraceEntry:
        meta = MemoryRecordMeta.for_type(
            record_type,
            importance=importance,
            scope=scope,
            source=source,
            stability=stability,
            project_id=project_id,
            retention_policy=retention_policy,
        )
        trace_id = f"tr-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        self._sub.connection.execute(
            "INSERT INTO raw_traces"
            "(trace_id, record_type, scope, source, raw_content, normalized_summary, "
            "importance, stability, project_id, retention_policy, tags_json, "
            "session_type, metadata_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trace_id, meta.record_type.value, meta.scope.value, meta.source,
             raw_content, normalized_summary,
             meta.importance, meta.stability, meta.project_id,
             meta.retention_policy.value,
             json.dumps(list(tags), ensure_ascii=False),
             session_type, meta_json, now),
        )
        self._sub.connection.commit()
        return TraceEntry(
            trace_id=trace_id, record_type=meta.record_type,
            scope=meta.scope, source=meta.source,
            raw_content=raw_content, normalized_summary=normalized_summary,
            importance=meta.importance, stability=meta.stability,
            project_id=meta.project_id,
            retention_policy=meta.retention_policy,
            tags=tags, session_type=session_type,
            metadata_json=meta_json, created_at=now,
        )

    def get_recent(self, limit: int = 50, *, scope: Scope | None = None, project_id: str | None = None) -> list[TraceEntry]:
        clauses = ["1=1"]
        params: list[Any] = []
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope.value)
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = " AND ".join(clauses)
        rows = self._sub.connection.execute(
            f"SELECT trace_id, record_type, scope, source, raw_content, normalized_summary, "
            f"importance, stability, project_id, retention_policy, tags_json, "
            f"session_type, metadata_json, created_at "
            f"FROM raw_traces WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [_row_to_trace(r) for r in rows]

    def get_by_type(self, record_type: RecordType, limit: int = 50) -> list[TraceEntry]:
        rows = self._sub.connection.execute(
            "SELECT trace_id, record_type, scope, source, raw_content, normalized_summary, "
            "importance, stability, project_id, retention_policy, tags_json, "
            "session_type, metadata_json, created_at "
            "FROM raw_traces WHERE record_type = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (record_type.value, limit),
        ).fetchall()
        return [_row_to_trace(r) for r in rows]

    def get_for_compilation(self, since_hours: int = 24, limit: int = 500) -> list[TraceEntry]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
        rows = self._sub.connection.execute(
            "SELECT trace_id, record_type, scope, source, raw_content, normalized_summary, "
            "importance, stability, project_id, retention_policy, tags_json, "
            "session_type, metadata_json, created_at "
            "FROM raw_traces WHERE created_at >= ? "
            "AND record_type NOT IN (?, ?, ?) "
            "AND importance >= ? "
            "ORDER BY created_at DESC LIMIT ?",
            (cutoff,
             RecordType.raw_trace.value, RecordType.subagent_trace.value,
             RecordType.tool_observation.value,
             0.4, limit),
        ).fetchall()
        return [_row_to_trace(r) for r in rows]

    def apply_decay(self, *, archive_after_days: int = 30) -> int:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=archive_after_days)).isoformat()
        cursor = self._sub.connection.execute(
            "DELETE FROM raw_traces WHERE retention_policy = ? AND created_at < ?",
            (RetentionPolicy.archive_only.value, cutoff),
        )
        deleted = cursor.rowcount
        self._sub.connection.commit()
        return deleted


def _row_to_trace(row) -> TraceEntry:
    raw_tags = row[10] or "[]"
    try:
        tags = tuple(json.loads(raw_tags))
    except (json.JSONDecodeError, TypeError):
        tags = ()
    return TraceEntry(
        trace_id=row[0], record_type=RecordType(row[1]),
        scope=Scope(row[2]), source=row[3],
        raw_content=row[4], normalized_summary=row[5],
        importance=row[6], stability=row[7],
        project_id=row[8],
        retention_policy=RetentionPolicy(row[9]),
        tags=tags, session_type=row[11],
        metadata_json=row[12] or "", created_at=row[13],
    )


__all__ = ["TraceLayer", "TraceEntry"]