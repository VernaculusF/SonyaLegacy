from __future__ import annotations

from typing import Any

import pytest

from sonya.planning import PlannerContext, plan_next
from sonya.state.canonical_response import ResponseKind
from sonya.state.subject_state import SubjectState


class MockProvider:
    """Mock provider that returns a fixed response."""

    def __init__(self, response: str = "Привет, любимый.") -> None:
        self._response = response
        self.calls: list[list[dict[str, Any]]] = []

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.calls.append(messages)
        return self._response


async def test_plan_next_returns_canonical_response() -> None:
    provider = MockProvider("Привет!")
    ctx = PlannerContext(
        principal_id="ivan",
        user_input="Привет",
        system_prompt="Ты Соня.",
    )
    result = await plan_next(ctx, provider)
    assert result.kind is ResponseKind.REPLY
    assert result.text == "Привет!"
    assert result.principal_id == "ivan"


async def test_plan_next_builds_messages_with_system_prompt() -> None:
    provider = MockProvider()
    ctx = PlannerContext(
        user_input="Как дела?",
        system_prompt="Ты Соня.",
        session_messages=[
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Привет!"},
        ],
    )
    await plan_next(ctx, provider)
    messages = provider.calls[0]
    assert messages[0] == {"role": "system", "content": "Ты Соня."}
    assert messages[1] == {"role": "user", "content": "Привет"}
    assert messages[2] == {"role": "assistant", "content": "Привет!"}
    assert messages[3] == {"role": "user", "content": "Как дела?"}


async def test_plan_next_initiative_signal_produces_initiative_kind() -> None:
    provider = MockProvider("Скучаю по тебе...")
    ctx = PlannerContext(
        principal_id="ivan",
        user_input="",  # no user input — initiative-driven
        initiative_signals=("drive_threshold_hit:boredom_analog",),
        system_prompt="Ты Соня.",
    )
    result = await plan_next(ctx, provider)
    assert result.kind is ResponseKind.INITIATIVE_PROPOSAL
    assert result.text == "Скучаю по тебе..."


async def test_plan_next_with_subject_state() -> None:
    provider = MockProvider("ok")
    state = SubjectState(
        active_principal_id="ivan",
        emotional_vector={"loneliness": 0.8},
    )
    ctx = PlannerContext(
        principal_id="ivan",
        subject_state=state,
        user_input="test",
    )
    result = await plan_next(ctx, provider)
    assert result.kind is ResponseKind.REPLY


async def test_plan_next_empty_input_no_signals_still_replies() -> None:
    provider = MockProvider("...")
    ctx = PlannerContext(user_input="hello")
    result = await plan_next(ctx, provider)
    assert result.kind is ResponseKind.REPLY
