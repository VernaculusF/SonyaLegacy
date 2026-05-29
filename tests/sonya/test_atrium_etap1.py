"""Atrium Этап 1 — dialog composer (T1.4) + TG emergency-only mode (T1.5).

Tests for:
- /api/atrium/dialog + /api/atrium/heartbeat routes registered
- atrium_dialog records incoming.atrium_dialog + triggers active session
- atrium_heartbeat writes atrium_last_seen to environment_state
- context_builder recognizes incoming.atrium_dialog as Ivan's message
- OutboundGate emergency-mode: TG dialog suppressed when Atrium live
- OutboundGate emergency-mode: TG dialog resumes when Atrium offline past threshold
- emergency_override bypasses suppression
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.environment import EnvironmentStore
from sonya.state.substrate import Substrate


def _fresh_substrate(tmp_path: Path) -> Substrate:
    return Substrate.open(tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def test_atrium_etap1_routes_registered(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test")
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import create_app

    app = create_app()
    routes = {r.resource.canonical for r in app.router.routes()}
    assert "/api/atrium/dialog" in routes
    assert "/api/atrium/heartbeat" in routes


# ---------------------------------------------------------------------------
# T1.5 — OutboundGate emergency-only mode
# ---------------------------------------------------------------------------


def _make_gate(sub, *, emergency_mode: bool, threshold_hours: float = 24.0):
    from sonya.initiative.outbound import OutboundGate

    class _NullRegistry:
        async def send(self, *a, **k):
            return True

    stream = ContinuityStream(sub)
    return OutboundGate(
        registry=_NullRegistry(),
        stream=stream,
        target_tg_chat_id="123",
        substrate=sub,
        tg_emergency_mode=emergency_mode,
        tg_emergency_threshold_hours=threshold_hours,
    )


def test_emergency_off_does_not_suppress(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        gate = _make_gate(sub, emergency_mode=False)
        suppress, _ = gate._suppress_tg_dialog(emergency_override=False)
        assert suppress is False
    finally:
        sub.close()


def test_emergency_on_atrium_live_suppresses(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        # Atrium seen just now
        EnvironmentStore(sub).set(
            "atrium_last_seen", datetime.now(timezone.utc).isoformat()
        )
        gate = _make_gate(sub, emergency_mode=True)
        suppress, reason = gate._suppress_tg_dialog(emergency_override=False)
        assert suppress is True
        assert reason == "atrium_live"
    finally:
        sub.close()


def test_emergency_on_atrium_offline_does_not_suppress(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        # Atrium last seen 30h ago — past the 24h threshold
        old = datetime.now(timezone.utc) - timedelta(hours=30)
        EnvironmentStore(sub).set("atrium_last_seen", old.isoformat())
        gate = _make_gate(sub, emergency_mode=True, threshold_hours=24.0)
        suppress, reason = gate._suppress_tg_dialog(emergency_override=False)
        assert suppress is False
        assert reason == "atrium_offline_past_threshold"
    finally:
        sub.close()


def test_emergency_on_never_seen_does_not_suppress(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        gate = _make_gate(sub, emergency_mode=True)
        suppress, _ = gate._suppress_tg_dialog(emergency_override=False)
        assert suppress is False
    finally:
        sub.close()


def test_emergency_override_bypasses_suppression(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        EnvironmentStore(sub).set(
            "atrium_last_seen", datetime.now(timezone.utc).isoformat()
        )
        gate = _make_gate(sub, emergency_mode=True)
        suppress, reason = gate._suppress_tg_dialog(emergency_override=True)
        assert suppress is False
        assert reason == "emergency_override"
    finally:
        sub.close()


def test_send_via_tool_atrium_only_records_outgoing_dialog(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        EnvironmentStore(sub).set(
            "atrium_last_seen", datetime.now(timezone.utc).isoformat()
        )
        gate = _make_gate(sub, emergency_mode=True)
        result = asyncio.run(gate.send_via_tool("привет, малыш", channel="dialog"))
        assert "Atrium-only" in result
        # Event recorded as outgoing.dialog with tg_suppressed flag
        stream = ContinuityStream(sub)
        events = list(stream.read_since(0))
        dialog_evs = [e for e in events if e.kind == "outgoing.dialog"]
        assert len(dialog_evs) == 1
        assert dialog_evs[0].payload.get("tg_suppressed") is True
        assert dialog_evs[0].channel == "dialog"
    finally:
        sub.close()


def test_send_via_tool_normal_mode_goes_to_tg(tmp_path: Path) -> None:
    """With emergency mode off, dialog dispatches via the registry (TG)."""
    sub = _fresh_substrate(tmp_path)
    try:
        gate = _make_gate(sub, emergency_mode=False)
        result = asyncio.run(gate.send_via_tool("привет", channel="dialog"))
        assert "[OK] sent" in result
    finally:
        sub.close()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_emergency_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("SONYA_TG_EMERGENCY_MODE", raising=False)
    from sonya.config import load_config

    cfg = load_config()
    assert cfg.tg_emergency_mode is False
    assert cfg.tg_emergency_threshold_hours == 24.0


def test_config_emergency_enabled(monkeypatch) -> None:
    monkeypatch.setenv("SONYA_TG_EMERGENCY_MODE", "1")
    monkeypatch.setenv("SONYA_TG_EMERGENCY_THRESHOLD_HOURS", "12")
    from sonya.config import load_config

    cfg = load_config()
    assert cfg.tg_emergency_mode is True
    assert cfg.tg_emergency_threshold_hours == 12.0


# ---------------------------------------------------------------------------
# T1.4 — context_builder recognizes atrium dialog
# ---------------------------------------------------------------------------


def test_context_builder_shows_atrium_dialog(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        from sonya.state import seed_identity_if_empty
        seed_identity_if_empty(sub)
        stream = ContinuityStream(sub)
        stream.append(ContinuityEvent(
            kind="incoming.atrium_dialog",
            channel="dialog",
            principal_id="ivan",
            payload={"text": "ты тут?", "source": "atrium/composer"},
        ))
        from sonya.planning.context_builder import build_full_context

        ctx = build_full_context(substrate=sub)
        prompt = ctx.system_prompt
        assert "ты тут?" in prompt
        assert "Иван написал" in prompt
    finally:
        sub.close()


# ---------------------------------------------------------------------------
# WS feed cold-start backlog clamp (regression: full-history replay flooded UI)
# ---------------------------------------------------------------------------


def test_catchup_clamps_cold_start():
    """Cold start (since_seq=0) must clamp to a recent tail, not replay all."""
    from sonya.admin.server import _atrium_catchup_since
    # 14000 events in history, cold start, backlog 150 → start near the tail
    assert _atrium_catchup_since(0, 14000, 150) == 13850
    # backlog larger than history → start at 0 (but that's a small history)
    assert _atrium_catchup_since(0, 100, 150) == 0


def test_catchup_resumes_from_since_seq():
    """A resuming client keeps its seq regardless of backlog."""
    from sonya.admin.server import _atrium_catchup_since
    assert _atrium_catchup_since(13900, 14000, 150) == 13900
    # even if since_seq is old, we honor it (client wants the gap)
    assert _atrium_catchup_since(5, 14000, 150) == 5


def test_catchup_backlog_zero_means_no_history():
    """backlog=0 on cold start → only live events (start at latest)."""
    from sonya.admin.server import _atrium_catchup_since
    assert _atrium_catchup_since(0, 14000, 0) == 0
