from __future__ import annotations

from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory


class ConsolidationPipeline:
    """Consolidates episodic events into semantic facts.

    MVP form: simple rule — events with high importance and repeated patterns
    get promoted to semantic facts. Real ML-based consolidation — post-MVP.

    See: MEMORY_AND_IDENTITY_PLAN §7, §12.
    """

    def __init__(self, episodic: EpisodicMemory, semantic: SemanticMemory) -> None:
        self._episodic = episodic
        self._semantic = semantic

    def run_consolidation(self, min_importance: float = 0.7) -> int:
        """Scan recent episodic events and promote high-importance ones to semantic facts.

        Returns number of facts created.
        """
        events = self._episodic.get_recent(limit=100)
        created = 0
        for event in events:
            if event.importance_score >= min_importance and event.normalized_summary:
                self._semantic.add_fact(
                    fact_type="consolidated_observation",
                    statement=event.normalized_summary,
                    source_event_ids=(event.event_id,),
                    confidence=event.importance_score,
                )
                created += 1
        return created
