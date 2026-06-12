from __future__ import annotations

from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory
from sonya.memory.types import classify_event_type, is_trace_type
import json
from uuid import uuid4
from datetime import datetime, timezone

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConsolidationPipeline:
    def __init__(self, episodic: EpisodicMemory, semantic: SemanticMemory) -> None:
        self._episodic = episodic
        self._semantic = semantic

    def run_consolidation(self, min_importance: float = 0.5) -> int:
        events = self._episodic.get_recent(limit=500, mark_accessed=False, exclude_trace_types=True)
        existing_facts = self._semantic.get_all(limit=1000)
        existing_statements = {f.statement.strip().lower() for f in existing_facts}

        created = 0
        for event in events:
            if event.importance_score < min_importance:
                continue
            rt = classify_event_type(event.event_type)
            if is_trace_type(rt):
                continue
            summary = (event.normalized_summary or "").strip()
            if not summary:
                continue
            if summary.lower() in existing_statements:
                continue
            if len(summary) < 15:
                continue

            scope = event.scope or "global"
            project_id = event.project_id or ""

            now = _utc_now_iso()
            candidate_id = f"cc-{uuid4().hex[:12]}"
            self._semantic._sub.connection.execute(
                "INSERT INTO consolidation_candidates"
                "(candidate_id, statement, source_event_ids_json, confidence, scope, project_id, eval_status, eval_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', '', ?)",
                (
                    candidate_id,
                    summary,
                    json.dumps([event.event_id], ensure_ascii=False),
                    min(1.0, event.importance_score + 0.1),
                    scope,
                    project_id,
                    now
                )
            )
            existing_statements.add(summary.lower())
            created += 1
            if created >= 50:
                break
        
        self._semantic._sub.connection.commit()
        return created

    def evaluate_candidates(self) -> int:
        """Runs quality checks on pending consolidation candidates.
        
        For now, this uses a fast heuristic/stub that automatically approves
        non-empty candidates to satisfy #48's evaluation architecture requirement.
        It rejects candidates that are too short.
        """
        rows = self._semantic._sub.connection.execute(
            "SELECT candidate_id, statement, source_event_ids_json, confidence, scope, project_id "
            "FROM consolidation_candidates WHERE eval_status = 'pending' LIMIT 50"
        ).fetchall()
        
        processed = 0
        for row in rows:
            candidate_id, statement, src_json, conf, scope, project_id = row
            src_ids = json.loads(src_json or "[]")
            
            # Simple heuristic evaluation
            if len(statement.strip()) < 20:
                status = "rejected"
                reason = "statement too short for a durable semantic fact"
            else:
                status = "approved"
                reason = "heuristically approved as plausible consolidation"
                
            self._semantic._sub.connection.execute(
                "UPDATE consolidation_candidates SET eval_status = ?, eval_reason = ? WHERE candidate_id = ?",
                (status, reason, candidate_id)
            )
            
            if status == "approved":
                self._semantic.add_fact(
                    fact_type="consolidated_observation",
                    statement=statement,
                    source_event_ids=tuple(src_ids),
                    confidence=conf,
                    scope=scope,
                    project_id=project_id
                )
            processed += 1
            
        self._semantic._sub.connection.commit()
        return processed
