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
    assert len(cognitive) >= 1
    assert "idle_timeout" in cognitive[0].payload["triggers"]


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
    assert len(cognitive) >= 1
    triggers = cognitive[0].payload["triggers"]
    assert any("threshold:loneliness" in t for t in triggers)


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
    overdue_events = [e for e in events if e.kind == "internal.intention_overdue"]
    assert len(overdue_events) >= 1


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

    assert proc.tick_count >= 3
