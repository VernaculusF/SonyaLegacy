from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import Substrate, SubjectState, SubjectStateStore


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_subject_state_default_when_empty(substrate: Substrate) -> None:
    store = SubjectStateStore(substrate)
    state = store.load()
    assert state.active_principal_id is None
    assert state.last_canonical_response_ref is None
    assert state.active_channels == ()
    assert state.pending_intentions == ()


def test_subject_state_round_trip(substrate: Substrate) -> None:
    store = SubjectStateStore(substrate)
    new_state = SubjectState(
        active_principal_id="p1",
        last_canonical_response_ref="cr-42",
        active_channels=("telegram", "cli"),
        pending_intentions=("task-1", "task-2"),
    )
    store.save(new_state)
    loaded = store.load()
    assert loaded == new_state


def test_subject_state_restore_after_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    SubjectStateStore(sub1).save(
        SubjectState(active_principal_id="ivan", active_channels=("telegram",))
    )
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        loaded = SubjectStateStore(sub2).load()
        assert loaded.active_principal_id == "ivan"
        assert loaded.active_channels == ("telegram",)
    finally:
        sub2.close()
