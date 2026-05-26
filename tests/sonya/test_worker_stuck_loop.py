"""Tests for stuck-loop detection in the task worker.

26.05 sweetcow incident: worker did 42 sessions on one task. Last 9
handoffs all wrote literally the same next_step ("Проверить
/wp-content/uploads/gravity_forms/..."). Each tick burned ~5 LLM calls
trying the same blocked approach.

Fix has two helpers:
  - _detect_stuck_loop(task_id): looks back N handoffs (default 3) and
    returns a blocker string if all wrote the same stem-normalized
    first-12-tokens prefix.
  - _count_recent_no_progress(task_id): walks back consecutive handoffs
    tagged "[no-progress retry" so the next_step shows attempt count.
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.pending import PendingIntentionStore
from sonya.state.substrate import Substrate
from sonya.subject.internal_loop import InternalProcess


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def _seed_handoff(sub: Substrate, *, task_id: str, next_step: str, minutes_ago: int = 0) -> None:
    """Inject a backdated task.session_handoff event."""
    when = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    sub.connection.execute(
        "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (
            "task.session_handoff",
            None,
            _json.dumps({"task_id": task_id, "next_step": next_step, "sessions_used": 1}),
            when,
        ),
    )
    sub.connection.commit()


def _build_loop(substrate: Substrate) -> InternalProcess:
    return InternalProcess(
        stream=ContinuityStream(substrate),
        intention_store=PendingIntentionStore(substrate),
        substrate=substrate,
        provider=None,
    )


# --- _detect_stuck_loop ---


def test_stuck_loop_detected_after_3_identical_handoffs(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    tid = "task-stuck-1"
    same = "Проверить /wp-content/uploads/gravity_forms/ на directory listing"
    for i in range(3):
        _seed_handoff(substrate, task_id=tid, next_step=same, minutes_ago=20 - i * 5)
    reason = loop._detect_stuck_loop(tid)
    assert reason
    assert "stuck loop" in reason


def test_stuck_loop_silent_for_2_identical(substrate: Substrate) -> None:
    """Threshold is 3 — two identical handoffs are not yet a loop."""
    loop = _build_loop(substrate)
    tid = "task-stuck-2"
    same = "Проверить /wp-content/uploads/gravity_forms/"
    for i in range(2):
        _seed_handoff(substrate, task_id=tid, next_step=same, minutes_ago=20 - i * 5)
    assert loop._detect_stuck_loop(tid) == ""


def test_stuck_loop_silent_when_handoffs_differ(substrate: Substrate) -> None:
    """Different next_steps → not stuck."""
    loop = _build_loop(substrate)
    tid = "task-stuck-3"
    _seed_handoff(substrate, task_id=tid, next_step="Скачать wpo.json", minutes_ago=15)
    _seed_handoff(substrate, task_id=tid, next_step="Проверить плагины", minutes_ago=10)
    _seed_handoff(substrate, task_id=tid, next_step="Брутфорс через xmlrpc", minutes_ago=5)
    assert loop._detect_stuck_loop(tid) == ""


def test_stuck_loop_silent_when_no_handoffs(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    assert loop._detect_stuck_loop("task-nonexistent") == ""


def test_stuck_loop_stem_normalized_match(substrate: Substrate) -> None:
    """Paraphrases of the same first-12-stems should also match."""
    loop = _build_loop(substrate)
    tid = "task-stuck-4"
    # Same opening 12 tokens after stemming, different tail filler
    _seed_handoff(substrate, task_id=tid, next_step="Проверить gravity forms на directory listing — попробую через curl",
                  minutes_ago=15)
    _seed_handoff(substrate, task_id=tid, next_step="Проверить gravity forms на directory listing — другим юзер-агентом",
                  minutes_ago=10)
    _seed_handoff(substrate, task_id=tid, next_step="Проверить gravity forms на directory listing с заголовком Referer",
                  minutes_ago=5)
    reason = loop._detect_stuck_loop(tid)
    assert reason
    assert "stuck loop" in reason


def test_stuck_loop_only_other_task_handoffs(substrate: Substrate) -> None:
    """Handoffs for a DIFFERENT task must not count toward stuck count."""
    loop = _build_loop(substrate)
    tid_a = "task-A"
    tid_b = "task-B"
    same = "Проверить gravity forms"
    # 3 handoffs for task A
    for i in range(3):
        _seed_handoff(substrate, task_id=tid_a, next_step=same, minutes_ago=20 - i * 5)
    # 0 handoffs for task B
    assert loop._detect_stuck_loop(tid_b) == ""


# --- _count_recent_no_progress ---


def test_count_no_progress_walks_back_until_productive(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    tid = "task-np-1"
    # Newest first in continuity (highest seq = most recent). _seed_handoff
    # uses minutes_ago, so smaller minutes_ago = more recent.
    _seed_handoff(substrate, task_id=tid, next_step="something concrete found", minutes_ago=30)
    _seed_handoff(substrate, task_id=tid, next_step="[no-progress retry #1] try X", minutes_ago=20)
    _seed_handoff(substrate, task_id=tid, next_step="[no-progress retry #2] try X again", minutes_ago=10)
    _seed_handoff(substrate, task_id=tid, next_step="[no-progress retry #3] still trying X", minutes_ago=5)
    # 3 consecutive no-progress retries before hitting the productive one
    assert loop._count_recent_no_progress(tid) == 3


def test_count_no_progress_zero_when_latest_is_productive(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    tid = "task-np-2"
    _seed_handoff(substrate, task_id=tid, next_step="[no-progress retry #1] X", minutes_ago=10)
    _seed_handoff(substrate, task_id=tid, next_step="found something concrete", minutes_ago=5)
    assert loop._count_recent_no_progress(tid) == 0


def test_count_no_progress_zero_when_no_handoffs(substrate: Substrate) -> None:
    loop = _build_loop(substrate)
    assert loop._count_recent_no_progress("task-nonexistent") == 0
