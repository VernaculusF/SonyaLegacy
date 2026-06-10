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
class SemanticFact:
    fact_id: str
    fact_type: str
    statement: str
    source_event_ids: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.5
    last_reinforced_at: str = ""
    contradiction_flags: tuple[str, ...] = field(default_factory=tuple)
    scope: str = "global"
    project_id: str = ""
    retention_policy: str = "long"


class SemanticMemory:
    """Persistent semantic memory — consolidated knowledge from episodic events.

    See: docs/cognition/COGNITION.md §12 (semantic memory).
    """

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def add_fact(
        self,
        *,
        fact_type: str,
        statement: str,
        source_event_ids: tuple[str, ...] = (),
        confidence: float = 0.5,
        scope: str = "global",
        project_id: str = "",
        retention_policy: str = "long",
    ) -> SemanticFact:
        fact_id = f"sf-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO semantic_facts"
            "(fact_id, fact_type, statement, source_event_ids_json, "
            "confidence, last_reinforced_at, contradiction_flags_json, "
            "scope, project_id, retention_policy) "
            "VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)",
            (fact_id, fact_type, statement,
             json.dumps(list(source_event_ids), ensure_ascii=False),
             confidence, now, scope, project_id, retention_policy),
        )
        self._sub.connection.commit()
        return SemanticFact(
            fact_id=fact_id, fact_type=fact_type, statement=statement,
            source_event_ids=source_event_ids, confidence=confidence,
            last_reinforced_at=now, scope=scope,
            project_id=project_id, retention_policy=retention_policy,
        )

    def get_all(self, limit: int = 50, *, project_id: str | None = None, scope: str | None = None) -> list[SemanticFact]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        where = " AND ".join(clauses) if clauses else "1=1"
        cursor = self._sub.connection.execute(
            f"SELECT fact_id, fact_type, statement, source_event_ids_json, "
            f"confidence, last_reinforced_at, contradiction_flags_json, "
            f"scope, project_id, retention_policy "
            f"FROM semantic_facts WHERE {where} "
            f"ORDER BY confidence DESC LIMIT ?",
            (*params, limit),
        )
        return [_row_to_fact(r) for r in cursor.fetchall()]

    def get_for_context(self, *, project_id: str | None = None, limit: int = 10) -> list[SemanticFact]:
        project_facts = []
        global_facts = []
        if project_id:
            project_facts = self.get_all(limit=limit, project_id=project_id)
            global_facts = self.get_all(limit=limit, scope="global")
        else:
            global_facts = self.get_all(limit=limit, scope="global")
        seen = {f.statement.strip().lower() for f in project_facts}
        filtered_global = [f for f in global_facts if f.statement.strip().lower() not in seen]
        return project_facts + filtered_global[:limit]

    def reinforce(self, fact_id: str) -> None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE semantic_facts SET confidence = MIN(1.0, confidence + 0.1), "
            "last_reinforced_at = ? WHERE fact_id = ?",
            (now, fact_id),
        )
        self._sub.connection.commit()

    def apply_decay(self, *, decay_rate: float = 0.03) -> int:
        self._sub.connection.execute(
            "UPDATE semantic_facts SET confidence = confidence * ? "
            "WHERE retention_policy NOT IN (?, ?)",
            (1.0 - decay_rate, "identity_critical", "long"),
        )
        cursor = self._sub.connection.execute(
            "DELETE FROM semantic_facts WHERE confidence < 0.05 "
            "AND retention_policy IN (?, ?)",
            ("short", "medium"),
        )
        deleted = cursor.rowcount
        self._sub.connection.commit()
        return deleted


def _row_to_fact(row) -> SemanticFact:
    scope = row[7] if len(row) > 7 else "global"
    project_id = row[8] if len(row) > 8 else ""
    retention_policy = row[9] if len(row) > 9 else "long"
    return SemanticFact(
        fact_id=row[0], fact_type=row[1], statement=row[2],
        source_event_ids=tuple(json.loads(row[3] or "[]")),
        confidence=row[4], last_reinforced_at=row[5],
        contradiction_flags=tuple(json.loads(row[6] or "[]")),
        scope=scope, project_id=project_id,
        retention_policy=retention_policy,
    )
