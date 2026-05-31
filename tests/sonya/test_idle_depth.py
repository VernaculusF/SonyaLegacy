"""Tests for variable idle thinking depth based on drive state."""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import ContinuityStream, Substrate
from sonya.state.pending import PendingIntentionStore
from sonya.subject.internal_loop import InternalProcess


@pytest.fixture()
def proc(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    stream = ContinuityStream(sub)
    store = PendingIntentionStore(sub)
    p = InternalProcess(stream, store)
    yield p
    sub.close()


def test_idle_depth_default(proc: InternalProcess) -> None:
    kw = proc._idle_depth_kwargs({"curiosity_analog": 0.1, "boredom_analog": 0.1})
    assert kw["max_tokens"] == 500
    assert kw["temperature"] == pytest.approx(0.9)


def test_idle_depth_high_curiosity_deeper(proc: InternalProcess) -> None:
    kw = proc._idle_depth_kwargs({"curiosity_analog": 0.8})
    assert kw["max_tokens"] == 800
    assert kw["temperature"] == pytest.approx(0.95)


def test_idle_depth_pending_debt_compresses(proc: InternalProcess) -> None:
    kw = proc._idle_depth_kwargs({"pending_debt": 0.7})
    assert kw["max_tokens"] == 300


def test_idle_depth_loneliness_compresses(proc: InternalProcess) -> None:
    kw = proc._idle_depth_kwargs({"boredom_analog": 0.7})
    assert kw["max_tokens"] == 300


def test_idle_depth_pending_beats_curiosity(proc: InternalProcess) -> None:
    """When curiosity AND pending_debt are both high, action wins."""
    kw = proc._idle_depth_kwargs(
        {"curiosity_analog": 0.9, "pending_debt": 0.7}
    )
    assert kw["max_tokens"] == 300


def test_idle_depth_handles_invalid_values(proc: InternalProcess) -> None:
    kw = proc._idle_depth_kwargs(
        {"curiosity_analog": "not-a-number", "boredom_analog": None}
    )
    # Falls through to default.
    assert kw["max_tokens"] == 500
