"""Tests for InternalProcess._should_force_selfmod_track.

Background: when Ivan has a long-running task (e.g. sweetcow recon, 25+
active sessions), every active-session tick picks up that task and never
does self-improvement. Sonya stops applying selfmod proposals.

Fix: force selfmod track when no self_mod.applied event in the last 3
days (Ivan's directive 26.05). Legacy 8-session fallback kept for cases
where time-window check fails.
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.pending import PendingIntentionStore
from sonya.state.substrate import Substrate
from sonya.subject.internal_loop import InternalProcess


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def _build_loop(substrate: Substrate) -> InternalProcess:
    return InternalProcess(
        stream=ContinuityStream(substrate),
        intention_store=PendingIntentionStore(substrate),
        substrate=substrate,
        provider=None,
    )


def _seed_event(sub: Substrate, kind: str, *, minutes_ago: int = 5) -> None:
    when = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    sub.connection.execute(
        "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (kind, None, _json.dumps({}), when),
    )
    sub.connection.commit()


# --- Time-based primary rule ---


def test_force_when_no_apply_in_3_days_and_sessions_exist(
    substrate: Substrate,
) -> None:
    """No self_mod.applied in last 3 days + at least one active session →
    force selfmod track."""
    loop = _build_loop(substrate)
    # Apply was 4 days ago — outside 3-day window
    _seed_event(substrate, "self_mod.applied", minutes_ago=4 * 24 * 60)
    _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=120)
    assert loop._should_force_selfmod_track(substrate) is True


def test_dont_force_when_apply_within_3_days(substrate: Substrate) -> None:
    """Apply 2 days ago = within window → don't force."""
    loop = _build_loop(substrate)
    _seed_event(substrate, "self_mod.applied", minutes_ago=2 * 24 * 60)
    # Even with many sessions, since recent apply exists and we haven't hit
    # the 8-session legacy fallback yet
    for i in range(3):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=200 - i * 30)
    assert loop._should_force_selfmod_track(substrate) is False


def test_force_when_no_apply_ever_but_sessions_exist(substrate: Substrate) -> None:
    """Fresh deploy → no apply has ever happened → force as soon as one
    active session has run."""
    loop = _build_loop(substrate)
    _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=120)
    assert loop._should_force_selfmod_track(substrate) is True


def test_dont_force_on_empty_stream(substrate: Substrate) -> None:
    """Brand new substrate, no events at all → don't force (boot-time guard)."""
    loop = _build_loop(substrate)
    assert loop._should_force_selfmod_track(substrate) is False


# --- Legacy 8-session fallback ---


def test_legacy_fallback_force_at_8_sessions(substrate: Substrate) -> None:
    """When recent apply (within 3 days) BUT 8+ sessions accumulated since
    it — fallback rule fires."""
    loop = _build_loop(substrate)
    # Apply was 1 day ago (within 3-day window — primary rule says don't force)
    _seed_event(substrate, "self_mod.applied", minutes_ago=24 * 60)
    # 8 active sessions after the apply
    for i in range(8):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=60 - i * 5)
    assert loop._should_force_selfmod_track(substrate) is True


def test_legacy_fallback_silent_at_7_sessions(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    _seed_event(substrate, "self_mod.applied", minutes_ago=24 * 60)
    for i in range(7):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=60 - i * 5)
    assert loop._should_force_selfmod_track(substrate) is False


def test_agent_session_complete_also_counts_for_legacy(substrate: Substrate) -> None:
    """Both agent_session_outcome and agent_session_complete count toward
    the legacy 8-session fallback."""
    loop = _build_loop(substrate)
    _seed_event(substrate, "self_mod.applied", minutes_ago=24 * 60)
    for i in range(4):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=200 - i * 10)
    for i in range(4):
        _seed_event(substrate, "internal.agent_session_complete", minutes_ago=100 - i * 10)
    # 4 + 4 = 8 active sessions
    assert loop._should_force_selfmod_track(substrate) is True
