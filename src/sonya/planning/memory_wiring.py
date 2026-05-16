from __future__ import annotations

from sonya.memory.episodic import EpisodicMemory
from sonya.state.canonical_response import CanonicalResponse
from sonya.state.substrate import Substrate


def record_response_as_memory(
    substrate: Substrate,
    user_input: str,
    response: CanonicalResponse,
    channel: str = "telegram",
) -> None:
    """Record a planner response as an episodic memory event.

    Called after every successful plan_next → response cycle.
    This is the memory wiring: responses become part of Sonya's biography.
    """
    episodic = EpisodicMemory(substrate)

    # Record user message
    if user_input:
        episodic.record(
            event_type="dialogue_event",
            raw_content=user_input,
            normalized_summary=f"Иван написал: {user_input[:100]}",
            source="user",
            channel=channel,
            actor=response.principal_id or "ivan",
            importance_score=0.5,
        )

    # Record Sonya's response
    if response.text:
        episodic.record(
            event_type="dialogue_event",
            raw_content=response.text,
            normalized_summary=f"Соня ответила: {response.text[:100]}",
            source="sonya",
            channel=channel,
            actor="sonya",
            importance_score=0.6,
        )
