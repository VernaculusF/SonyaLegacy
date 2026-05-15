from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sonya.state.canonical_response import CanonicalResponse, ResponseKind
from sonya.state.subject_state import SubjectState


class CompletionProvider(Protocol):
    """Minimal provider interface for planner. Matches ProviderBackend.complete_text."""

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        ...


@dataclass(frozen=True, slots=True)
class PlannerContext:
    """Everything the planner needs to decide what Sonya does next."""

    principal_id: str | None = None
    subject_state: SubjectState = field(default_factory=SubjectState)
    user_input: str = ""
    attachments: tuple[str, ...] = field(default_factory=tuple)
    recent_continuity_kinds: tuple[str, ...] = field(default_factory=tuple)
    initiative_signals: tuple[str, ...] = field(default_factory=tuple)
    active_skill_ids: tuple[str, ...] = field(default_factory=tuple)
    session_messages: list[dict[str, Any]] = field(default_factory=list)
    system_prompt: str = ""


async def plan_next(
    context: PlannerContext,
    provider: CompletionProvider,
) -> CanonicalResponse:
    """Core planner: decides what Sonya does next.

    Takes full context (subject state, user input, initiative signals, skills)
    and returns a CanonicalResponse that channels render into their format.

    On MVP this is a simple LLM call with context assembly.
    Post-MVP: System 1/System 2 split, confidence-based routing, skill selection.
    """
    # Build messages for LLM
    messages = _build_messages(context)

    # Call provider
    raw_response = await provider.complete_text(messages)

    # Determine response kind
    kind = _determine_kind(context, raw_response)

    return CanonicalResponse(
        kind=kind,
        text=raw_response,
        principal_id=context.principal_id,
    )


def _build_messages(context: PlannerContext) -> list[dict[str, Any]]:
    """Assemble messages for LLM call from planner context."""
    messages: list[dict[str, Any]] = []

    # System prompt
    if context.system_prompt:
        messages.append({"role": "system", "content": context.system_prompt})

    # Session history
    for msg in context.session_messages:
        messages.append(msg)

    # Current user input
    if context.user_input:
        messages.append({"role": "user", "content": context.user_input})

    return messages


def _determine_kind(context: PlannerContext, response: str) -> ResponseKind:
    """Determine CanonicalResponse kind from context and response content."""
    # If this was triggered by initiative (no user input), it's an initiative proposal
    if not context.user_input and context.initiative_signals:
        return ResponseKind.INITIATIVE_PROPOSAL

    # Default: reply
    return ResponseKind.REPLY
