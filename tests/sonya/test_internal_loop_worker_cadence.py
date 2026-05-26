"""Tests for adaptive task-worker cadence and on-demand kick.

Background: when Sonya delegates to a task ("ушла в фоне"), worker tick
fires every ``task_worker_interval_seconds`` (default 30 min). Without
adaptive cadence or external kick, Ivan waits 0-30 minutes before any
real progress on a task he's actively waiting for.

Two mechanisms tested:
  - InternalProcess.request_worker_soon: TG handler calls this after a
    tasks.create / tasks.pick / tasks.unblock, telling the loop to fire
    the worker on the next tick instead of waiting the full interval.
  - InternalProcess._effective_worker_interval: returns 180s (3 min)
    when Ivan is recently active (last incoming msg <30 min) AND there's
    an urgent in_progress task; default interval otherwise.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.pending import PendingIntentionStore
from sonya.state.substrate import Substrate
from sonya.subject.internal_loop import InternalProcess
from sonya.tasks.store import TaskStore


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def _build_loop(substrate: Substrate, *, worker_interval: float = 1800.0) -> InternalProcess:
    return InternalProcess(
        stream=ContinuityStream(substrate),
        intention_store=PendingIntentionStore(substrate),
        substrate=substrate,
        provider=None,
        task_worker_interval_seconds=worker_interval,
    )


# --- request_worker_soon ---


@pytest.mark.asyncio
async def test_request_worker_soon_pulls_next_tick_forward(
    substrate: Substrate,
) -> None:
    """After request_worker_soon, _last_task_worker_at moves enough into the
    past that the next tick sees the worker as overdue."""
    loop = _build_loop(substrate, worker_interval=1800.0)
    # Simulate a tick just ran — worker recently fired.
    asyncio_loop = asyncio.get_event_loop()
    loop._last_task_worker_at = asyncio_loop.time()

    # Without kick: worker is NOT due yet (just ran).
    elapsed_before = asyncio_loop.time() - loop._last_task_worker_at
    assert elapsed_before < loop._task_worker_interval

    loop.request_worker_soon(delay_seconds=30.0)

    # After kick: in 30s the elapsed time should exceed the effective
    # interval. We don't actually wait — just check the math.
    elapsed_after_30s = (asyncio_loop.time() + 30.0) - loop._last_task_worker_at
    # Effective interval at this moment is the constructor value (no urgent
    # tasks seeded). Kick set _last_task_worker_at to (now - interval + 30s),
    # so in 30s elapsed = interval (≈ due).
    assert elapsed_after_30s >= loop._task_worker_interval - 1.0


@pytest.mark.asyncio
async def test_request_worker_soon_emits_continuity_event(
    substrate: Substrate,
) -> None:
    loop = _build_loop(substrate)
    stream = ContinuityStream(substrate)
    before_seq = stream.latest_seq()
    loop.request_worker_soon(delay_seconds=30.0)
    new_events = list(stream.read_since(before_seq))
    kinds = {e.kind for e in new_events}
    assert "internal.task_worker_scheduled" in kinds


@pytest.mark.asyncio
async def test_request_worker_soon_idempotent(
    substrate: Substrate,
) -> None:
    """Calling twice with later delay must not push the schedule later."""
    loop = _build_loop(substrate)
    # Set a recent _last_task_worker_at so first kick has effect to compare.
    loop._last_task_worker_at = asyncio.get_event_loop().time()
    loop.request_worker_soon(delay_seconds=30.0)
    first = loop._last_task_worker_at
    loop.request_worker_soon(delay_seconds=300.0)  # later delay
    # Should NOT push later — earliest scheduled wins.
    assert loop._last_task_worker_at == first


# --- _effective_worker_interval ---


def _seed_urgent_task(substrate: Substrate) -> None:
    """Insert an in_progress Ivan-task with notify_mode=progress (urgent)."""
    from sonya.tasks.service import TaskService
    store = TaskStore(substrate)
    svc = TaskService(store, stream=ContinuityStream(substrate))
    task = store.create(
        title="Test urgent task",
        description="—",
        principal_id="ivan",
        created_by="ivan",
        notify_mode="progress",
    )
    svc.set_in_progress(task.task_id)


@pytest.mark.asyncio
async def test_effective_interval_fast_when_urgent_task_exists(
    substrate: Substrate,
) -> None:
    """Urgent in_progress task → 3-minute cadence regardless of Ivan activity."""
    _seed_urgent_task(substrate)
    loop = _build_loop(substrate, worker_interval=1800.0)
    interval = loop._effective_worker_interval()
    assert interval == 180.0


@pytest.mark.asyncio
async def test_effective_interval_default_when_no_urgent_task(
    substrate: Substrate,
) -> None:
    """No urgent task — fall back to constructor interval (token saver)."""
    loop = _build_loop(substrate, worker_interval=1800.0)
    interval = loop._effective_worker_interval()
    assert interval == 1800.0


@pytest.mark.asyncio
async def test_effective_interval_falls_back_when_no_substrate(
    tmp_path: Path,
) -> None:
    """Loop without substrate (test scaffolding) returns constructor interval."""
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    try:
        loop = InternalProcess(
            stream=ContinuityStream(sub),
            intention_store=PendingIntentionStore(sub),
            substrate=None,  # explicitly None
            provider=None,
            task_worker_interval_seconds=1234.0,
        )
        loop._last_external_event = asyncio.get_event_loop().time()
        assert loop._effective_worker_interval() == 1234.0
    finally:
        sub.close()
