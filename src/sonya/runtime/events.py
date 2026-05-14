from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Event:
    """Typed runtime event.

    `event_type` follows domain.subject.action convention, e.g. subject.lifecycle.started.
    """

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[Event], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class SubscriptionHandle:
    handle_id: str
    event_type: str


class EventBus:
    """In-process async typed pub/sub.

    Plumbing only: the bus knows nothing about substrate, identity, or planning.
    """

    def __init__(self) -> None:
        self._subs: dict[str, dict[str, Handler]] = {}

    def subscribe(self, event_type: str, handler: Handler) -> SubscriptionHandle:
        handle_id = uuid4().hex
        self._subs.setdefault(event_type, {})[handle_id] = handler
        return SubscriptionHandle(handle_id=handle_id, event_type=event_type)

    def unsubscribe(self, handle: SubscriptionHandle) -> None:
        bucket = self._subs.get(handle.event_type)
        if not bucket:
            return
        bucket.pop(handle.handle_id, None)
        if not bucket:
            self._subs.pop(handle.event_type, None)

    async def publish(self, event: Event) -> None:
        handlers = list(self._subs.get(event.event_type, {}).values())
        if not handlers:
            return
        await asyncio.gather(*(h(event) for h in handlers))

    def subscriber_count(self, event_type: str) -> int:
        return len(self._subs.get(event_type, {}))
