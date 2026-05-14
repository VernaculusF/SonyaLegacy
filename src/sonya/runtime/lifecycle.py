from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

from sonya.state import ContinuityEvent, ContinuityStream, Substrate
from sonya.runtime.events import Event, EventBus


class LifecycleState(str, Enum):
    NEW = "new"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"


class DoubleStartError(RuntimeError):
    pass


@dataclass(slots=True)
class Lifecycle:
    """Long-lived process lifecycle attached to substrate continuity stream."""

    substrate: Substrate
    event_bus: EventBus
    _state: LifecycleState = LifecycleState.NEW
    _stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        if self._state is not LifecycleState.NEW:
            raise DoubleStartError(self._state.value)
        ContinuityStream(self.substrate).append(
            ContinuityEvent(kind="subject.lifecycle.started")
        )
        self._state = LifecycleState.STARTED
        self._stop_event = asyncio.Event()
        await self.event_bus.publish(
            Event(event_type="subject.lifecycle.started", payload={})
        )

    async def request_stop(self) -> None:
        if self._state is LifecycleState.STOPPED:
            return
        if self._state is LifecycleState.NEW:
            self._state = LifecycleState.STOPPED
            return
        self._state = LifecycleState.STOPPING
        await self.event_bus.publish(
            Event(event_type="subject.lifecycle.stopping", payload={})
        )
        ContinuityStream(self.substrate).append(
            ContinuityEvent(kind="subject.lifecycle.stopped")
        )
        await self.event_bus.publish(
            Event(event_type="subject.lifecycle.stopped", payload={})
        )
        self._state = LifecycleState.STOPPED
        if self._stop_event is not None:
            self._stop_event.set()

    async def wait_for_stop(self) -> None:
        if self._stop_event is None:
            return
        await self._stop_event.wait()

    @property
    def state(self) -> LifecycleState:
        return self._state
