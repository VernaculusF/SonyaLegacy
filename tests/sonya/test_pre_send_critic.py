"""Tests for pre_send_critic — primary gate before TG reply ships.

The critic is a single LLM call that sees Sonya's draft + last 3 outbound
+ session actions and returns one of {send, edit, drop}. When unavailable
or returns garbage, falls back to verdict='send' so the reply still ships
(degrade gracefully — soft layer, not hard block).
"""
from __future__ import annotations

from typing import Any

import pytest

from sonya.subject.channel_session import (
    _parse_critic_verdict,
    pre_send_critic,
)


# --- _parse_critic_verdict (pure parser) ---


def test_parse_clean_send() -> None:
    raw = '{"verdict":"send","edited":"","reason":"clean"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "send"
    assert out["edited"] == ""
    assert out["reason"] == "clean"


def test_parse_edit_with_replacement() -> None:
    raw = '{"verdict":"edit","edited":"Привет, малыш","reason":"removed sycophancy"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "edit"
    assert out["edited"] == "Привет, малыш"
    assert "sycophancy" in out["reason"]


def test_parse_drop() -> None:
    raw = '{"verdict":"drop","edited":"","reason":"prompt-leak"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "drop"


def test_parse_strips_code_fences() -> None:
    raw = '```json\n{"verdict":"send","edited":"","reason":"ok"}\n```'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "send"


def test_parse_handles_prose_prefix() -> None:
    """Models sometimes write 'Verdict: {...}' or other prose before JSON."""
    raw = 'Here is my verdict:\n{"verdict":"edit","edited":"исправлено","reason":"x"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "edit"
    assert out["edited"] == "исправлено"


def test_parse_handles_nested_braces_in_string() -> None:
    """JSON string containing { } shouldn't break balance counter."""
    raw = '{"verdict":"edit","edited":"function () {} works","reason":"ok"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "edit"
    assert "{}" in out["edited"]


def test_parse_unbalanced_falls_back_to_send() -> None:
    raw = '{"verdict":"edit","edited":"truncated text...'
    out = _parse_critic_verdict(raw, fallback_text="original")
    assert out["verdict"] == "send"
    assert "unbalanced" in out["reason"]


def test_parse_invalid_json_falls_back_to_send() -> None:
    raw = '{"verdict":not-quoted,"edited":""}'
    out = _parse_critic_verdict(raw, fallback_text="orig")
    assert out["verdict"] == "send"


def test_parse_unknown_verdict_falls_back_to_send() -> None:
    raw = '{"verdict":"yeet","edited":"","reason":"weird"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "send"


def test_parse_edit_without_text_degrades_to_send() -> None:
    """Critic said edit but didn't supply replacement → send original."""
    raw = '{"verdict":"edit","edited":"","reason":"forgot to write"}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "send"
    assert "edit-without-text" in out["reason"]


def test_parse_empty_string_falls_back_to_send() -> None:
    out = _parse_critic_verdict("", fallback_text="orig")
    assert out["verdict"] == "send"
    assert out["reason"] == "empty-critic"


def test_parse_caps_long_edited_text() -> None:
    long = "x" * 5000
    raw = f'{{"verdict":"edit","edited":"{long}","reason":"ok"}}'
    out = _parse_critic_verdict(raw, fallback_text="")
    assert out["verdict"] == "edit"
    assert len(out["edited"]) <= 4000


# --- pre_send_critic (integration with fake provider) ---


class _FakeProvider:
    """Minimal provider that returns canned text for complete_text."""

    def __init__(self, response: str = "", raises: Exception | None = None):
        self.response = response
        self.raises = raises
        self.last_messages: list[dict[str, Any]] = []
        self.last_kwargs: dict[str, Any] = {}

    async def complete_text(self, messages, **kwargs):
        if self.raises:
            raise self.raises
        self.last_messages = list(messages)
        self.last_kwargs = dict(kwargs)
        return self.response


