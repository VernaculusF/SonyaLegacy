"""Priority scheduler — picks the highest-priority Window candidate per tick.

Phase 2D of unified-loop work. The 4 historical entry points
(_run_active_session, _run_task_worker, _emit_cognitive_events, TG handler)
fired on independent timers. They could overlap, miss each other, or
starve while one was hogging the busy_lock.

The scheduler turns this into ONE decision per tick: "given the current
state, what's the most important thing to run now?".

Priority ladder (top wins):

  9  TG message pending in inbox        — Ivan is waiting, interrupt anything else
  8  urgent task with deadline ≤6h      — externally bound timeline
  7  external active-session trigger    — manual force from CLI/admin
  6  active session due (>=2h)          — regular cadence
  5  in_progress task + worker due      — continue Ivan's work
  4  pending APPROVED selfmod proposal  — close the loop, commit improvement
  3  drift-response work                — react to detected anchor drift
  2  homeostasis threshold crossed      — emotional regulation
  1  idle reflection                    — fill silence productively
  0  nothing to do                      — sleep until next tick

The scheduler is INFORMATIONAL: it proposes an action but doesn't execute.
The loop tick decides whether to actually run it (e.g. busy_lock held).
This separation keeps the priority logic testable in isolation.

Future work:
  - When all priority-X candidates are blocked (lock held), promote
    priority-X-1 candidates so we don't lose ticks.
  - TG inbox priority-9 should preempt active session via injecting
    [NEW MESSAGE] turn — that's already in agent_session.inbox_drain.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Priority constants. Higher = more urgent. Stable so tests can compare.
PRIO_TG_INBOX = 9
PRIO_URGENT_TASK = 8
PRIO_EXTERNAL_TRIGGER = 7
PRIO_ACTIVE_DUE = 6
PRIO_WORKER_DUE = 5
PRIO_APPROVED_PROPOSAL = 4
PRIO_DRIFT_RESPONSE = 3
PRIO_HOMEOSTASIS = 2
PRIO_IDLE = 1
PRIO_IDLE_LITE = 0  # placeholder when nothing else


# Candidate kinds — strings (not enum) so they round-trip through audit JSON.
KIND_ACTIVE_SESSION = "active_session"
KIND_TASK_WORKER = "task_worker"
KIND_IDLE_THOUGHT = "idle_thought"
# (TG sessions don't go through the scheduler — they fire reactively from
# the channel handler. Listed for completeness in audit logging though.)
KIND_TG_SESSION = "tg_session"


@dataclass(frozen=True, slots=True)
class Candidate:
    """A scheduling candidate — what could run, why, at what priority.

    `payload` carries kind-specific details (task_id, request_seq, etc.)
    used by the loop tick when actually executing.
    """

    priority: int
    kind: str
    reason: str
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    """Result of scheduler.pick(). Always returns a Decision (never None).

    `chosen` is the highest-priority candidate above `min_priority`.
    If nothing meets the bar, chosen.priority == PRIO_IDLE_LITE and the
    loop tick is expected to do nothing this iteration.

    `runners_up` is the rest of the candidates (sorted desc) — useful for
    audit ("active was due but TG won; here's what else was ready").
    """

    chosen: Candidate
    runners_up: tuple[Candidate, ...] = ()


class Scheduler:
    """Stateless priority picker. State (timers, queues) lives in the loop.

    Usage::

        sched = Scheduler()
        candidates = []
        if external_trigger:
            candidates.append(Candidate(PRIO_EXTERNAL_TRIGGER, KIND_ACTIVE_SESSION, "external_trigger"))
        if active_due:
            candidates.append(Candidate(PRIO_ACTIVE_DUE, KIND_ACTIVE_SESSION, "interval_elapsed"))
        if worker_due:
            candidates.append(Candidate(PRIO_WORKER_DUE, KIND_TASK_WORKER, "task_in_progress",
                                        payload={"task_id": "..."}))
        if idle_triggered:
            candidates.append(Candidate(PRIO_IDLE, KIND_IDLE_THOUGHT, "idle_timeout"))

        decision = sched.pick(candidates)
        if decision.chosen.priority > 0:
            # actually run decision.chosen
            ...
    """

    @staticmethod
    def pick(candidates: list[Candidate]) -> Decision:
        if not candidates:
            return Decision(
                chosen=Candidate(PRIO_IDLE_LITE, "nothing", "no_candidates"),
            )
        sorted_c = sorted(candidates, key=lambda c: -c.priority)
        return Decision(chosen=sorted_c[0], runners_up=tuple(sorted_c[1:]))


__all__ = [
    "Candidate",
    "Decision",
    "Scheduler",
    "PRIO_TG_INBOX",
    "PRIO_URGENT_TASK",
    "PRIO_EXTERNAL_TRIGGER",
    "PRIO_ACTIVE_DUE",
    "PRIO_WORKER_DUE",
    "PRIO_APPROVED_PROPOSAL",
    "PRIO_DRIFT_RESPONSE",
    "PRIO_HOMEOSTASIS",
    "PRIO_IDLE",
    "PRIO_IDLE_LITE",
    "KIND_ACTIVE_SESSION",
    "KIND_TASK_WORKER",
    "KIND_IDLE_THOUGHT",
    "KIND_TG_SESSION",
]
