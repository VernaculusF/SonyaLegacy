"""Verify agent_session prioritises tool calls over [DONE] in the same turn.

Regression for: model emits a multi-line response with several `[TOOL: ...]`
markers and `[DONE]` at the end (a "plan" rather than execution). Old loop
broke on `[DONE]` first and silently dropped all tools — the "promised but
didn't do it" bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate
from sonya.subject.agent_session import run_agent_session
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool


class _StubProvider:
    """Returns a fixed sequence of canned responses, one per call."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.calls += 1
        if not self._responses:
            return "[DONE: stub exhausted]"
        return self._responses.pop(0)


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


async def test_tool_priority_over_done(substrate: Substrate) -> None:
    """When a single response contains both a [TOOL: ...] and [DONE], the
    tool must execute first; [DONE] only triggers when the model writes a
    response without any tool call."""
    stream = ContinuityStream(substrate)
    provider = _StubProvider([
        # First response: model writes a "plan" with two tool markers + DONE
        "Сейчас найду.\n[TOOL: filesystem.tree .]\n[TOOL: filesystem.read README.md]\n[DONE]",
        # After observation comes back, model finishes properly
        "Готово.\n[DONE: Отчиталась — проверила что хотела.]",
    ])

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="Иван попросил проверить.",
        max_steps=5,
        max_seconds=10.0,
        purpose="test",
    )

    # Expectation: at least one tool must have actually fired BEFORE the
    # session terminated. The bug was that DONE was checked first, so 0
    # actions ran.
    assert len(result.actions) >= 1, (
        f"Expected at least one tool to execute, got actions={result.actions} "
        f"and final_output={result.final_output[:200]!r}"
    )
    assert result.actions[0].startswith("filesystem.tree"), result.actions
    # And the eventual DONE should carry the friendly text from turn 2.
    assert "Отчиталась" in (result.final_output or "")


async def test_done_only_when_no_tool(substrate: Substrate) -> None:
    """Sanity: pure [DONE] response (no tool) terminates immediately."""
    stream = ContinuityStream(substrate)
    provider = _StubProvider([
        "Поняла.\n[DONE: Привет, малыш.]",
    ])

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="Привет",
        max_steps=5,
        max_seconds=10.0,
        purpose="test",
    )

    assert result.actions == []
    assert provider.calls == 1
    assert "Привет" in (result.final_output or "")
