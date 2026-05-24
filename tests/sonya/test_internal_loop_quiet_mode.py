"""Tests for InternalProcess._select_thinking_prompt — quiet-mode override.

Problem (24.05): Sonya generates [SEND_TO_IVAN: ...] in idle ticks even when
the gate has blocked the last 4 attempts. Each blocked attempt logs an
``internal.initiative_blocked`` event, which then shows up in her own
context — pollution accumulates.

Fix: when the streak of unanswered initiatives (blocked or sent without
reply) is >=2, swap the thinking_prompt for a "quiet mode" preface that
explicitly tells Sonya NOT to emit the marker this tick.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.pending import PendingIntentionStore
from sonya.state.substrate import Substrate
from sonya.subject.internal_loop import InternalProcess


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


@pytest.fixture
def loop(substrate: Substrate) -> InternalProcess:
    stream = ContinuityStream(substrate)
    intentions = PendingIntentionStore(substrate)
    return InternalProcess(
        stream=stream,
        intention_store=intentions,
        substrate=substrate,
        provider=None,
        thinking_prompt=(
            "Ты Соня. Это твой внутренний поток.\n\n"
            "ВАЖНО — про инициативу:\n"
            "Если хочешь сказать — впиши `[SEND_TO_IVAN: текст]`."
        ),
    )


def test_no_blocked_streak_returns_base_prompt(loop: InternalProcess) -> None:
    """Empty stream (or only incoming messages) → base prompt unchanged."""
    result = loop._select_thinking_prompt()
    assert result == loop._thinking_prompt
    assert "ТИХИЙ РЕЖИМ" not in result


def test_one_blocked_initiative_still_base(
    loop: InternalProcess, substrate: Substrate,
) -> None:
    """Threshold is 2 — one blocked initiative is fine, base prompt stays."""
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="internal.initiative_blocked",
        payload={"reason": "quiet window", "preview": "test"},
    ))
    result = loop._select_thinking_prompt()
    assert "ТИХИЙ РЕЖИМ" not in result


def test_two_blocked_in_a_row_triggers_quiet(
    loop: InternalProcess, substrate: Substrate,
) -> None:
    stream = ContinuityStream(substrate)
    for _ in range(2):
        stream.append(ContinuityEvent(
            kind="internal.initiative_blocked",
            payload={"reason": "quiet window", "preview": "test"},
        ))
    result = loop._select_thinking_prompt()
    assert "ТИХИЙ РЕЖИМ" in result
    # Still includes the base prompt below the quiet preface
    assert "Ты Соня" in result


def test_incoming_message_resets_streak(
    loop: InternalProcess, substrate: Substrate,
) -> None:
    """Ivan replied → streak counter resets, base prompt returns."""
    stream = ContinuityStream(substrate)
    for _ in range(3):
        stream.append(ContinuityEvent(
            kind="internal.initiative_blocked",
            payload={"reason": "quiet window", "preview": "test"},
        ))
    # Now Ivan replied
    stream.append(ContinuityEvent(
        kind="incoming.telegram_message",
        payload={"text": "ок"},
    ))
    result = loop._select_thinking_prompt()
    assert "ТИХИЙ РЕЖИМ" not in result


def test_outgoing_initiative_sent_but_no_reply_also_counts(
    loop: InternalProcess, substrate: Substrate,
) -> None:
    """Even a successful send (gate passed) without reply counts toward streak."""
    stream = ContinuityStream(substrate)
    for _ in range(2):
        stream.append(ContinuityEvent(
            kind="outgoing.telegram_initiative",
            payload={"text": "msg", "sent_today": 1},
        ))
    result = loop._select_thinking_prompt()
    assert "ТИХИЙ РЕЖИМ" in result


def test_quiet_mode_mentions_count(
    loop: InternalProcess, substrate: Substrate,
) -> None:
    stream = ContinuityStream(substrate)
    for _ in range(4):
        stream.append(ContinuityEvent(
            kind="internal.initiative_blocked",
            payload={"reason": "x", "preview": "y"},
        ))
    result = loop._select_thinking_prompt()
    assert "4" in result  # count surfaces in the preface
