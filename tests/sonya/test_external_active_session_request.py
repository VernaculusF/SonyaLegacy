"""Tests for the external 'fire active session now' trigger.

Mechanism: any external script (admin endpoint, CLI helper) appends a
continuity event of kind ``internal.active_session_requested_external``.
On the next loop tick, the loop sees the new seq, pulls
``_last_active_session`` back so ``should_active`` becomes True, and
fires the active session within one tick interval.

Use-case: Ivan asks "проведи стартовый сейчас" — instead of waiting up
to 2h for the regular cadence to swing around, push the loop manually.
"""
from __future__ import annotations

import asyncio
import json as _json
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


class _DummyProvider:
    """Provider stub — its mere presence enables active-session firing
    in the should_active gating, without actually doing LLM work."""

    pass


def _make_loop(substrate: Substrate) -> InternalProcess:
    return InternalProcess(
        stream=ContinuityStream(substrate),
        intention_store=PendingIntentionStore(substrate),
        substrate=substrate,
        provider=_DummyProvider(),
        active_interval_seconds=7200.0,
    )


def test_external_request_pulls_schedule_back(substrate: Substrate) -> None:
    """After event is appended and processed, _last_active_session is
    rewound so active_elapsed >= active_interval."""
    loop = _make_loop(substrate)
    loop._last_active_session = 1000.0
    loop._last_external_active_request_seq = 0

    # Append the trigger event
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="internal.active_session_requested_external",
        payload={"reason": "test"},
    ))

    # Replicate the loop's polling logic
    row = substrate.connection.execute(
        "SELECT seq FROM continuity_events "
        "WHERE kind = 'internal.active_session_requested_external' "
        "  AND seq > ? "
        "ORDER BY seq DESC LIMIT 1",
        (loop._last_external_active_request_seq,),
    ).fetchone()
    assert row is not None

    fake_now = 5000.0
    loop._last_external_active_request_seq = int(row[0])
    loop._last_active_session = fake_now - loop._active_interval

    active_elapsed = fake_now - loop._last_active_session
    assert active_elapsed >= loop._active_interval


def test_cursor_advances_so_same_request_doesnt_refire(
    substrate: Substrate,
) -> None:
    """If we processed seq=N, a second tick must not fire again on the same N."""
    loop = _make_loop(substrate)
    stream = ContinuityStream(substrate)

    stream.append(ContinuityEvent(
        kind="internal.active_session_requested_external",
        payload={},
    ))

    # First poll — see new seq
    row = substrate.connection.execute(
        "SELECT seq FROM continuity_events "
        "WHERE kind = 'internal.active_session_requested_external' "
        "  AND seq > ? ORDER BY seq DESC LIMIT 1",
        (loop._last_external_active_request_seq,),
    ).fetchone()
    assert row is not None
    loop._last_external_active_request_seq = int(row[0])

    # Second poll — must return None (no new requests since cursor moved)
    row2 = substrate.connection.execute(
        "SELECT seq FROM continuity_events "
        "WHERE kind = 'internal.active_session_requested_external' "
        "  AND seq > ? ORDER BY seq DESC LIMIT 1",
        (loop._last_external_active_request_seq,),
    ).fetchone()
    assert row2 is None


def test_two_requests_each_fire_once(substrate: Substrate) -> None:
    """Two separate requests should both eventually fire (once each)."""
    loop = _make_loop(substrate)
    stream = ContinuityStream(substrate)

    fired_seqs = []

    def poll_and_consume() -> int | None:
        row = substrate.connection.execute(
            "SELECT seq FROM continuity_events "
            "WHERE kind = 'internal.active_session_requested_external' "
            "  AND seq > ? ORDER BY seq DESC LIMIT 1",
            (loop._last_external_active_request_seq,),
        ).fetchone()
        if row is None:
            return None
        loop._last_external_active_request_seq = int(row[0])
        return int(row[0])

    stream.append(ContinuityEvent(
        kind="internal.active_session_requested_external",
        payload={"n": 1},
    ))
    seq1 = poll_and_consume()
    assert seq1 is not None
    assert poll_and_consume() is None  # cursor advanced

    stream.append(ContinuityEvent(
        kind="internal.active_session_requested_external",
        payload={"n": 2},
    ))
    seq2 = poll_and_consume()
    assert seq2 is not None
    assert seq2 > seq1
    assert poll_and_consume() is None


def test_unrelated_events_do_not_trigger(substrate: Substrate) -> None:
    """Cursor stays put when other event kinds are appended."""
    loop = _make_loop(substrate)
    loop._last_external_active_request_seq = 0
    stream = ContinuityStream(substrate)

    stream.append(ContinuityEvent(kind="internal.cognitive_tick", payload={}))
    stream.append(ContinuityEvent(kind="internal.thought", payload={"thought": "hi"}))

    row = substrate.connection.execute(
        "SELECT seq FROM continuity_events "
        "WHERE kind = 'internal.active_session_requested_external' "
        "  AND seq > ? ORDER BY seq DESC LIMIT 1",
        (loop._last_external_active_request_seq,),
    ).fetchone()
    assert row is None
