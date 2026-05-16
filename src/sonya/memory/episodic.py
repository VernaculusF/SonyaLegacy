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
    """One episodic memory event.

    See: MEMORY_AND_IDENTITY_PLAN §5.
    """

    event_id: str
    event_type: str  # dialogue_event, initiative_event, tool_event, etc.
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


class EpisodicMemory:
    """Persistent episodic memory backed by substrate.

    Append-only baseline with retrieval by recency, type, and importance.
    Retention strength decays over time (Ebbinghaus curve applied externally).
    See: MEMORY_AND_IDENTITY_PLAN §5, §12.
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
    ) -> EpisodicEvent:
        event_id = f"ep-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO episodic_events"
            "(event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, "
            "importance_score, retention_strength, last_accessed_at, access_count, archived) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, 0, 0)",
            (event_id, event_type, now, source, channel, actor,
             raw_content, normalized_summary,
             json.dumps(list(emotion_tags), ensure_ascii=False),
             importance_score, now),
        )
        self._sub.connection.commit()
        return EpisodicEvent(
            event_id=event_id, event_type=event_type, timestamp=now,
            source=source, channel=channel, actor=actor,
            raw_content=raw_content, normalized_summary=normalized_summary,
            emotion_tags=emotion_tags, importance_score=importance_score,
            retention_strength=1.0, last_accessed_at=now,
        )

    def get_recent(self, limit: int = 20) -> list[EpisodicEvent]:
        cursor = self._sub.connection.execute(
            "SELECT event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, importance_score, "
            "retention_strength, last_accessed_at, access_count, archived "
            "FROM episodic_events WHERE archived = 0 "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_event(r) for r in cursor.fetchall()]

    def get_by_type(self, event_type: str, limit: int = 20) -> list[EpisodicEvent]:
        cursor = self._sub.connection.execute(
            "SELECT event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, importance_score, "
            "retention_strength, last_accessed_at, access_count, archived "
            "FROM episodic_events WHERE event_type = ? AND archived = 0 "
            "ORDER BY timestamp DESC LIMIT ?",
            (event_type, limit),
        )
        return [_row_to_event(r) for r in cursor.fetchall()]

    def mark_accessed(self, event_id: str) -> None:
        """Increment access_count and update last_accessed_at (strengthens retention)."""
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE episodic_events SET access_count = access_count + 1, "
            "last_accessed_at = ?, retention_strength = MIN(1.0, retention_strength + 0.1) "
            "WHERE event_id = ?",
            (now, event_id),
        )
        self._sub.connection.commit()


def _row_to_event(row) -> EpisodicEvent:
    return EpisodicEvent(
        event_id=row[0], event_type=row[1], timestamp=row[2],
        source=row[3], channel=row[4], actor=row[5],
        raw_content=row[6], normalized_summary=row[7],
        emotion_tags=tuple(json.loads(row[8] or "[]")),
        importance_score=row[9], retention_strength=row[10],
        last_accessed_at=row[11], access_count=row[12], archived=bool(row[13]),
    )