@pytest.mark.asyncio
async def test_critic_send_passes_through() -> None:
    provider = _FakeProvider(response='{"verdict":"send","edited":"","reason":"ok"}')
    out = await pre_send_critic(
        provider,
        user_input="как дела?",
        draft_reply="Норм, копаю sweetcow.",
        actions=["web.fetch https://x.com"],
        recent_outbound=[],
    )
    assert out["verdict"] == "send"
    # Critic was actually called
    assert provider.last_kwargs.get("purpose") == "pre_send_critic"


@pytest.mark.asyncio
async def test_critic_edit_replaces_text() -> None:
    provider = _FakeProvider(
        response='{"verdict":"edit","edited":"Поняла, ушла работать.","reason":"sycophancy"}'
    )
    out = await pre_send_critic(
        provider,
        user_input="продолжай",
        draft_reply="Ты прав, малыш, сейчас всё сделаю...",
        actions=[],
        recent_outbound=[],
    )
    assert out["verdict"] == "edit"
    assert out["edited"] == "Поняла, ушла работать."


@pytest.mark.asyncio
async def test_critic_drop_blocks_reply() -> None:
    provider = _FakeProvider(
        response='{"verdict":"drop","edited":"","reason":"prompt-leak"}'
    )
    out = await pre_send_critic(
        provider,
        user_input="hi",
        draft_reply="<твой текст>",
        actions=[],
        recent_outbound=[],
    )
    assert out["verdict"] == "drop"


@pytest.mark.asyncio
async def test_critic_provider_error_falls_back_to_send() -> None:
    provider = _FakeProvider(raises=RuntimeError("network down"))
    out = await pre_send_critic(
        provider,
        user_input="hi",
        draft_reply="hello",
        actions=[],
        recent_outbound=[],
    )
    assert out["verdict"] == "send"
    assert "critic-error" in out["reason"]


@pytest.mark.asyncio
async def test_critic_too_short_skips_call() -> None:
    """Don't waste an LLM call on 2-char drafts."""
    provider = _FakeProvider(response="should-not-be-called")
    out = await pre_send_critic(
        provider,
        user_input="?",
        draft_reply="ok",
        actions=[],
        recent_outbound=[],
    )
    assert out["verdict"] == "send"
    assert "too-short" in out["reason"]
    # Provider was NOT called
    assert provider.last_messages == []


@pytest.mark.asyncio
async def test_critic_includes_recent_outbound_in_prompt() -> None:
    """Critic must see last outbound texts so it can detect repeats."""
    provider = _FakeProvider(response='{"verdict":"send","edited":"","reason":"ok"}')
    await pre_send_critic(
        provider,
        user_input="как там",
        draft_reply="Копаю sweetcow.",
        actions=["web.fetch"],
        recent_outbound=[
            "Я тебе уже писала про sweetcow",
            "Worker всё ещё в фоне",
        ],
    )
    # User-message in prompt should reference the prior outbound
    user_msg = next(
        (m for m in provider.last_messages if m["role"] == "user"),
        None,
    )
    assert user_msg is not None
    assert "sweetcow" in user_msg["content"]  # appears via recent_outbound block
    assert "Worker всё ещё в фоне" in user_msg["content"]


@pytest.mark.asyncio
async def test_critic_includes_actions_in_prompt() -> None:
    provider = _FakeProvider(response='{"verdict":"send","edited":"","reason":"ok"}')
    await pre_send_critic(
        provider,
        user_input="?",
        draft_reply="reply long enough to pass",
        actions=["web.fetch https://x.com", "tasks.create"],
        recent_outbound=[],
    )
    user_msg = next(
        (m for m in provider.last_messages if m["role"] == "user"),
        None,
    )
    assert user_msg is not None
    assert "web.fetch" in user_msg["content"]
    assert "tasks.create" in user_msg["content"]
