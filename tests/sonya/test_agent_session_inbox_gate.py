"""Inbox priority gate — Sonya can't [DONE] without chat.dialog reply.

Regression for the 30.05 silent-no-reply bug: active session was triggered
by an atrium dialog message; Sonya called body.expression and immediately
[DONE], leaving Ivan with no text reply. The gate forces chat.dialog before
[DONE] when the session was opened on a real Ivan message
(`require_dialog_reply=True`).
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


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.calls += 1
        if not self._responses:
            return "[DONE]"
        return self._responses.pop(0)


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


async def test_done_blocked_when_dialog_reply_required(substrate: Substrate) -> None:
    """If the session opened on a real Ivan message, [DONE] without
    chat.dialog must be refused and the model nudged to reply."""
    stream = ContinuityStream(substrate)

    # First turn: model tries to close without replying. Gate must block.
    # Second turn: model still tries. Gate blocks again.
    # Third turn: model finally writes a [DONE] (would normally close, but
    # again gate blocks because no chat.dialog ever fired).
    # We're not driving chat.dialog here — that needs the outbound machinery.
    # Just verify the gate triggered at least once.
    provider = _Stub([
        "[DONE: тихо смотрю]",
        "[DONE: всё ещё тихо]",
        "[DONE: ну хватит]",
        "[DONE: финал]",
    ])

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="Привет, отзовись",
        require_dialog_reply=True,
        max_steps=4,
        max_seconds=10.0,
        purpose="test",
    )

    # Find inbox_priority_gate audit events.
    gate_events = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events WHERE kind = 'internal.inbox_priority_gate'"
    ).fetchone()[0]
    assert gate_events >= 1, "gate must have blocked at least one [DONE]"
    # The session should have hit the step cap (no chat.dialog tool, no
    # break path). budget_exceeded covers the case where time ran out;
    # otherwise we expect at least N gate events.
    assert provider.calls >= 2, "model should have been re-prompted"


async def test_done_allowed_without_dialog_reply_required(substrate: Substrate) -> None:
    """When the caller doesn't set require_dialog_reply, [DONE] closes
    immediately as before — internal sessions keep their old semantics."""
    stream = ContinuityStream(substrate)
    provider = _Stub([
        "[DONE: всё, я закончила]",
    ])

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="seed",  # provided but require_dialog_reply NOT set
        require_dialog_reply=False,
        max_steps=4,
        max_seconds=10.0,
        purpose="test",
    )

    assert provider.calls == 1
    assert "закончила" in (result.final_output or "")
    # No gate events
    gate_events = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events WHERE kind = 'internal.inbox_priority_gate'"
    ).fetchone()[0]
    assert gate_events == 0
