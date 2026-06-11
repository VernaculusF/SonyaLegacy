from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sonya.state import ContinuityStream, Substrate
from sonya.state.pending import PendingIntentionStore
from sonya.subject.internal_loop import HomeostasisCounters, InternalProcess


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_homeostasis_counters_tick_increments() -> None:
    c = HomeostasisCounters(loneliness_rate=0.1, curiosity_rate=0.05, threshold=0.5)
    crossed = c.tick()
    assert c.loneliness == pytest.approx(0.1)
    assert c.curiosity == pytest.approx(0.05)
    assert crossed == []


def test_homeostasis_threshold_crossing() -> None:
    c = HomeostasisCounters(loneliness_rate=0.4, threshold=0.7)
    c.loneliness = 0.65
    crossed = c.tick()
    assert "loneliness" in crossed
    assert c.loneliness >= 0.7


def test_homeostasis_reset() -> None:
    c = HomeostasisCounters()
    c.loneliness = 0.9
    c.reset("loneliness")
    assert c.loneliness == 0.0


async def test_internal_process_emits_on_idle_timeout(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(
        stream, store, idle_interval_seconds=0.05, tick_interval_seconds=0.02
    )

    await proc.start()
    await asyncio.sleep(0.15)
    await proc.stop()

    events = list(stream.read_since(0))
    cognitive = [e for e in events if e.kind == "internal.cognitive_tick"]
    assert len(cognitive) >= 2  # boot + at least one idle
    # Find one with idle_timeout trigger (skip boot)
    idle_events = [e for e in cognitive if "idle_timeout" in e.payload.get("triggers", [])]
    assert len(idle_events) >= 1


async def test_internal_process_emits_on_threshold_crossing(
    substrate: Substrate,
) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(
        stream, store, idle_interval_seconds=999, tick_interval_seconds=0.02
    )
    # Pre-set counter close to threshold
    proc.counters.loneliness = 0.69
    proc.counters.loneliness_rate = 0.02

    await proc.start()
    await asyncio.sleep(0.08)
    await proc.stop()

    events = list(stream.read_since(0))
    cognitive = [e for e in events if e.kind == "internal.cognitive_tick"]
    # Find threshold crossing event (skip boot)
    threshold_events = [e for e in cognitive if any("threshold:" in t for t in e.payload.get("triggers", []))]
    assert len(threshold_events) >= 1


async def test_internal_process_detects_overdue_intention(
    substrate: Substrate,
) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    # Create intention with past deadline
    store.create(
        description="overdue task",
        deadline="2020-01-01T00:00:00+00:00",
    )

    proc = InternalProcess(
        stream, store, idle_interval_seconds=0.03, tick_interval_seconds=0.02
    )

    await proc.start()
    await asyncio.sleep(0.1)
    await proc.stop()

    events = list(stream.read_since(0))
    # M-5 fix: overdue intentions now appear in cognitive_tick.triggers, not as separate events
    overdue_in_triggers = [
        e for e in events
        if e.kind == "internal.cognitive_tick"
        and any(t.startswith("deadline_overdue:") for t in e.payload.get("triggers", []))
    ]
    assert len(overdue_in_triggers) >= 1


async def test_internal_process_stops_cleanly(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(
        stream, store, idle_interval_seconds=999, tick_interval_seconds=0.02
    )

    await proc.start()
    await asyncio.sleep(0.05)
    await proc.stop()

    seq_after_stop = stream.latest_seq()
    await asyncio.sleep(0.05)
    assert stream.latest_seq() == seq_after_stop  # no new events after stop


async def test_notify_external_event_resets_loneliness(
    substrate: Substrate,
) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(
        stream, store, idle_interval_seconds=999, tick_interval_seconds=0.02
    )
    proc.counters.loneliness = 0.5

    await proc.start()
    proc.notify_external_event()
    assert proc.counters.loneliness == 0.0
    await proc.stop()


async def test_tick_count_increments(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(
        stream, store, idle_interval_seconds=999, tick_interval_seconds=0.02
    )

    await proc.start()
    await asyncio.sleep(0.08)
    await proc.stop()

    assert proc.tick_count >= 2


def test_pending_ivan_message_detects_unanswered(substrate: Substrate) -> None:
    """An incoming atrium dialog with no later reply is 'pending'."""
    from sonya.state import ContinuityEvent
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(stream, store)

    stream.append(ContinuityEvent(
        kind="incoming.atrium_dialog",
        channel="dialog",
        principal_id="ivan",
        payload={"text": "привет, ты тут?", "media_kind": None},
    ))
    pending = proc._pending_ivan_message(substrate)
    assert pending is not None
    assert pending["text"] == "привет, ты тут?"


def test_pending_ivan_message_none_after_reply(substrate: Substrate) -> None:
    """Once she replies (outgoing event with higher seq), nothing pending."""
    from sonya.state import ContinuityEvent
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(stream, store)

    stream.append(ContinuityEvent(
        kind="incoming.atrium_dialog",
        channel="dialog",
        principal_id="ivan",
        payload={"text": "привет"},
    ))
    stream.append(ContinuityEvent(
        kind="outgoing.dialog",
        channel="dialog",
        payload={"text": "привет, малыш"},
    ))
    assert proc._pending_ivan_message(substrate) is None


def test_pending_ivan_message_empty_stream(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    proc = InternalProcess(stream, store)
    assert proc._pending_ivan_message(substrate) is None


def test_subagent_completion_poll_emits_each_new_completion_once(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    store = PendingIntentionStore(substrate)
    substrate.connection.execute(
        "INSERT INTO subagent_tasks(subagent_id, task, status, result, created_at, completed_at) "
        "VALUES ('old-done', 'old', 'done', 'old result', datetime('now'), datetime('now'))"
    )
    substrate.connection.commit()
    proc = InternalProcess(stream, store, substrate=substrate)

    proc._check_subagent_completions()
    assert substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events WHERE kind = 'subagent.complete'"
    ).fetchone()[0] == 0

    substrate.connection.execute(
        "INSERT INTO subagent_tasks(subagent_id, task, status, result, created_at, completed_at) "
        "VALUES ('new-done', 'new', 'done', 'new result', datetime('now'), datetime('now'))"
    )
    substrate.connection.commit()
    proc._check_subagent_completions()
    proc._check_subagent_completions()

    rows = substrate.connection.execute(
        "SELECT payload_json FROM continuity_events WHERE kind = 'subagent.complete'"
    ).fetchall()
    assert len(rows) == 1
    assert "new-done" in rows[0][0]
