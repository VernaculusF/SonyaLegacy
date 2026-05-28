"""Consolidation pipeline: episodic events → semantic facts.

Scans unarchived episodic events above a threshold and promotes them
to semantic_facts. Deduplicates by checking if a fact with the same
statement already exists. Runs once per 24h from internal_loop.

See: docs/cognition/COGNITION.md §13-§14 (consolidation pipeline + forgetting curve).
"""

from __future__ import annotations

from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory


class ConsolidationPipeline:
    """Promotes high-importance episodic memories to semantic facts."""

    def __init__(self, episodic: EpisodicMemory, semantic: SemanticMemory) -> None:
        self._episodic = episodic
        self._semantic = semantic

    def run_consolidation(self, min_importance: float = 0.5) -> int:
        """Scan episodic events and promote qualifying ones to semantic facts.

        Conditions to promote:
        - importance_score >= min_importance (default 0.5)
        - has normalized_summary (non-empty)
        - not already in semantic_facts (dedup by statement text)

        Returns number of new facts created.
        """
        # Get recent events (wider window than before — 500 instead of 100)
        events = self._episodic.get_recent(limit=500, mark_accessed=False)

        # Existing statements for dedup
        existing_facts = self._semantic.get_all(limit=1000)
        existing_statements = {f.statement.strip().lower() for f in existing_facts}

        created = 0
        for event in events:
            if event.importance_score < min_importance:
                continue
            summary = (event.normalized_summary or "").strip()
            if not summary:
                continue
            # Dedup: skip if this exact statement already exists
            if summary.lower() in existing_statements:
                continue
            # Skip very short summaries (likely noise)
            if len(summary) < 15:
                continue

            self._semantic.add_fact(
                fact_type="consolidated_observation",
                statement=summary,
                source_event_ids=(event.event_id,),
                confidence=min(1.0, event.importance_score + 0.1),
            )
            existing_statements.add(summary.lower())
            created += 1

            # Cap to avoid creating thousands in one run
            if created >= 50:
                break

        return created
