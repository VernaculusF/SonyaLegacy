from __future__ import annotations

import pytest

from sonya.initiative import DriveCounters, InitiativeSignal, OutboundActionProposal, create_proposal_from_signal, create_signal


def test_drive_counters_tick_increments() -> None:
    d = DriveCounters(boredom_rate=0.1, threshold=0.5)
    crossed = d.tick()
    assert d.boredom_analog == pytest.approx(0.1)
    assert crossed == []


def test_drive_threshold_crossing() -> None:
    d = DriveCounters(boredom_rate=0.4, threshold=0.7)
    d.boredom_analog = 0.65
    crossed = d.tick()
    assert "boredom_analog" in crossed


def test_drive_on_external_message_decrements() -> None:
    d = DriveCounters()
    d.boredom_analog = 0.5
    d.relational_focus = 0.4
    d.on_external_message()
    assert d.boredom_analog == pytest.approx(0.2)
    assert d.relational_focus == pytest.approx(0.2)


def test_drive_on_action_completed_decrements() -> None:
    d = DriveCounters()
    d.pending_debt = 0.5
    d.curiosity_analog = 0.3
    d.on_action_completed()
    assert d.pending_debt == pytest.approx(0.2)
    assert d.curiosity_analog == pytest.approx(0.2)


def test_pending_debt_increments_with_intentions() -> None:
    d = DriveCounters(threshold=0.7)
    d.tick(active_intentions_count=3)
    assert d.pending_debt == pytest.approx(0.06)


def test_create_signal() -> None:
    sig = create_signal(kind="drive_threshold_hit", source_drive="boredom_analog", priority=5)
    assert sig.signal_id.startswith("sig-")
    assert sig.kind == "drive_threshold_hit"
    assert sig.priority == 5


def test_create_proposal_from_signal() -> None:
    sig = create_signal(kind="drive_threshold_hit", source_drive="boredom_analog")
    prop = create_proposal_from_signal(sig, action_kind="send_message", target_channel="telegram")
    assert prop.proposal_id.startswith("oprp-")
    assert prop.signal_id == sig.signal_id
    assert prop.action_kind == "send_message"
    assert prop.target_channel == "telegram"
