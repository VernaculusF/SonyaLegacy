from __future__ import annotations

import asyncio

import pytest

from sonya.runtime import Event, EventBus


@pytest.mark.asyncio
async def test_publish_to_typed_subscriber() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(ev: Event) -> None:
        received.append(ev)

    bus.subscribe("subject.test", handler)
    await bus.publish(Event(event_type="subject.test", payload={"x": 1}))

    assert len(received) == 1
    assert received[0].event_type == "subject.test"
    assert received[0].payload == {"x": 1}


@pytest.mark.asyncio
async def test_subscriber_does_not_receive_other_event_types() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(ev: Event) -> None:
        received.append(ev)

    bus.subscribe("subject.a", handler)
    await bus.publish(Event(event_type="subject.b"))

    assert received == []


@pytest.mark.asyncio
async def test_async_subscribers_receive_concurrently() -> None:
    bus = EventBus()
    order: list[str] = []

    async def slow(ev: Event) -> None:
        await asyncio.sleep(0.02)
        order.append("slow")

    async def fast(ev: Event) -> None:
        order.append("fast")

    bus.subscribe("e", slow)
    bus.subscribe("e", fast)
    await bus.publish(Event(event_type="e"))

    # fast should land first because slow yields.
    assert order == ["fast", "slow"]


@pytest.mark.asyncio
async def test_unsubscribe_works() -> None:
    bus = EventBus()
    received: list[Event] = []

    async def handler(ev: Event) -> None:
        received.append(ev)

    h = bus.subscribe("e", handler)
    bus.unsubscribe(h)
    await bus.publish(Event(event_type="e"))

    assert received == []
    assert bus.subscriber_count("e") == 0


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_is_noop() -> None:
    bus = EventBus()
    await bus.publish(Event(event_type="nobody.is.listening"))
