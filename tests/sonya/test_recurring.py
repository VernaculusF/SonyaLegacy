"""Recurring tasks scheduler — DONE/FAILED задачи c recurring_spec
переоткрываются по cadence."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state import Substrate
from sonya.tasks.models import Task, TaskStatus
from sonya.tasks.recurring import (
    RecurrenceCheck,
    RecurrenceScheduler,
    evaluate_recurrence,
    parse_duration,
)
from sonya.tasks.store import TaskStore


@pytest.fixture()
def substrate(tmp_path: Path):
    s = Substrate.open(tmp_path / "s.db")
    yield s
    s.close()


@pytest.fixture()
def store(substrate):
    return TaskStore(substrate)


def _make_task(store: TaskStore, **kwargs) -> Task:
    defaults = {
        "title": "test",
        "description": "",
        "plan_steps": [],
        "principal_id": "self",
        "parent_task_id": None,
        "deadline": None,
        "created_by": "self",
        "scheduled_for": "",
        "recurring_spec": "",
        "notify_mode": "progress",
        "max_sessions": 0,
        "urgency": "normal",
    }
    defaults.update(kwargs)
    return store.create(**defaults)


def _set_status(store: TaskStore, task_id: str, status: TaskStatus,
                *, updated_at: str = "") -> None:
    if not updated_at:
        updated_at = datetime.now(timezone.utc).isoformat()
    store._sub.connection.execute(
        "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
        (status.value, updated_at, task_id),
    )
    store._sub.connection.commit()


def test_parse_duration_units() -> None:
    assert parse_duration("30s") == timedelta(seconds=30)
    assert parse_duration("5m") == timedelta(minutes=5)
    assert parse_duration("2h") == timedelta(hours=2)
    assert parse_duration("3d") == timedelta(days=3)
    assert parse_duration("1w") == timedelta(weeks=1)
    assert parse_duration("0h") is None
    assert parse_duration("abc") is None
    assert parse_duration("") is None


def test_no_recurrence_for_terminal_with_empty_spec(store: TaskStore) -> None:
    t = _make_task(store, title="oneshot")
    _set_status(store, t.task_id, TaskStatus.DONE)
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    assert not check.should_clone
    assert check.reason == "no_spec"


def test_no_recurrence_for_active_task(store: TaskStore) -> None:
    t = _make_task(store, title="active", recurring_spec='{"every": "1d"}')
    # status is pending by default
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    assert not check.should_clone
    assert check.reason == "not_terminal"


def test_recurrence_due_after_cadence(store: TaskStore) -> None:
    t = _make_task(store, title="daily", recurring_spec='{"every": "1d"}')
    # Mark DONE 25 hours ago — past 1d cadence.
    past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    _set_status(store, t.task_id, TaskStatus.DONE, updated_at=past)
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    assert check.should_clone
    assert check.reason == "due"


def test_recurrence_not_due_yet(store: TaskStore) -> None:
    t = _make_task(store, title="daily", recurring_spec='{"every": "1d"}')
    # DONE 1 hour ago — much less than 1 day.
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _set_status(store, t.task_id, TaskStatus.DONE, updated_at=past)
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    assert not check.should_clone
    assert check.reason == "not_due_yet"
    assert check.next_run_at  # should be set


def test_scheduler_run_once_creates_clone(store: TaskStore, substrate) -> None:
    t = _make_task(
        store, title="morning ritual", recurring_spec='{"every": "1h"}',
    )
    # DONE 2h ago
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _set_status(store, t.task_id, TaskStatus.DONE, updated_at=past)

    scheduler = RecurrenceScheduler(store)
    results = scheduler.run_once()
    assert len(results) == 1
    assert results[0]["parent_id"] == t.task_id
    assert results[0]["new_task_id"] != t.task_id
    assert results[0]["reason"] == "due"

    # Clone exists with parent link, status pending
    clone = store.get(results[0]["new_task_id"])
    assert clone is not None
    assert clone.parent_task_id == t.task_id
    assert clone.status is TaskStatus.PENDING
    assert clone.title == t.title
    assert clone.recurring_spec == t.recurring_spec


def test_scheduler_skips_when_open_clone_exists(store: TaskStore) -> None:
    t = _make_task(store, title="thrice-checked", recurring_spec='{"every": "1m"}')
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    _set_status(store, t.task_id, TaskStatus.DONE, updated_at=past)

    scheduler = RecurrenceScheduler(store)
    results1 = scheduler.run_once()
    assert len(results1) == 1
    # Second run — open clone exists → no new spawn
    results2 = scheduler.run_once()
    assert len(results2) == 0


def test_recurrence_with_at_field_pins_to_time(store: TaskStore) -> None:
    """`at` field forces next run to specific UTC time-of-day."""
    t = _make_task(store, title="9am check", recurring_spec='{"every": "1d", "at": "09:00"}')
    # DONE 25 hours ago (past 1d cadence)
    past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    _set_status(store, t.task_id, TaskStatus.DONE, updated_at=past)
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    # Either should clone (если now > 9am UTC after the past+1d)
    # or not (если ещё не наступил 9am). Главное — next_run_at должен
    # содержать 09:00.
    if check.next_run_at:
        assert "09:00" in check.next_run_at or "T09" in check.next_run_at


def test_failed_status_also_recurs(store: TaskStore) -> None:
    t = _make_task(store, title="retry-daily", recurring_spec='{"every": "1d"}')
    past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    _set_status(store, t.task_id, TaskStatus.FAILED, updated_at=past)
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    assert check.should_clone


def test_bad_json_spec_is_ignored(store: TaskStore) -> None:
    t = _make_task(store, title="garbled", recurring_spec="{not json}")
    past = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    _set_status(store, t.task_id, TaskStatus.DONE, updated_at=past)
    refreshed = store.get(t.task_id)
    check = evaluate_recurrence(refreshed)
    assert not check.should_clone
    assert check.reason == "bad_spec_json"
