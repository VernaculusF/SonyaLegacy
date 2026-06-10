from __future__ import annotations

from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory
from sonya.memory.types import classify_event_type, is_trace_type


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

            self._semantic.add_fact(
                fact_type="consolidated_observation",
                statement=summary,
                source_event_ids=(event.event_id,),
                confidence=min(1.0, event.importance_score + 0.1),
                scope=scope,
                project_id=project_id,
            )
            existing_statements.add(summary.lower())
            created += 1
            if created >= 50:
                break

        return created
