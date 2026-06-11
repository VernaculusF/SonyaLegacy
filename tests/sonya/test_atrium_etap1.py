"""Atrium Этап 1 — dialog composer (T1.4) + TG emergency-only mode (T1.5).

Tests for:
- /api/atrium/dialog + /api/atrium/heartbeat routes registered
- atrium_dialog records incoming.atrium_dialog + triggers active session
- atrium_heartbeat writes atrium_last_seen to technical runtime state
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
from sonya.state.runtime_state import RuntimeStateStore
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
    assert "/api/atrium/events-history" in routes


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
        RuntimeStateStore(sub).set(
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
        RuntimeStateStore(sub).set("atrium_last_seen", old.isoformat())
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
        RuntimeStateStore(sub).set(
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
        RuntimeStateStore(sub).set(
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


# ---------------------------------------------------------------------------
# Atrium media attachments (uploads + dialog refs + serve) + workshop lockdown
# ---------------------------------------------------------------------------


def test_atrium_media_routes_registered(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test")
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import create_app

    app = create_app()
    routes = {r.resource.canonical for r in app.router.routes()}
    assert "/api/atrium/upload" in routes
    assert "/api/atrium/media/{name}" in routes


def test_app_client_max_size_raised(tmp_path: Path, monkeypatch) -> None:
    """Body limit must be well above the 1 MB default so attachments fit."""
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test")
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import create_app

    app = create_app()
    assert app._client_max_size >= 16 * 1024 * 1024


def test_dialog_accepts_attachments(tmp_path: Path, monkeypatch) -> None:
    """atrium_dialog records media_path/media_mime into the incoming event."""
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from aiohttp.test_utils import make_mocked_request
    from sonya.admin.server import atrium_dialog
    from sonya.config import load_config

    cfg = load_config()

    class _Req:
        def __init__(self, app, body):
            self.app = app
            self._body = body
            self.headers = {}
            self.query = {}

        async def json(self):
            return self._body

    app = {"config": cfg, "admin_password": ""}
    body = {
        "text": "посмотри это видео",
        "attachments": [{
            "name": "atrium_abc.mp4",
            "media_path": str(tmp_path / "atrium_abc.mp4"),
            "media_mime": "video/mp4",
            "media_kind": "видео",
        }],
    }
    resp = asyncio.run(atrium_dialog(_Req(app, body)))
    assert resp.status == 200

    sub = Substrate.open(tmp_path / "test.db")
    try:
        events = list(ContinuityStream(sub).read_since(0))
        inc = [e for e in events if e.kind == "incoming.atrium_dialog"]
        assert len(inc) == 1
        p = inc[0].payload
        assert p["text"] == "посмотри это видео"
        assert p["media_mime"] == "video/mp4"
        assert p["media_kind"] == "видео"
        assert len(p["attachments"]) == 1
    finally:
        sub.close()


def test_dialog_rejects_attachment_from_another_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import atrium_dialog
    from sonya.config import load_config

    cfg = load_config()

    class _Req:
        def __init__(self, app, body):
            self.app = app
            self._body = body
            self.headers = {}
            self.query = {}

        async def json(self):
            return self._body

    app = {"config": cfg, "admin_password": ""}
    body = {
        "text": "wrong project",
        "workspace_id": "proj-target",
        "attachments": [{
            "name": "atrium_abc.txt",
            "media_path": str(tmp_path / "atrium_abc.txt"),
            "media_mime": "text/plain",
            "media_kind": "text",
            "workspace_id": "proj-other",
        }],
    }
    resp = asyncio.run(atrium_dialog(_Req(app, body)))
    assert resp.status == 400
    assert "workspace" in resp.text


def test_dialog_accepts_attachment_bound_to_same_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import atrium_dialog
    from sonya.config import load_config
    from sonya.project import ProjectStore

    cfg = load_config()
    sub = Substrate.open(tmp_path / "test.db")
    project = ProjectStore(sub).create("attachment project")
    sub.close()

    class _Req:
        def __init__(self, app, body):
            self.app = app
            self._body = body
            self.headers = {}
            self.query = {}

        async def json(self):
            return self._body

    app = {"config": cfg, "admin_password": ""}
    body = {
        "text": "right project",
        "workspace_id": project.project_id,
        "attachments": [{
            "name": "atrium_abc.txt",
            "media_path": str(tmp_path / "atrium_abc.txt"),
            "media_mime": "text/plain",
            "media_kind": "text",
            "workspace_id": project.project_id,
        }],
    }
    resp = asyncio.run(atrium_dialog(_Req(app, body)))
    assert resp.status == 200


def test_dialog_rejects_empty_no_attachment(tmp_path: Path) -> None:
    from sonya.admin.server import atrium_dialog
    from sonya.config import load_config

    cfg = load_config()

    class _Req:
        def __init__(self, app):
            self.app = app
            self.headers = {}
            self.query = {}

        async def json(self):
            return {}

    app = {"config": cfg, "admin_password": ""}
    resp = asyncio.run(atrium_dialog(_Req(app)))
    assert resp.status == 400


def test_dialog_records_workspace_id_and_history_filters_by_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import atrium_dialog, atrium_history
    from sonya.config import load_config
    from sonya.project import ProjectStore

    cfg = load_config()
    sub = Substrate.open(tmp_path / "test.db")
    project = ProjectStore(sub).create("history project")
    sub.close()

    class _Req:
        def __init__(self, app, body=None, query=None):
            self.app = app
            self._body = body or {}
            self.headers = {}
            self.query = query or {}

        async def json(self):
            return self._body

    app = {"config": cfg, "admin_password": ""}
    body_main = {"text": "main chat"}
    body_ws = {"text": "project chat", "workspace_id": project.project_id}
    assert asyncio.run(atrium_dialog(_Req(app, body_main))).status == 200
    assert asyncio.run(atrium_dialog(_Req(app, body_ws))).status == 200

    resp_ws = asyncio.run(atrium_history(_Req(app, query={"before_seq": "0", "limit": "20", "workspace_id": project.project_id})))
    assert resp_ws.status == 200
    import json as _json
    data_ws = _json.loads(resp_ws.text)
    assert len(data_ws["events"]) == 1
    assert data_ws["events"][0]["payload"]["workspace_id"] == project.project_id

    resp_main = asyncio.run(atrium_history(_Req(app, query={"before_seq": "0", "limit": "20"})))
    assert resp_main.status == 200
    data_main = _json.loads(resp_main.text)
    assert len(data_main["events"]) == 1
    assert data_main["events"][0]["text"] == "main chat"


def test_history_initial_page_returns_newest_dialog_events(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "history-newest.db"))
    from sonya.admin.server import atrium_dialog, atrium_history
    from sonya.config import load_config

    cfg = load_config()

    class _Req:
        def __init__(self, app, body=None, query=None):
            self.app = app
            self._body = body or {}
            self.headers = {}
            self.query = query or {}

        async def json(self):
            return self._body

    app = {"config": cfg, "admin_password": ""}
    for text in ("history one", "history two", "history three"):
        assert asyncio.run(atrium_dialog(_Req(app, {"text": text}))).status == 200

    resp = asyncio.run(atrium_history(_Req(app, query={"before_seq": "0", "limit": "2"})))
    assert resp.status == 200
    import json as _json
    data = _json.loads(resp.text)
    assert [event["text"] for event in data["events"]] == ["history two", "history three"]
    assert data["has_more"] is True


def test_history_excludes_telegram_social_channel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "history-no-tg.db"))
    from sonya.admin.server import atrium_dialog, atrium_history
    from sonya.config import load_config

    cfg = load_config()
    sub = Substrate.open(tmp_path / "history-no-tg.db")
    try:
        stream = ContinuityStream(sub)
        stream.append(ContinuityEvent(kind="incoming.telegram_message", channel="telegram", payload={"text": "tg social"}))
        stream.append(ContinuityEvent(kind="outgoing.telegram_response", channel="telegram", payload={"text": "tg reply"}))
    finally:
        sub.close()

    class _Req:
        def __init__(self, app, body=None, query=None):
            self.app = app
            self._body = body or {}
            self.headers = {}
            self.query = query or {}

        async def json(self):
            return self._body

    app = {"config": cfg, "admin_password": ""}
    assert asyncio.run(atrium_dialog(_Req(app, {"text": "atrium only"}))).status == 200

    resp = asyncio.run(atrium_history(_Req(app, query={"before_seq": "0", "limit": "20"})))
    assert resp.status == 200
    import json as _json
    data = _json.loads(resp.text)
    assert [event["text"] for event in data["events"]] == ["atrium only"]


def test_events_history_returns_non_private_scrollback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "events-history.db"))
    from sonya.admin.server import atrium_events_history
    from sonya.config import load_config

    cfg = load_config()
    sub = Substrate.open(tmp_path / "events-history.db")
    try:
        stream = ContinuityStream(sub)
        stream.append(ContinuityEvent(kind="internal.thought", channel="mind", payload={"text": "hidden"}, private=True))
        stream.append(ContinuityEvent(kind="internal.agent_step", channel="active", payload={"tool": "shell.run"}))
        stream.append(ContinuityEvent(kind="outgoing.worker_log", channel="worker_log", payload={"text": "worker"}))
    finally:
        sub.close()

    class _Req:
        def __init__(self, app, query=None):
            self.app = app
            self.headers = {}
            self.query = query or {}

    app = {"config": cfg, "admin_password": ""}
    resp = asyncio.run(atrium_events_history(_Req(app, query={"before_seq": "0", "limit": "10"})))
    assert resp.status == 200
    import json as _json
    data = _json.loads(resp.text)
    assert [event["kind"] for event in data["events"]] == ["internal.agent_step", "outgoing.worker_log"]
    assert all(event["payload"].get("text") != "hidden" for event in data["events"])


def test_dialog_resumes_waiting_choice_project(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))
    from sonya.admin.server import atrium_dialog
    from sonya.config import load_config
    from sonya.project import ProjectStore

    cfg = load_config()
    sub = Substrate.open(tmp_path / "test.db")
    project = ProjectStore(sub).create("choice project")
    ProjectStore(sub).set_status(project.project_id, "waiting_choice")
    sub.close()

    class _Req:
        def __init__(self, app):
            self.app = app
            self.headers = {}
            self.query = {}

        async def json(self):
            return {"text": "выбираю вариант два", "workspace_id": project.project_id}

    resp = asyncio.run(atrium_dialog(_Req({"config": cfg, "admin_password": ""})))
    assert resp.status == 200
    sub = Substrate.open(tmp_path / "test.db")
    try:
        assert ProjectStore(sub).get(project.project_id).status == "in_progress"
    finally:
        sub.close()


@pytest.mark.parametrize("status", ["waiting", "completed", "cancelled"])
def test_dialog_rejects_read_only_project_status(tmp_path: Path, monkeypatch, status: str) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / f"{status}.db"))
    from sonya.admin.server import atrium_dialog
    from sonya.config import load_config
    from sonya.project import ProjectStore

    cfg = load_config()
    sub = Substrate.open(tmp_path / f"{status}.db")
    project = ProjectStore(sub).create(f"{status} project")
    ProjectStore(sub).set_status(project.project_id, status)
    sub.close()

    class _Req:
        def __init__(self, app):
            self.app = app
            self.headers = {}
            self.query = {}

        async def json(self):
            return {"text": "продолжай", "workspace_id": project.project_id}

    resp = asyncio.run(atrium_dialog(_Req({"config": cfg, "admin_password": ""})))
    assert resp.status == 409
    assert status in resp.text


def test_workshop_read_write_disabled(tmp_path: Path) -> None:
    """Workshop is list-only — read and write return 403 for all kinds."""
    from sonya.admin.workshop import workshop_read, workshop_write

    class _Req:
        def __init__(self):
            self.app = {"admin_password": ""}
            self.headers = {}
            self.query = {"kind": "skills", "path": "x.py"}

        async def json(self):
            return {"kind": "skills", "path": "x.py", "content": "x = 1"}

    r1 = asyncio.run(workshop_read(_Req()))
    assert r1.status == 403
    r2 = asyncio.run(workshop_write(_Req()))
    assert r2.status == 403
