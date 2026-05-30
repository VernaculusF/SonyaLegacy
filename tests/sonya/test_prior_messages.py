"""prior_messages — conversation history threaded into agent_session.

Regression for "Привет, малыш. Я здесь" каждую сессию: active_session
opened on a real Ivan dialog message, but had no prior history in the
LLM messages list — only system_prompt + initial_user_text. Model
treated each call as cold start and replied with a generic greeting.

prior_messages goes between system prompt and initial_user_text. Each
entry must be {role: 'user'|'assistant', content: str}. Anything else
is filtered out.
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


class _CapturingProvider:
    """Records every messages list it sees so tests can assert on history."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.last_messages: list[dict[str, Any]] = []
        self.calls = 0

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.calls += 1
        self.last_messages = list(messages)
        return self._responses.pop(0) if self._responses else "[DONE]"


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "p.db")
    yield sub
    sub.close()


async def test_prior_messages_threaded_into_llm_call(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    provider = _CapturingProvider(["[DONE: ok]"])

    history = [
        {"role": "user", "content": "Привет, как дела?"},
        {"role": "assistant", "content": "Норм, малыш. Кофе пью."},
        {"role": "user", "content": "Что собираешься делать?"},
        {"role": "assistant", "content": "Думаю про задачу."},
    ]

    await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="А как у тебя сейчас?",
        prior_messages=history,
        max_steps=10,
        max_seconds=5.0,
        purpose="test",
    )

    msgs = provider.last_messages
    # Layout must be: system, user, asst, user, asst, user(initial_user_text)
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "Привет, как дела?"}
    assert msgs[2] == {"role": "assistant", "content": "Норм, малыш. Кофе пью."}
    assert msgs[3] == {"role": "user", "content": "Что собираешься делать?"}
    assert msgs[4] == {"role": "assistant", "content": "Думаю про задачу."}
    assert msgs[5] == {"role": "user", "content": "А как у тебя сейчас?"}


async def test_prior_messages_with_invalid_entries_filtered(substrate: Substrate) -> None:
    """Bad entries (wrong role, not a dict) are silently dropped instead
    of crashing the session."""
    stream = ContinuityStream(substrate)
    provider = _CapturingProvider(["[DONE]"])
    history = [
        {"role": "user", "content": "ok"},
        {"role": "system", "content": "should be dropped"},  # invalid role
        "not a dict",                                          # not a dict
        {"role": "assistant", "content": "valid"},
    ]
    await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="hi",
        prior_messages=history,
        max_steps=10,
        max_seconds=5.0,
        purpose="test",
    )
    msgs = provider.last_messages
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "ok"}
    assert msgs[2] == {"role": "assistant", "content": "valid"}
    assert msgs[3] == {"role": "user", "content": "hi"}


async def test_prior_messages_none_keeps_old_behaviour(substrate: Substrate) -> None:
    """Without prior_messages, session messages list is system + initial only."""
    stream = ContinuityStream(substrate)
    provider = _CapturingProvider(["[DONE]"])
    await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="hello",
        max_steps=10,
        max_seconds=5.0,
        purpose="test",
    )
    msgs = provider.last_messages
    # System + user_text only (budget warning only fires at step >= max_steps-2).
    assert len(msgs) == 2, [m["role"] for m in msgs]
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "hello"}
