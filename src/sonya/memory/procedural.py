from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.memory.types import RecordType, Scope, RetentionPolicy
from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ProceduralLesson:
    lesson_id: str
    record_type: RecordType
    scope: Scope
    statement: str
    domain: str
    pattern: str = ""
    project_id: str = ""
    source_trace_ids: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.5
    last_reinforced_at: str = ""
    retention_policy: RetentionPolicy = RetentionPolicy.long
    created_at: str = ""


class ProceduralMemory:
    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def add_lesson(
        self,
        *,
        statement: str,
        domain: str,
        pattern: str = "",
        project_id: str = "",
        source_trace_ids: tuple[str, ...] = (),
        confidence: float = 0.5,
        scope: Scope = Scope.global_,
    ) -> ProceduralLesson:
        lesson_id = f"pl-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO procedural_memory"
            "(lesson_id, record_type, scope, statement, domain, pattern, "
            "project_id, source_trace_ids_json, confidence, "
            "last_reinforced_at, retention_policy, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lesson_id, RecordType.operational_lesson.value, scope.value,
             statement, domain, pattern, project_id,
             json.dumps(list(source_trace_ids), ensure_ascii=False),
             confidence, now, RetentionPolicy.long.value, now),
        )
        self._sub.connection.commit()
        return ProceduralLesson(
            lesson_id=lesson_id, record_type=RecordType.operational_lesson,
            scope=scope, statement=statement, domain=domain,
            pattern=pattern, project_id=project_id,
            source_trace_ids=source_trace_ids, confidence=confidence,
            last_reinforced_at=now, retention_policy=RetentionPolicy.long,
            created_at=now,
        )

    def get_all(self, limit: int = 50, *, project_id: str | None = None, domain: str | None = None) -> list[ProceduralLesson]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if domain is not None:
            clauses.append("domain = ?")
            params.append(domain)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self._sub.connection.execute(
            f"SELECT lesson_id, record_type, scope, statement, domain, pattern, "
            f"project_id, source_trace_ids_json, confidence, "
            f"last_reinforced_at, retention_policy, created_at "
            f"FROM procedural_memory WHERE {where} "
            f"ORDER BY confidence DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [_row_to_lesson(r) for r in rows]

    def reinforce(self, lesson_id: str) -> None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE procedural_memory SET confidence = MIN(1.0, confidence + 0.1), "
            "last_reinforced_at = ? WHERE lesson_id = ?",
            (now, lesson_id),
        )
        self._sub.connection.commit()

    def apply_decay(self, *, decay_rate: float = 0.03) -> int:
        self._sub.connection.execute(
            "UPDATE procedural_memory SET confidence = confidence * ? "
            "WHERE retention_policy != ?",
            (1.0 - decay_rate, RetentionPolicy.identity_critical.value),
        )
        cursor = self._sub.connection.execute(
            "DELETE FROM procedural_memory WHERE confidence < 0.05 "
            "AND retention_policy = ?",
            (RetentionPolicy.short.value,),
        )
        deleted = cursor.rowcount
        self._sub.connection.commit()
        return deleted


def _row_to_lesson(row) -> ProceduralLesson:
    raw_ids = row[7] or "[]"
    try:
        source_ids = tuple(json.loads(raw_ids))
    except (json.JSONDecodeError, TypeError):
        source_ids = ()
    return ProceduralLesson(
        lesson_id=row[0], record_type=RecordType(row[1]),
        scope=Scope(row[2]), statement=row[3], domain=row[4],
        pattern=row[5], project_id=row[6],
        source_trace_ids=source_ids, confidence=row[8],
        last_reinforced_at=row[9],
        retention_policy=RetentionPolicy(row[10]),
        created_at=row[11],
    )


__all__ = ["ProceduralMemory", "ProceduralLesson"]