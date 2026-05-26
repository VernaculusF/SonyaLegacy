"""Tests for split between ``outgoing.telegram_initiative`` (unsolicited)
and ``outgoing.telegram_progress`` (chat.tell_ivan from a tool / worker
progress) in continuity events.

Earlier ALL outbound got kind=outgoing.telegram_initiative which made:
  - escalating quiet (1 unanswered initiative → 2× window) fire on
    ordinary tool progress messages
  - cross-session dedup miss real near-duplicates
  - admin filter conflate the two
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.channels.base import OutgoingMessage
from sonya.channels.registry import ChannelRegistry
from sonya.initiative.outbound import OutboundGate
from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate


class _FakeChannel:
    name = "telegram"

    def __init__(self):
        self.sent: list[tuple[str, str]] = []
        self.is_running = True

    async def start(self, deps=None) -> None: ...
    async def stop(self) -> None: ...

    async def send(self, chat_id: str, message: OutgoingMessage):
        self.sent.append((chat_id, message.text))


@pytest.fixture
def env(tmp_path: Path):
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    stream = ContinuityStream(sub)
    registry = ChannelRegistry()
    registry.register(_FakeChannel())  # type: ignore[arg-type]
    yield sub, stream, registry
    sub.close()


def _make_gate(env_):
    sub, stream, registry = env_
    return OutboundGate(
        registry=registry,
        stream=stream,
        target_tg_chat_id="123",
        max_per_day=10,
        min_quiet_minutes=0,
        substrate=sub,
    )


async def test_tool_path_emits_progress_kind(env) -> None:
    """send_via_tool with default reason='tool' → outgoing.telegram_progress."""
    sub, stream, _ = env
    gate = _make_gate(env)
    await gate.send_via_tool("ack from a tool")
    events = list(stream.read_since(0))
    kinds = [e.kind for e in events]
    assert "outgoing.telegram_progress" in kinds
    assert "outgoing.telegram_initiative" not in kinds


async def test_idle_thought_marker_emits_initiative_kind(env) -> None:
    """maybe_send_from_thought with [SEND_TO_IVAN: ...] → outgoing.telegram_initiative."""
    sub, stream, _ = env
    gate = _make_gate(env)
    await gate.maybe_send_from_thought("[SEND_TO_IVAN: hello, just thinking of you]")
    events = list(stream.read_since(0))
    kinds = [e.kind for e in events]
    assert "outgoing.telegram_initiative" in kinds
    assert "outgoing.telegram_progress" not in kinds


async def test_unanswered_streak_ignores_progress(env) -> None:
    """4 progress messages should NOT trigger escalating quiet — only real
    initiatives count toward the streak."""
    sub, stream, _ = env
    gate = _make_gate(env)
    for i in range(4):
        await gate.send_via_tool(f"progress msg {i}")
    # Streak counter for real initiatives stays at 0
    assert gate._unanswered_initiatives_streak() == 0


async def test_unanswered_streak_counts_initiative(env) -> None:
    """Idle [SEND_TO_IVAN: ...] does count toward the streak."""
    sub, stream, _ = env
    gate = _make_gate(env)
    msgs = [
        "[SEND_TO_IVAN: малыш, я закончила анализ ladygunn, нашла открытый wp-admin]",
        "[SEND_TO_IVAN: ещё хочу сказать про новый план — buy XYZ token tomorrow morning]",
    ]
    for m in msgs:
        result = await gate.maybe_send_from_thought(m)
        assert result is not None and not result.startswith("[BLOCKED]"), result
    assert gate._unanswered_initiatives_streak() == 2


async def test_progress_resets_quiet_window(env) -> None:
    """Tool-progress message updates 'last activity' so the quiet window
    sees recent activity, not silence."""
    sub, stream, _ = env
    gate = _make_gate(env)
    # Initially no recent activity
    assert gate._latest_tg_seconds_ago() is None
    await gate.send_via_tool("progress")
    # Now there's activity — non-None elapsed
    elapsed = gate._latest_tg_seconds_ago()
    assert elapsed is not None
    assert elapsed >= 0
