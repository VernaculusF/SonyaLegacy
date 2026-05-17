"""Tests for the Этап C task runtime."""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import Substrate
from sonya.state.continuity_stream import ContinuityStream
from sonya.tasks import Task, TaskNotFoundError, TaskStatus, TaskService, TaskStore
from sonya.tasks.models import TaskTransitionError
from sonya.tools.tasks_tool import TasksTool


# ---------- store ----------

@pytest.fixture()
def store(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield TaskStore(sub)
    sub.close()


def test_create_task_starts_pending(store: TaskStore) -> None:
    t = store.create(title="Write Discord channel", description="adapter for Discord API")
    assert t.task_id.startswith("task-")
    assert t.title == "Write Discord channel"
    assert t.description == "adapter for Discord API"
    assert t.status is TaskStatus.PENDING
    assert t.plan_steps == []
    assert t.completed_steps == []


def test_get_missing_raises(store: TaskStore) -> None:
    with pytest.raises(TaskNotFoundError):
        store.get("task-missing")


def test_replace_plan_steps(store: TaskStore) -> None:
    t = store.create(title="x")
    updated = store.replace_plan_steps(t.task_id, ["read", "design", "write", "test"])
    assert updated.plan_steps == ["read", "design", "write", "test"]


def test_append_completed_step(store: TaskStore) -> None:
    t = store.create(title="x")
    store.replace_plan_steps(t.task_id, ["a", "b", "c"])
    updated = store.append_completed_step(t.task_id, step_idx=0, summary="did a")
    assert len(updated.completed_steps) == 1
    assert updated.completed_steps[0]["step_idx"] == 0
    assert updated.completed_steps[0]["summary"] == "did a"


def test_list_open_excludes_resolved(store: TaskStore) -> None:
    a = store.create(title="a")
    b = store.create(title="b")
    c = store.create(title="c")
    store.set_result(b.task_id, "ok", TaskStatus.DONE)
    store.set_result(c.task_id, "fail", TaskStatus.FAILED)
    open_tasks = store.list_open()
    open_ids = {t.task_id for t in open_tasks}
    assert a.task_id in open_ids
    assert b.task_id not in open_ids
    assert c.task_id not in open_ids


def test_persistence_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    t = TaskStore(sub1).create(title="persist", description="me")
    sub1.close()
    sub2 = Substrate.open(db)
    try:
        loaded = TaskStore(sub2).get(t.task_id)
        assert loaded.title == "persist"
        assert loaded.description == "me"
    finally:
        sub2.close()


# ---------- service ----------

@pytest.fixture()
def service(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    stream = ContinuityStream(sub)
    yield TaskService(TaskStore(sub), stream=stream), stream
    sub.close()


def test_service_create_emits_continuity(service) -> None:
    svc, stream = service
    svc.create(title="ship", principal_id="ivan")
    events = list(stream.read_since(0))
    kinds = [e.kind for e in events]
    assert "task.created" in kinds


def test_service_create_rejects_empty_title(service) -> None:
    svc, _ = service
    with pytest.raises(ValueError):
        svc.create(title="   ")


def test_set_in_progress_transitions(service) -> None:
    svc, _ = service
    t = svc.create(title="x")
    started = svc.set_in_progress(t.task_id)
    assert started.status is TaskStatus.IN_PROGRESS


def test_set_in_progress_fails_for_done(service) -> None:
    svc, _ = service
    t = svc.create(title="x")
    svc.complete(t.task_id, "fine")
    with pytest.raises(TaskTransitionError):
        svc.set_in_progress(t.task_id)


def test_complete_then_complete_raises(service) -> None:
    svc, _ = service
    t = svc.create(title="x")
    svc.complete(t.task_id, "ok")
    with pytest.raises(TaskTransitionError):
        svc.complete(t.task_id, "again")


def test_step_done_idempotent(service) -> None:
    svc, _ = service
    t = svc.create(title="x", plan_steps=["a", "b"])
    svc.mark_step_done(t.task_id, 0, "did a")
    svc.mark_step_done(t.task_id, 0, "did a again")  # idempotent
    after = svc.get(t.task_id)
    assert len(after.completed_steps) == 1


def test_step_done_out_of_range(service) -> None:
    svc, _ = service
    t = svc.create(title="x", plan_steps=["a"])
    with pytest.raises(ValueError):
        svc.mark_step_done(t.task_id, 5, "nope")


def test_block_and_unblock(service) -> None:
    svc, _ = service
    t = svc.create(title="x")
    svc.set_in_progress(t.task_id)
    blocked = svc.block(t.task_id, "waiting on Ivan for OAuth")
    assert blocked.status is TaskStatus.BLOCKED
    assert "OAuth" in blocked.blocker
    unblocked = svc.unblock(t.task_id)
    assert unblocked.status is TaskStatus.IN_PROGRESS


def test_pick_next_returns_in_progress_first(service) -> None:
    svc, _ = service
    a = svc.create(title="a")
    b = svc.create(title="b")
    svc.set_in_progress(a.task_id)
    picked = svc.pick_next()
    assert picked is not None
    assert picked.task_id == a.task_id


def test_pick_next_falls_back_to_oldest_pending(service) -> None:
    svc, _ = service
    a = svc.create(title="older")
    b = svc.create(title="newer")
    picked = svc.pick_next()
    assert picked is not None
    assert picked.task_id == a.task_id


def test_pick_next_returns_none_when_only_blocked(service) -> None:
    svc, _ = service
    a = svc.create(title="a")
    svc.set_in_progress(a.task_id)
    svc.block(a.task_id, "waiting")
    picked = svc.pick_next()
    assert picked is None


def test_remaining_steps(service) -> None:
    svc, _ = service
    t = svc.create(title="x", plan_steps=["a", "b", "c"])
    svc.mark_step_done(t.task_id, 1, "did b")
    after = svc.get(t.task_id)
    remaining = after.remaining_steps()
    assert remaining == ["a", "c"]


# ---------- TasksTool ----------

@pytest.fixture()
def tasks_tool(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield TasksTool(sub, stream=ContinuityStream(sub), default_principal_id="ivan")
    sub.close()


def test_tool_create_minimal(tasks_tool: TasksTool) -> None:
    out = tasks_tool.create("Write Discord channel")
    assert "[OK] created" in out
    assert "title: Write Discord channel" in out
    assert "status: pending" in out


def test_tool_create_with_plan(tasks_tool: TasksTool) -> None:
    out = tasks_tool.create("Refactor planner | extract scoring | read; design; propose; apply")
    assert "[OK]" in out
    assert "[ ] 0. read" in out
    assert "[ ] 3. apply" in out


def test_tool_create_empty_rejected(tasks_tool: TasksTool) -> None:
    out = tasks_tool.create("")
    assert "[ERROR]" in out


def test_tool_list_empty(tasks_tool: TasksTool) -> None:
    out = tasks_tool.list("")
    assert "no tasks" in out.lower()


def test_tool_list_with_filter(tasks_tool: TasksTool) -> None:
    tasks_tool.create("a")
    tasks_tool.create("b")
    listing = tasks_tool.list("pending")
    assert "a" in listing and "b" in listing


def test_tool_pick_and_step_and_complete(tasks_tool: TasksTool) -> None:
    create_out = tasks_tool.create("ship | description | step1; step2")
    # Extract task_id
    task_id = next(line.split(": ")[1] for line in create_out.splitlines() if line.startswith("task_id:"))

    pick_out = tasks_tool.pick("")
    assert "[OK] picked" in pick_out

    step_out = tasks_tool.step(f"{task_id} | 0 | did step1")
    assert "[OK] step 0 done (1/2)" in step_out

    complete_out = tasks_tool.complete(f"{task_id} | shipped it")
    assert "[OK] task done" in complete_out
    assert "status: done" in complete_out


def test_tool_block_then_unblock(tasks_tool: TasksTool) -> None:
    out = tasks_tool.create("x")
    task_id = next(line.split(": ")[1] for line in out.splitlines() if line.startswith("task_id:"))
    tasks_tool.pick("")
    block_out = tasks_tool.block(f"{task_id} | waiting on Ivan for API key")
    assert "[OK] task blocked" in block_out
    assert "blocker: waiting on Ivan" in block_out
    unblock_out = tasks_tool.unblock(task_id)
    assert "[OK] unblocked" in unblock_out
    assert "status: in_progress" in unblock_out


def test_tool_get_missing(tasks_tool: TasksTool) -> None:
    out = tasks_tool.get("task-missing")
    assert "[ERROR]" in out
    assert "not found" in out


# ---------- migration / schema_version ----------

def test_fresh_substrate_at_v7(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "s.db")
    try:
        assert sub.schema_version >= 7
        # tasks table exists
        row = sub.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        assert row is not None
    finally:
        sub.close()
