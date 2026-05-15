from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import Substrate
from sonya.state.pending import (
    IntentionAlreadyResolvedError,
    IntentionNotFoundError,
    IntentionStatus,
    PendingIntentionStore,
)


@pytest.fixture()
def store(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield PendingIntentionStore(sub)
    sub.close()


def test_create_starts_active(store: PendingIntentionStore) -> None:
    intn = store.create(description="write report", principal_id="ivan")
    assert intn.status is IntentionStatus.ACTIVE
    assert intn.intention_id.startswith("intn-")
    assert intn.description == "write report"
    assert intn.principal_id == "ivan"


def test_get_missing_raises(store: PendingIntentionStore) -> None:
    with pytest.raises(IntentionNotFoundError):
        store.get("intn-does-not-exist")


def test_list_active_returns_only_active(store: PendingIntentionStore) -> None:
    a = store.create(description="a")
    b = store.create(description="b")
    store.complete(a.intention_id)
    active = store.list_active()
    ids = [i.intention_id for i in active]
    assert a.intention_id not in ids
    assert b.intention_id in ids


def test_complete_flow(store: PendingIntentionStore) -> None:
    intn = store.create(description="x")
    done = store.complete(intn.intention_id)
    assert done.status is IntentionStatus.COMPLETED
    assert done.updated_at >= intn.created_at


def test_cancel_flow(store: PendingIntentionStore) -> None:
    intn = store.create(description="x")
    cancelled = store.cancel(intn.intention_id)
    assert cancelled.status is IntentionStatus.CANCELLED


def test_mark_overdue_flow(store: PendingIntentionStore) -> None:
    intn = store.create(description="x", deadline="2020-01-01T00:00:00+00:00")
    overdue = store.mark_overdue(intn.intention_id)
    assert overdue.status is IntentionStatus.OVERDUE


def test_transition_from_resolved_raises(store: PendingIntentionStore) -> None:
    intn = store.create(description="x")
    store.complete(intn.intention_id)
    with pytest.raises(IntentionAlreadyResolvedError):
        store.cancel(intn.intention_id)


def test_task_id_and_deadline_stored(store: PendingIntentionStore) -> None:
    intn = store.create(
        description="deploy",
        task_id="task-abc",
        deadline="2026-06-01T00:00:00+00:00",
    )
    loaded = store.get(intn.intention_id)
    assert loaded.task_id == "task-abc"
    assert loaded.deadline == "2026-06-01T00:00:00+00:00"


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    intn = PendingIntentionStore(sub1).create(description="persist me")
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        loaded = PendingIntentionStore(sub2).get(intn.intention_id)
        assert loaded.description == "persist me"
        assert loaded.status is IntentionStatus.ACTIVE
    finally:
        sub2.close()
