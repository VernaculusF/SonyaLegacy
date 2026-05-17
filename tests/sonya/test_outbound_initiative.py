"""Tests for Этап D — OutboundGate (initiative)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sonya.channels.base import OutgoingMessage
from sonya.channels.registry import ChannelRegistry
from sonya.initiative.outbound import OutboundGate
from sonya.state import Substrate
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream


class _FakeChannel:
    name = "telegram"

    def __init__(self):
        self.sent = []
        self.fail = False
        self.is_running = True

    async def start(self, deps):
        self.is_running = True

    async def stop(self):
        self.is_running = False

    async def send(self, chat_id, message):
        if self.fail:
            raise RuntimeError("simulated send failure")
        self.sent.append((chat_id, message.text))


@pytest.fixture()
def env(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    stream = ContinuityStream(sub)
    registry = ChannelRegistry()
    fake = _FakeChannel()
    registry.register(fake)
    yield sub, stream, registry, fake
    sub.close()


def _make_gate(env, *, max_per_day=5, min_quiet=1, target="123"):
    _, stream, registry, _ = env
    return OutboundGate(
        registry=registry,
        stream=stream,
        target_tg_chat_id=target,
        max_per_day=max_per_day,
        min_quiet_minutes=min_quiet,
    )


async def test_send_via_tool_dispatches_when_no_recent_tg(env) -> None:
    _, stream, _, fake = env
    gate = _make_gate(env)
    out = await gate.send_via_tool("hello, ivan")
    assert "[OK] sent" in out
    assert fake.sent == [("123", "hello, ivan")]
    # Continuity event recorded
    events = list(stream.read_since(0))
    assert any(e.kind == "outgoing.telegram_initiative" for e in events)


async def test_send_blocked_when_quiet_window_not_passed(env) -> None:
    sub, stream, _, _ = env
    # Fresh outgoing tg event 0 minutes ago
    stream.append(ContinuityEvent(
        kind="incoming.telegram_message",
        payload={"text": "ping"},
    ))
    gate = _make_gate(env, min_quiet=120)
    # Default tool behaviour now bypasses quiet-window (Sonya is in active dialog).
    # Use ignore_quiet=False to assert the gate still works for that mode.
    out = await gate.send_via_tool("hi", ignore_quiet=False)
    assert "[BLOCKED]" in out
    assert "quiet window" in out


async def test_daily_cap(env) -> None:
    gate = _make_gate(env, max_per_day=2, min_quiet=0)
    a = await gate.send_via_tool("one")
    b = await gate.send_via_tool("two")
    c = await gate.send_via_tool("three")
    assert "[OK] sent" in a
    assert "[OK] sent" in b
    assert "[BLOCKED]" in c
    assert "daily cap" in c


async def test_no_target_blocks(env) -> None:
    gate = _make_gate(env, target="")
    out = await gate.send_via_tool("hi")
    assert "[BLOCKED]" in out
    assert "no SONYA_PRIMARY_USER_TG_ID" in out


async def test_empty_text_rejected(env) -> None:
    gate = _make_gate(env)
    out = await gate.send_via_tool("   ")
    assert "[ERROR]" in out


async def test_send_failure_records_event(env) -> None:
    _, stream, _, fake = env
    fake.fail = True
    gate = _make_gate(env)
    out = await gate.send_via_tool("hi")
    # Registry swallows exceptions and returns False, so the gate sees a soft
    # failure (no [OK]) and no success event is recorded.
    assert "[OK]" not in out
    events = list(stream.read_since(0))
    assert not any(e.kind == "outgoing.telegram_initiative" for e in events)


async def test_marker_in_thought_triggers_send(env) -> None:
    _, stream, _, fake = env
    gate = _make_gate(env)
    thought = "Думаю об Иване... [SEND_TO_IVAN: Привет, скучаю] И ещё подумаю про работу."
    out = await gate.maybe_send_from_thought(thought)
    assert out is not None
    assert "[OK] sent" in out
    assert fake.sent == [("123", "Привет, скучаю")]


async def test_marker_absent_returns_none(env) -> None:
    gate = _make_gate(env)
    out = await gate.maybe_send_from_thought("Просто думаю, никаких маркеров.")
    assert out is None


async def test_marker_blocked_logs_event(env) -> None:
    _, stream, _, _ = env
    gate = _make_gate(env, max_per_day=0)
    out = await gate.maybe_send_from_thought("[SEND_TO_IVAN: hi]")
    assert "[BLOCKED]" in out
    events = list(stream.read_since(0))
    assert any(e.kind == "internal.initiative_blocked" for e in events)
