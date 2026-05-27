"""Tests for the priority Scheduler.

Phase 2D of unified-loop work. Pure logic — no async, no substrate, no LLM.
The scheduler's only job is: given a list of Candidate, return Decision
with the highest-priority one chosen and the rest as runners_up.
"""
from __future__ import annotations

import pytest

from sonya.subject.scheduler import (
    Candidate,
    Decision,
    Scheduler,
    PRIO_ACTIVE_DUE,
    PRIO_EXTERNAL_TRIGGER,
    PRIO_HOMEOSTASIS,
    PRIO_IDLE,
    PRIO_IDLE_LITE,
    PRIO_TG_INBOX,
    PRIO_URGENT_TASK,
    PRIO_WORKER_DUE,
    KIND_ACTIVE_SESSION,
    KIND_IDLE_THOUGHT,
    KIND_TASK_WORKER,
    KIND_TG_SESSION,
)


def test_empty_candidates_returns_idle_lite() -> None:
    decision = Scheduler.pick([])
    assert decision.chosen.priority == PRIO_IDLE_LITE
    assert decision.chosen.kind == "nothing"
    assert decision.runners_up == ()


def test_single_candidate_wins() -> None:
    c = Candidate(PRIO_IDLE, KIND_IDLE_THOUGHT, "idle_timeout")
    decision = Scheduler.pick([c])
    assert decision.chosen is c
    assert decision.runners_up == ()


def test_higher_priority_wins() -> None:
    """When TG inbox + active session both ready, TG wins."""
    tg = Candidate(PRIO_TG_INBOX, KIND_TG_SESSION, "incoming_message")
    active = Candidate(PRIO_ACTIVE_DUE, KIND_ACTIVE_SESSION, "cadence_elapsed")
    decision = Scheduler.pick([active, tg])
    assert decision.chosen is tg
    assert decision.runners_up == (active,)


def test_runners_up_sorted_descending() -> None:
    cands = [
        Candidate(PRIO_IDLE, KIND_IDLE_THOUGHT, "idle"),
        Candidate(PRIO_HOMEOSTASIS, KIND_IDLE_THOUGHT, "loneliness"),
        Candidate(PRIO_WORKER_DUE, KIND_TASK_WORKER, "worker"),
        Candidate(PRIO_ACTIVE_DUE, KIND_ACTIVE_SESSION, "active"),
    ]
    decision = Scheduler.pick(cands)
    assert decision.chosen.priority == PRIO_ACTIVE_DUE
    # Runners-up sorted desc by priority
    runners_prios = [c.priority for c in decision.runners_up]
    assert runners_prios == sorted(runners_prios, reverse=True)
    assert runners_prios == [PRIO_WORKER_DUE, PRIO_HOMEOSTASIS, PRIO_IDLE]


def test_external_trigger_beats_regular_active() -> None:
    """External 'fire now' trigger should outrank scheduled cadence."""
    ext = Candidate(PRIO_EXTERNAL_TRIGGER, KIND_ACTIVE_SESSION, "external_trigger")
    cadence = Candidate(PRIO_ACTIVE_DUE, KIND_ACTIVE_SESSION, "cadence_elapsed")
    decision = Scheduler.pick([cadence, ext])
    assert decision.chosen.reason == "external_trigger"


def test_urgent_task_beats_active_session() -> None:
    urgent = Candidate(PRIO_URGENT_TASK, KIND_TASK_WORKER, "deadline_close",
                       payload={"task_id": "task-x"})
    active = Candidate(PRIO_ACTIVE_DUE, KIND_ACTIVE_SESSION, "cadence_elapsed")
    decision = Scheduler.pick([active, urgent])
    assert decision.chosen is urgent
    assert decision.chosen.payload == {"task_id": "task-x"}


def test_priority_ladder_is_strict() -> None:
    """The ladder TG > Urgent > External > Active > Worker > Approved >
    Drift > Homeostasis > Idle > Idle-lite must be strictly decreasing."""
    ladder = [
        PRIO_TG_INBOX, PRIO_URGENT_TASK, PRIO_EXTERNAL_TRIGGER,
        PRIO_ACTIVE_DUE, PRIO_WORKER_DUE,
    ]
    assert ladder == sorted(ladder, reverse=True)
    assert len(set(ladder)) == len(ladder)  # no duplicates


def test_payload_preserved_through_decision() -> None:
    c = Candidate(
        priority=PRIO_WORKER_DUE,
        kind=KIND_TASK_WORKER,
        reason="worker_due",
        payload={"task_id": "task-abc", "remaining_steps": 3},
    )
    decision = Scheduler.pick([c])
    assert decision.chosen.payload == {"task_id": "task-abc", "remaining_steps": 3}


def test_two_candidates_same_priority_stable_pick() -> None:
    """When two candidates tie on priority, picker shouldn't crash. The
    exact tie-break is implementation-defined (Python's sorted is stable)."""
    a = Candidate(PRIO_IDLE, KIND_IDLE_THOUGHT, "first")
    b = Candidate(PRIO_IDLE, KIND_IDLE_THOUGHT, "second")
    decision = Scheduler.pick([a, b])
    assert decision.chosen.priority == PRIO_IDLE
    assert len(decision.runners_up) == 1
