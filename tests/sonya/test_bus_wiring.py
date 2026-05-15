from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sonya.runtime.events import Event, EventBus
from sonya.state import ContinuityEvent, ContinuityStream, SubjectState, SubjectStateStore, Substrate
from sonya.subject.bus_wiring import BusAwareContinuityStream, BusAwareSubjectStateStore


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


async def test_append_publishes_continuity_event_added(substrate: Substrate) -> None:
    bus = EventBus()
    stream = ContinuityStream(substrate)
    wrapped = BusAwareContinuityStream(stream, bus)

    received: list[Event] = []
    bus.subscribe("continuity.event_added", lambda e: _capture(received, e))

    result = wrapped.append(ContinuityEvent(kind="test.event", principal_id="ivan"))

    await asyncio.sleep(0.05)

    assert result.seq >= 1
    assert len(received) == 1
    assert received[0].payload["kind"] == "test.event"
    assert received[0].payload["seq"] == result.seq


async def test_save_publishes_subject_state_changed(substrate: Substrate) -> None:
    bus = EventBus()
    store = SubjectStateStore(substrate)
    wrapped = BusAwareSubjectStateStore(store, bus)

    received: list[Event] = []
    bus.subscribe("subject.state_changed", lambda e: _capture(received, e))

    state = SubjectState(active_principal_id="ivan", active_channels=("telegram",))
    wrapped.save(state)

    await asyncio.sleep(0.05)

    assert len(received) == 1
    assert received[0].payload["active_principal_id"] == "ivan"


async def test_wrapped_stream_still_persists(substrate: Substrate) -> None:
    bus = EventBus()
    stream = ContinuityStream(substrate)
    wrapped = BusAwareContinuityStream(stream, bus)

    wrapped.append(ContinuityEvent(kind="persist.test"))

    events = list(stream.read_since(0))
    assert len(events) == 1
    assert events[0].kind == "persist.test"


async def test_wrapped_store_still_persists(substrate: Substrate) -> None:
    bus = EventBus()
    store = SubjectStateStore(substrate)
    wrapped = BusAwareSubjectStateStore(store, bus)

    wrapped.save(SubjectState(active_principal_id="test"))

    loaded = store.load()
    assert loaded.active_principal_id == "test"


async def _capture(lst: list, event: Event) -> None:
    lst.append(event)
