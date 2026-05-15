from __future__ import annotations

import asyncio

from sonya.runtime.events import Event, EventBus
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.subject_state import SubjectState, SubjectStateStore


class BusAwareContinuityStream:
    """Wrapper: after append, publishes `continuity.event_added` to event bus."""

    def __init__(self, stream: ContinuityStream, bus: EventBus) -> None:
        self._stream = stream
        self._bus = bus

    def append(self, event: ContinuityEvent) -> ContinuityEvent:
        result = self._stream.append(event)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._bus.publish(
                    Event(
                        event_type="continuity.event_added",
                        payload={"kind": result.kind, "seq": result.seq},
                    )
                )
            )
        except RuntimeError:
            pass  # no running loop (e.g. in sync test context)
        return result

    def latest_seq(self) -> int:
        return self._stream.latest_seq()

    def read_since(self, seq: int):
        return self._stream.read_since(seq)


class BusAwareSubjectStateStore:
    """Wrapper: after save, publishes `subject.state_changed` to event bus."""

    def __init__(self, store: SubjectStateStore, bus: EventBus) -> None:
        self._store = store
        self._bus = bus

    def load(self) -> SubjectState:
        return self._store.load()

    def save(self, state: SubjectState) -> None:
        self._store.save(state)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._bus.publish(
                    Event(
                        event_type="subject.state_changed",
                        payload={"active_principal_id": state.active_principal_id},
                    )
                )
            )
        except RuntimeError:
            pass  # no running loop

    def create_snapshot(self, snapshot_id: str):
        return self._store.create_snapshot(snapshot_id)

    def restore_from_snapshot(self, snapshot_id: str) -> None:
        return self._store.restore_from_snapshot(snapshot_id)
