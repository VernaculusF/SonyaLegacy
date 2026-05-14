from __future__ import annotations

from pathlib import Path

import pytest

from sonya.runtime import DoubleStartError, Event, EventBus, Lifecycle, LifecycleState
from sonya.state import ContinuityStream, Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


@pytest.mark.asyncio
async def test_lifecycle_emits_started_event(substrate: Substrate) -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(ev: Event) -> None:
        received.append(ev)

    bus.subscribe("subject.lifecycle.started", handler)
    lc = Lifecycle(substrate=substrate, event_bus=bus)
    await lc.start()

    assert lc.state is LifecycleState.STARTED
    assert any(ev.event_type == "subject.lifecycle.started" for ev in received)


@pytest.mark.asyncio
async def test_lifecycle_records_continuity_events(substrate: Substrate) -> None:
    bus = EventBus()
    lc = Lifecycle(substrate=substrate, event_bus=bus)
    await lc.start()
    await lc.request_stop()

    kinds = [ev.kind for ev in ContinuityStream(substrate).read_since(0)]
    assert "subject.lifecycle.started" in kinds
    assert "subject.lifecycle.stopped" in kinds


@pytest.mark.asyncio
async def test_lifecycle_request_stop_emits_stopping_then_stopped(
    substrate: Substrate,
) -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(ev: Event) -> None:
        received.append(ev)

    for kind in (
        "subject.lifecycle.started",
        "subject.lifecycle.stopping",
        "subject.lifecycle.stopped",
    ):
        bus.subscribe(kind, handler)

    lc = Lifecycle(substrate=substrate, event_bus=bus)
    await lc.start()
    await lc.request_stop()

    types = [ev.event_type for ev in received]
    assert types == [
        "subject.lifecycle.started",
        "subject.lifecycle.stopping",
        "subject.lifecycle.stopped",
    ]
    assert lc.state is LifecycleState.STOPPED


@pytest.mark.asyncio
async def test_double_start_raises(substrate: Substrate) -> None:
    bus = EventBus()
    lc = Lifecycle(substrate=substrate, event_bus=bus)
    await lc.start()
    with pytest.raises(DoubleStartError):
        await lc.start()


@pytest.mark.asyncio
async def test_wait_for_stop_completes_after_request_stop(
    substrate: Substrate,
) -> None:
    import asyncio

    bus = EventBus()
    lc = Lifecycle(substrate=substrate, event_bus=bus)
    await lc.start()

    waiter = asyncio.create_task(lc.wait_for_stop())
    await lc.request_stop()
    await asyncio.wait_for(waiter, timeout=1)
