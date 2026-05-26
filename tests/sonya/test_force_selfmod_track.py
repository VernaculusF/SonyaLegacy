"""Tests for InternalProcess._should_force_selfmod_track.

Background: when Ivan has a long-running task (e.g. sweetcow recon, 25+
active sessions), every active-session tick picks up that task and never
does self-improvement. Sonya stops applying selfmod proposals.

Fix: every Nth active session (N=4) skips Ivan-task pickup and is seeded
with selfmod-prompt instead. Counter is implicit — count active-session
outcomes since the last self_mod.applied event.
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


def test_force_selfmod_when_4_active_sessions_since_last_apply(
    substrate: Substrate,
) -> None:
    """4 active-session outcomes since last self_mod.applied → force selfmod."""
    loop = _build_loop(substrate)
    _seed_event(substrate, "self_mod.applied", minutes_ago=600)
    for i in range(4):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=120 - i * 30)
    assert loop._should_force_selfmod_track(substrate) is True


def test_dont_force_selfmod_when_3_active_sessions(
    substrate: Substrate,
) -> None:
    """3 active sessions = below threshold."""
    loop = _build_loop(substrate)
    _seed_event(substrate, "self_mod.applied", minutes_ago=600)
    for i in range(3):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=120 - i * 30)
    assert loop._should_force_selfmod_track(substrate) is False


def test_dont_force_when_recent_apply(substrate: Substrate) -> None:
    """Apply just happened → counter resets."""
    loop = _build_loop(substrate)
    # 5 sessions, then an apply, then 1 more
    for i in range(5):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=200 - i * 10)
    _seed_event(substrate, "self_mod.applied", minutes_ago=120)
    _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=60)
    # Only 1 session since last apply
    assert loop._should_force_selfmod_track(substrate) is False


def test_force_selfmod_when_no_apply_ever(substrate: Substrate) -> None:
    """If Sonya has never self-applied AND there are 4+ active sessions,
    force selfmod track. Without this, a fresh deploy never triggers
    self-improvement."""
    loop = _build_loop(substrate)
    for i in range(5):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=200 - i * 30)
    assert loop._should_force_selfmod_track(substrate) is True


def test_no_force_on_empty_stream(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    assert loop._should_force_selfmod_track(substrate) is False


def test_agent_session_complete_also_counts(substrate: Substrate) -> None:
    """Some paths emit agent_session_complete instead of agent_session_outcome.
    Both should count toward the threshold."""
    loop = _build_loop(substrate)
    for i in range(2):
        _seed_event(substrate, "internal.agent_session_outcome", minutes_ago=300 - i * 30)
    for i in range(2):
        _seed_event(substrate, "internal.agent_session_complete", minutes_ago=200 - i * 30)
    # 2 + 2 = 4 active sessions, no apply
    assert loop._should_force_selfmod_track(substrate) is True
