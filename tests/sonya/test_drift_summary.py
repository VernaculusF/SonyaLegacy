"""Tests for SelfInspectTool.read_drift_summary.

This is the data feed for the periodic self-improvement track. Sonya
calls it (or it's pre-loaded into her active-session seed) and sees
aggregate counts of her own drift patterns + blocked tasks + selfmod
activity. She decides what to fix in her own code.
"""
from __future__ import annotations

import json as _json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state import seed_identity_if_empty
from sonya.state.substrate import Substrate
from sonya.tools.self_inspect import SelfInspectTool


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def _seed_event(sub: Substrate, kind: str, payload: dict | None = None,
                *, days_ago: float = 0.1) -> None:
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    sub.connection.execute(
        "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (kind, None, _json.dumps(payload or {}), when),
    )
    sub.connection.commit()


def _seed_task(sub: Substrate, *, status: str, title: str,
               sessions_used: int = 0, blocker: str = "",
               days_ago: float = 0.1) -> None:
    """Insert a task row directly with a backdated updated_at."""
    when = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    from uuid import uuid4
    tid = f"task-{uuid4().hex[:12]}"
    sub.connection.execute(
        "INSERT INTO tasks (task_id, title, description, status, plan_steps_json, "
        "completed_steps_json, blocker, result, created_at, updated_at, "
        "max_sessions, sessions_used, last_session_notes, next_step_hint) "
        "VALUES (?, ?, ?, ?, '[]', '[]', ?, '', ?, ?, 0, ?, '', '')",
        (tid, title, "", status, blocker, when, when, sessions_used),
    )
    sub.connection.commit()


def test_drift_summary_minimal_when_no_signals(substrate: Substrate) -> None:
    """Empty stream → still shows selfmod activity + work volume sections
    (which are 'NEVER applied' / '0 sessions'). No drift signal sections."""
    si = SelfInspectTool(substrate)
    out = si.read_drift_summary(days=3)
    # Selfmod section always present
    assert "Selfmod" in out
    assert "NEVER" in out
    # Drift signal sections absent
    assert "gate отклонил" not in out
    assert "Stuck-loop" not in out
    assert "blocked/failed" not in out


def test_drift_summary_counts_initiative_blocked(substrate: Substrate) -> None:
    si = SelfInspectTool(substrate)
    for _ in range(4):
        _seed_event(substrate, "internal.initiative_blocked",
                    payload={"reason": "quiet window: 60min"}, days_ago=0.5)
    for _ in range(2):
        _seed_event(substrate, "internal.initiative_blocked",
                    payload={"reason": "ivan_status='спит'"}, days_ago=0.5)
    out = si.read_drift_summary(days=3)
    assert "gate отклонил" in out
    assert "4×" in out
    assert "2×" in out


def test_drift_summary_counts_stuck_loops(substrate: Substrate) -> None:
    si = SelfInspectTool(substrate)
    for _ in range(3):
        _seed_event(substrate, "internal.task_worker_stuck_blocked",
                    payload={"task_id": f"task-{_}"}, days_ago=0.5)
    out = si.read_drift_summary(days=3)
    assert "Stuck-loop" in out
    assert "3×" in out


def test_drift_summary_lists_blocked_tasks(substrate: Substrate) -> None:
    si = SelfInspectTool(substrate)
    _seed_task(substrate, status="blocked", title="Sweetcow recon",
               sessions_used=42, blocker="Sucuri WAF rate-limited")
    _seed_task(substrate, status="failed", title="Old try",
               sessions_used=12, blocker="approach exhausted")
    out = si.read_drift_summary(days=3)
    assert "blocked" in out.lower() or "blocked/failed" in out.lower()
    assert "Sweetcow recon" in out


def test_drift_summary_shows_selfmod_activity(substrate: Substrate) -> None:
    si = SelfInspectTool(substrate)
    _seed_event(substrate, "self_mod.applied",
                payload={"target_module": "src/sonya/main.py"},
                days_ago=0.3)
    out = si.read_drift_summary(days=3)
    assert "Selfmod" in out
    assert "applied: 1" in out
    assert "src/sonya/main.py" in out


def test_drift_summary_shows_never_applied(substrate: Substrate) -> None:
    si = SelfInspectTool(substrate)
    out = si.read_drift_summary(days=3)
    assert "NEVER" in out


def test_drift_summary_window_excludes_old(substrate: Substrate) -> None:
    """Events older than `days` window must not count."""
    si = SelfInspectTool(substrate)
    _seed_event(substrate, "internal.initiative_blocked",
                payload={"reason": "old"}, days_ago=10)
    out = si.read_drift_summary(days=3)
    # No initiative_blocked should appear in the report
    assert "gate отклонил" not in out


def test_drift_summary_counts_work_volume(substrate: Substrate) -> None:
    si = SelfInspectTool(substrate)
    for _ in range(5):
        _seed_event(substrate, "internal.agent_session_outcome", days_ago=0.5)
    for _ in range(20):
        _seed_event(substrate, "internal.task_worker_outcome", days_ago=0.5)
    out = si.read_drift_summary(days=3)
    assert "active sessions: 5" in out
    assert "worker ticks: 20" in out


def test_drift_summary_days_arg_clamped(substrate: Substrate) -> None:
    """Sanity: invoke with various window sizes."""
    si = SelfInspectTool(substrate)
    # Should not crash on edge sizes
    si.read_drift_summary(days=1)
    si.read_drift_summary(days=7)
    si.read_drift_summary(days=30)
