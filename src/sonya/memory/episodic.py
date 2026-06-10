from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class EpisodicEvent:
    event_id: str
    event_type: str
    timestamp: str
    source: str = ""
    channel: str = ""
    actor: str = ""
    raw_content: str = ""
    normalized_summary: str = ""
    emotion_tags: tuple[str, ...] = field(default_factory=tuple)
    importance_score: float = 0.5
    retention_strength: float = 1.0
    last_accessed_at: str = ""
    access_count: int = 0
    archived: bool = False
    record_type: str = ""
    scope: str = ""
    project_id: str = ""
    retention_policy: str = ""


class EpisodicMemory:
    """Persistent episodic memory backed by substrate.

    Append-only baseline with retrieval by recency, type, and importance.
    Retention strength decays over time (Ebbinghaus curve applied externally).
    See: docs/cognition/COGNITION.md §11, §14 (forgetting curve).
    """

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def record(
        self,
        *,
        event_type: str,
        raw_content: str,
        normalized_summary: str = "",
        source: str = "",
        channel: str = "",
        actor: str = "",
        emotion_tags: tuple[str, ...] = (),
        importance_score: float = 0.5,
        record_type: str = "",
        scope: str = "",
        project_id: str = "",
        retention_policy: str = "",
    ) -> EpisodicEvent:
        from sonya.memory.types import classify_event_type, default_scope, default_retention, RecordType
        rt = record_type or classify_event_type(event_type).value
        sc = scope or default_scope(RecordType(rt)).value
        rp = retention_policy or default_retention(RecordType(rt)).value
        event_id = f"ep-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO episodic_events"
            "(event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, "
            "importance_score, retention_strength, last_accessed_at, access_count, archived, "
            "record_type, scope, project_id, retention_policy) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, 0, 0, ?, ?, ?, ?)",
            (event_id, event_type, now, source, channel, actor,
             raw_content, normalized_summary,
             json.dumps(list(emotion_tags), ensure_ascii=False),
             importance_score, now, rt, sc, project_id, rp),
        )
        self._sub.connection.commit()
        return EpisodicEvent(
            event_id=event_id, event_type=event_type, timestamp=now,
            source=source, channel=channel, actor=actor,
            raw_content=raw_content, normalized_summary=normalized_summary,
            emotion_tags=emotion_tags, importance_score=importance_score,
            retention_strength=1.0, last_accessed_at=now,
            record_type=rt, scope=sc, project_id=project_id,
            retention_policy=rp,
        )

    def get_recent(self, limit: int = 20, *, mark_accessed: bool = True, project_id: str | None = None, exclude_trace_types: bool = True) -> list[EpisodicEvent]:
        from sonya.memory.types import is_trace_type, RecordType
        clauses = ["archived = 0"]
        if exclude_trace_types:
            trace_vals = ",".join(f"'{rt.value}'" for rt in RecordType if is_trace_type(rt))
            clauses.append(f"record_type NOT IN ({trace_vals}) OR record_type = ''")
        params: list[Any] = []
        if project_id is not None:
            clauses.append("(project_id = ? OR scope = 'global')")
            params.append(project_id)
        where = " AND ".join(clauses)
        cursor = self._sub.connection.execute(
            f"SELECT event_id, event_type, timestamp, source, channel, actor, "
            f"raw_content, normalized_summary, emotion_tags_json, importance_score, "
            f"retention_strength, last_accessed_at, access_count, archived, "
            f"record_type, scope, project_id, retention_policy "
            f"FROM episodic_events WHERE {where} "
            f"ORDER BY timestamp DESC LIMIT ?",
            (*params, limit),
        )
        events = [_row_to_event(r) for r in cursor.fetchall()]
        if mark_accessed and events:
            self._mark_batch_accessed([e.event_id for e in events])
        return events

    def get_by_date_range(
        self, *, since: str = "", until: str = "", limit: int = 200, mark_accessed: bool = False
    ) -> list[EpisodicEvent]:
        """Retrieve events within a date range (ISO 8601 timestamps).

        Useful for retrospection — e.g. ``since='2026-05-01' until='2026-06-01'``
        to see all of May. Without arguments returns the most recent events.

        ``mark_accessed`` defaults to False because batch-retrospective queries
        shouldn't artificially boost retention on old events.
        """
        clauses = ["archived = 0"]
        params: list[Any] = []
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp < ?")
            params.append(until)
        where = " AND ".join(clauses)
        cursor = self._sub.connection.execute(
            f"SELECT event_id, event_type, timestamp, source, channel, actor, "
            f"raw_content, normalized_summary, emotion_tags_json, importance_score, "
            f"retention_strength, last_accessed_at, access_count, archived, "
            f"record_type, scope, project_id, retention_policy "
            f"FROM episodic_events WHERE {where} "
            f"ORDER BY timestamp DESC LIMIT ?",
            (*params, limit),
        )
        events = [_row_to_event(r) for r in cursor.fetchall()]
        if mark_accessed and events:
            self._mark_batch_accessed([e.event_id for e in events])
        return events

    def get_by_type(self, event_type: str, limit: int = 20, *, mark_accessed: bool = True) -> list[EpisodicEvent]:
        cursor = self._sub.connection.execute(
            "SELECT event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, importance_score, "
            "retention_strength, last_accessed_at, access_count, archived, "
            "record_type, scope, project_id, retention_policy "
            "FROM episodic_events WHERE event_type = ? AND archived = 0 "
            "ORDER BY timestamp DESC LIMIT ?",
            (event_type, limit),
        )
        events = [_row_to_event(r) for r in cursor.fetchall()]
        if mark_accessed and events:
            self._mark_batch_accessed([e.event_id for e in events])
        return events

    def mark_accessed(self, event_id: str) -> None:
        """Increment access_count and update last_accessed_at (strengthens retention)."""
        self._mark_batch_accessed([event_id])

    def _mark_batch_accessed(self, event_ids: list[str]) -> None:
        """Bulk update for multiple events accessed together (e.g. in get_recent)."""
        if not event_ids:
            return
        now = _utc_now_iso()
        placeholders = ",".join("?" * len(event_ids))
        self._sub.connection.execute(
            f"UPDATE episodic_events SET access_count = access_count + 1, "
            f"last_accessed_at = ?, retention_strength = MIN(1.0, retention_strength + 0.1) "
            f"WHERE event_id IN ({placeholders})",
            (now, *event_ids),
        )
        self._sub.connection.commit()

    def apply_decay(self, *, decay_rate: float = 0.05, archive_threshold: float = 0.1) -> int:
        """Apply Ebbinghaus-style decay to all unarchived events.

        Each call multiplies retention_strength by (1 - decay_rate). When a
        retention_strength drops below archive_threshold, the event is archived
        (excluded from future recall but kept for audit). Should be called
        periodically (e.g. once per day from consolidation pipeline).

        Returns number of events archived in this pass.
        """
        # Decay all unarchived
        self._sub.connection.execute(
            "UPDATE episodic_events SET retention_strength = retention_strength * ? "
            "WHERE archived = 0",
            (1.0 - decay_rate,),
        )
        # Archive those that fell below threshold
        cursor = self._sub.connection.execute(
            "UPDATE episodic_events SET archived = 1 "
            "WHERE archived = 0 AND retention_strength < ?",
            (archive_threshold,),
        )
        archived_count = cursor.rowcount
        self._sub.connection.commit()
        return archived_count


def _row_to_event(row) -> EpisodicEvent:
    raw_tags = row[8] or "[]"
    try:
        emotion_tags = tuple(json.loads(raw_tags))
    except (json.JSONDecodeError, TypeError):
        emotion_tags = ()
    rt = row[14] if len(row) > 14 else ""
    sc = row[15] if len(row) > 15 else ""
    pid = row[16] if len(row) > 16 else ""
    rp = row[17] if len(row) > 17 else ""
    return EpisodicEvent(
        event_id=row[0], event_type=row[1], timestamp=row[2],
        source=row[3], channel=row[4], actor=row[5],
        raw_content=row[6], normalized_summary=row[7],
        emotion_tags=emotion_tags,
        importance_score=row[9], retention_strength=row[10],
        last_accessed_at=row[11], access_count=row[12], archived=bool(row[13]),
        record_type=rt, scope=sc, project_id=pid, retention_policy=rp,
    )
