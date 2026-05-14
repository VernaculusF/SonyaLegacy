from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import (
    ContinuityEvent,
    ContinuityStream,
    Substrate,
    SubjectState,
    SubjectStateStore,
)


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_stream_starts_empty(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    assert stream.latest_seq() == 0
    assert list(stream.read_since(0)) == []


def test_append_returns_monotonic_seq(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    e1 = stream.append(ContinuityEvent(kind="lifecycle.started", payload={"x": 1}))
    e2 = stream.append(ContinuityEvent(kind="lifecycle.tick", payload={}))
    assert e1.seq == 1
    assert e2.seq == 2
    assert stream.latest_seq() == 2


def test_read_since_returns_events_in_order(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(kind="a"))
    stream.append(ContinuityEvent(kind="b"))
    stream.append(ContinuityEvent(kind="c"))
    seqs = [ev.seq for ev in stream.read_since(0)]
    kinds = [ev.kind for ev in stream.read_since(0)]
    assert seqs == [1, 2, 3]
    assert kinds == ["a", "b", "c"]


def test_read_since_skips_earlier(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    for k in ("a", "b", "c", "d"):
        stream.append(ContinuityEvent(kind=k))
    later = list(stream.read_since(2))
    assert [ev.kind for ev in later] == ["c", "d"]


def test_continuity_event_carries_principal_and_payload(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(
        ContinuityEvent(
            kind="subject.test",
            principal_id="ivan",
            payload={"note": "hello"},
        )
    )
    [ev] = list(stream.read_since(0))
    assert ev.principal_id == "ivan"
    assert ev.payload == {"note": "hello"}


def test_snapshot_replay_reproduces_state(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub = Substrate.open(db)
    try:
        store = SubjectStateStore(sub)
        store.save(SubjectState(active_principal_id="ivan", active_channels=("telegram",)))
        snap = store.create_snapshot(snapshot_id="snap-A")

        # Mutate state.
        store.save(SubjectState(active_principal_id="other"))

        # Restore from snapshot.
        store.restore_from_snapshot(snap.snapshot_id)
        loaded = store.load()
        assert loaded.active_principal_id == "ivan"
        assert loaded.active_channels == ("telegram",)
    finally:
        sub.close()
