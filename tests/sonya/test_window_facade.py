"""Tests for the Window dataclass + run_window facade.

Phase 2A of unified-loop work: Window is a thin dataclass that captures
"who's calling Sonya, what tools, what budget, what initial context".
run_window() unwraps it and calls the existing run_agent_session().

Today this is purely a facade — no behavior change. Tests verify:
  - Window construction with sensible defaults per kind
  - Budget defaults differ per kind (TG short, active long, idle minimal)
  - Caller-supplied budget overrides defaults
  - run_window passes through to the underlying agent loop without
    losing any of the 15 named parameters
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sonya.state import Substrate, seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.subject.window import (
    Window,
    run_window,
    WINDOW_KIND_ACTIVE,
    WINDOW_KIND_IDLE,
    WINDOW_KIND_TG,
    WINDOW_KIND_WORKER,
    _resolve_budget,
)
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


# --- budget defaults ---


def test_default_budget_for_tg() -> None:
    w = Window(kind=WINDOW_KIND_TG, system_prompt="x", tools={})
    steps, seconds = _resolve_budget(w)
    assert steps == 15
    assert seconds == 150.0


def test_default_budget_for_active() -> None:
    w = Window(kind=WINDOW_KIND_ACTIVE, system_prompt="x", tools={})
    steps, seconds = _resolve_budget(w)
    assert steps == 30
    assert seconds == 1800.0


def test_default_budget_for_worker() -> None:
    w = Window(kind=WINDOW_KIND_WORKER, system_prompt="x", tools={})
    steps, seconds = _resolve_budget(w)
    assert steps == 5
    assert seconds == 60.0


def test_default_budget_for_idle() -> None:
    w = Window(kind=WINDOW_KIND_IDLE, system_prompt="x", tools={})
    steps, seconds = _resolve_budget(w)
    assert steps == 3
    assert seconds == 60.0


def test_unknown_kind_falls_back_to_safe_default() -> None:
    w = Window(kind="custom_thing", system_prompt="x", tools={})
    steps, seconds = _resolve_budget(w)
    assert steps == 15
    assert seconds == 300.0


def test_explicit_budget_overrides_default() -> None:
    w = Window(
        kind=WINDOW_KIND_TG, system_prompt="x", tools={},
        max_steps=99, max_seconds=999.0,
    )
    steps, seconds = _resolve_budget(w)
    assert steps == 99
    assert seconds == 999.0


def test_zero_budget_uses_default() -> None:
    """max_steps=0 means 'use default', not 'no steps allowed'."""
    w = Window(kind=WINDOW_KIND_ACTIVE, system_prompt="x", tools={}, max_steps=0)
    steps, _ = _resolve_budget(w)
    assert steps == 30


# --- run_window plumbing ---


async def test_run_window_passes_through(substrate: Substrate, monkeypatch) -> None:
    """run_window unpacks the Window into run_agent_session args correctly."""
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs):
        captured.update(kwargs)
        from sonya.subject.agent_session import SessionResult
        return SessionResult(final_output="[DONE]", thoughts=[], actions=[])

    import sonya.subject.window as winmod
    monkeypatch.setattr(winmod, "run_agent_session", fake_run)

    si = SelfInspectTool(substrate)
    fs = FilesystemTool()
    stream = ContinuityStream(substrate)
    provider = AsyncMock()

    w = Window(
        kind=WINDOW_KIND_ACTIVE,
        system_prompt="hello",
        tools={"self_inspect": si, "filesystem": fs},
        initial_thought="seed",
        max_steps=12,
        max_seconds=99.0,
        purpose="custom_audit_label",
    )

    result = await run_window(w, provider=provider, stream=stream)

    assert result.final_output == "[DONE]"
    assert captured["system_prompt"] == "hello"
    assert captured["self_inspect"] is si
    assert captured["filesystem"] is fs
    assert captured["max_steps"] == 12
    assert captured["max_seconds"] == 99.0
    assert captured["initial_thought"] == "seed"
    assert captured["purpose"] == "custom_audit_label"
    # Tools not provided → None
    assert captured["selfmod"] is None
    assert captured["web"] is None
    assert captured["code"] is None
    assert captured["shell"] is None


async def test_run_window_default_purpose_is_kind(substrate: Substrate, monkeypatch) -> None:
    """If caller doesn't set purpose, default to the window kind for audit."""
    captured: dict[str, Any] = {}

    async def fake_run(**kwargs):
        captured.update(kwargs)
        from sonya.subject.agent_session import SessionResult
        return SessionResult()

    import sonya.subject.window as winmod
    monkeypatch.setattr(winmod, "run_agent_session", fake_run)

    si = SelfInspectTool(substrate)
    fs = FilesystemTool()

    w = Window(
        kind=WINDOW_KIND_TG,
        system_prompt="x",
        tools={"self_inspect": si, "filesystem": fs},
    )
    await run_window(w, provider=AsyncMock(), stream=ContinuityStream(substrate))
    assert captured["purpose"] == WINDOW_KIND_TG
