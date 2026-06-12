"""Test that recently-failed tasks surface in context_builder.

Symptom: 27.05.15:46. Sonya in idle thinking wrote
  "Думаю про mpbacademy. Бесит что worker наврал про дамп. Результатов
  UNION SQLi пока не вижу (worker молчит 1ч 45м), жду возможности проверить."

But the task `task-9ec82fa022dc` was in status=failed since 13:59 UTC
(session_budget_exhausted, 5/5 sessions). No worker would ever pick it
up. Sonya's narrative memory said "жду", but reality was "dead".

Root cause: WorkItemStore.list_open() filters status IN
('pending','in_progress','blocked'). 'failed' tasks vanish from the
context the LLM sees. Idle thoughts can't tell the difference between
"work is in progress somewhere" and "task is dead and forgotten".

Fix: WorkItemStore.list_recently_failed(hours=6) and a small block in
context_builder that surfaces them with explicit "worker won't pick
this up" wording.
"""
from __future__ import annotations

import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sonya.state import Substrate, seed_identity_if_empty
from sonya.work.store import WorkItemStore
from sonya.work.service import WorkItemService
from sonya.work.models import WorkItemStatus
from sonya.state.continuity_stream import ContinuityStream


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def test_list_recently_failed_returns_recent(substrate: Substrate) -> None:
    """Tasks failed within the window surface."""
    store = WorkItemStore(substrate)
    svc = WorkItemService(store, stream=ContinuityStream(substrate))
    t = svc.create(title="recon X", origin="ivan")
    svc.fail(t.item_id, reason="impossible without proxy")
    found = store.list_recently_failed(hours=6, limit=5)
    assert len(found) == 1
    assert found[0].item_id == t.item_id
    assert found[0].status is WorkItemStatus.FAILED


def test_list_recently_failed_skips_old(substrate: Substrate) -> None:
    """Tasks failed >6h ago do NOT surface."""
    svc = WorkItemService(WorkItemStore(substrate), stream=ContinuityStream(substrate))
    t = svc.create(title="ancient", origin="ivan")
    svc.fail(t.item_id, reason="meh")
    # Backdate updated_at past the window
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
    substrate.connection.execute(
        "UPDATE work_items SET updated_at = ? WHERE item_id = ?",
        (long_ago, t.item_id),
    )
    substrate.connection.commit()

    found = WorkItemStore(substrate).list_recently_failed(hours=6)
    assert found == []


def test_list_recently_failed_limit(substrate: Substrate) -> None:
    svc = WorkItemService(WorkItemStore(substrate), stream=ContinuityStream(substrate))
    for i in range(5):
        t = svc.create(title=f"t{i}", origin="ivan")
        svc.fail(t.item_id, reason="x")
    found = WorkItemStore(substrate).list_recently_failed(hours=6, limit=2)
    assert len(found) == 2


def test_context_builder_renders_failed_block(substrate: Substrate) -> None:
    """Context for idle thinking should include the 'failed' section so
    Sonya doesn't write 'жду возможности' about dead tasks."""
    from sonya.planning.context_builder import build_full_context
    from sonya.state.subject_state import SubjectStateStore

    svc = WorkItemService(WorkItemStore(substrate), stream=ContinuityStream(substrate))
    t = svc.create(title="mpbacademy SQLi", origin="ivan")
    svc.fail(t.item_id, reason="session budget exhausted, 5 attempts dead")

    state = SubjectStateStore(substrate).load()

    ctx = build_full_context(
        substrate=substrate,
        user_input="",
        principal_id="ivan",
    )
    sp = ctx.system_prompt
    assert "Недавно упавшие задачи" in sp
    assert "mpbacademy SQLi" in sp
    assert "Worker эти задачи не подхватит" in sp


def test_context_no_failed_block_when_clean(substrate: Substrate) -> None:
    """If nothing failed recently, the failed block is absent."""
    from sonya.planning.context_builder import build_full_context
    from sonya.state.subject_state import SubjectStateStore

    state = SubjectStateStore(substrate).load()
    ctx = build_full_context(
        substrate=substrate, user_input="", principal_id="ivan",
    )
    assert "Недавно упавшие задачи" not in ctx.system_prompt
