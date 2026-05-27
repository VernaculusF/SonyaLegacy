"""Tests for the Operator panel admin endpoints.

Covers:
  GET  /api/operator/snapshot        — current cognitive state
  GET  /api/operator/live            — incremental event stream
  POST /api/operator/trigger-active  — appends external trigger event
  POST /api/operator/inject-message  — appends incoming message event
  POST /api/operator/task/{id}/action — fail / unblock / repurpose / delete
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sonya.admin.server import (
    api_operator_snapshot,
    api_operator_live_steps,
    api_operator_trigger_active,
    api_operator_inject_message,
    api_operator_task_action,
)
from sonya.config import AppConfig
from sonya.state import Substrate, seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.tasks.service import TaskService
from sonya.tasks.store import TaskStore


@pytest.fixture
async def admin_client(tmp_path: Path):
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    sub.close()  # let endpoints reopen on demand

    cfg = AppConfig(
        substrate_path=tmp_path / "test.db",
        health_path=tmp_path / "health.json",
        primary_user_tg_id="5785127604",
    )
    app = web.Application()
    app["config"] = cfg
    app["admin_password"] = ""
    app.router.add_get("/api/operator/snapshot", api_operator_snapshot)
    app.router.add_get("/api/operator/live", api_operator_live_steps)
    app.router.add_post("/api/operator/trigger-active", api_operator_trigger_active)
    app.router.add_post("/api/operator/inject-message", api_operator_inject_message)
    app.router.add_post("/api/operator/task/{task_id}/action", api_operator_task_action)

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    try:
        yield client, cfg
    finally:
        await client.close()


# --- snapshot ---


async def test_snapshot_basic(admin_client) -> None:
    client, cfg = admin_client
    resp = await client.get("/api/operator/snapshot")
    assert resp.status == 200
    data = await resp.json()
    assert "latest_seq" in data
    assert "open_tasks_summary" in data
    assert data["open_tasks_summary"]["in_progress"] == 0
    assert data["recent_picks"] == []
    assert data["active_session"] is None


async def test_snapshot_reflects_scheduler_picks(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path)
    try:
        ContinuityStream(sub).append(ContinuityEvent(
            kind="internal.scheduler_pick",
            payload={
                "chosen_kind": "active_session",
                "chosen_priority": 6,
                "chosen_reason": "cadence_elapsed",
                "runners_up": [],
            },
        ))
    finally:
        sub.close()
    resp = await client.get("/api/operator/snapshot")
    data = await resp.json()
    assert len(data["recent_picks"]) == 1
    assert data["last_pick"]["chosen_kind"] == "active_session"


async def test_snapshot_counts_failed_tasks(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        svc = TaskService(TaskStore(sub), stream=ContinuityStream(sub))
        t = svc.create(title="x", created_by="ivan")
        svc.fail(t.task_id, reason="test")
    finally:
        sub.close()
    resp = await client.get("/api/operator/snapshot")
    data = await resp.json()
    assert data["open_tasks_summary"]["recently_failed_24h"] == 1


# --- live ---


async def test_live_returns_recent_events(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        ContinuityStream(sub).append(ContinuityEvent(
            kind="internal.agent_step",
            payload={"step": 0, "type": "action", "tool": "web.fetch", "arg": "https://x"},
        ))
        ContinuityStream(sub).append(ContinuityEvent(
            kind="internal.agent_step",
            payload={"step": 1, "type": "done", "content": "[DONE: ok]"},
        ))
    finally:
        sub.close()
    resp = await client.get("/api/operator/live?since=0&limit=10")
    data = await resp.json()
    assert len(data["events"]) == 2
    assert data["events"][0]["data"]["tool"] == "web.fetch"


async def test_live_since_advances_cursor(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        ev = ContinuityStream(sub).append(ContinuityEvent(
            kind="internal.agent_step",
            payload={"step": 0, "type": "action", "tool": "x"},
        ))
        first_seq = ev.seq
    finally:
        sub.close()
    resp = await client.get(f"/api/operator/live?since={first_seq}")
    data = await resp.json()
    assert data["events"] == []


# --- trigger active session ---


async def test_trigger_active_appends_event(admin_client) -> None:
    client, cfg = admin_client
    resp = await client.post(
        "/api/operator/trigger-active",
        json={"reason": "smoke"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True
    assert data["reason"] == "smoke"
    assert data["event_seq"] > 0

    sub = Substrate.open(cfg.substrate_path)
    try:
        rows = sub.connection.execute(
            "SELECT kind, payload_json FROM continuity_events "
            "WHERE kind = 'internal.active_session_requested_external' "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchall()
    finally:
        sub.close()
    assert len(rows) == 1
    payload = json.loads(rows[0][1])
    assert payload["reason"] == "smoke"
    assert payload["source"] == "admin/operator"


async def test_trigger_active_default_reason(admin_client) -> None:
    client, _ = admin_client
    resp = await client.post(
        "/api/operator/trigger-active",
        json={},
    )
    data = await resp.json()
    assert data["reason"] == "operator_panel"


# --- inject message ---


async def test_inject_message_writes_event(admin_client) -> None:
    client, cfg = admin_client
    resp = await client.post(
        "/api/operator/inject-message",
        json={"text": "проверь mpbacademy через 5 минут"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    sub = Substrate.open(cfg.substrate_path)
    try:
        rows = sub.connection.execute(
            "SELECT kind, payload_json FROM continuity_events "
            "WHERE kind = 'incoming.telegram_message' "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchall()
    finally:
        sub.close()
    assert len(rows) == 1
    payload = json.loads(rows[0][1])
    assert payload["text"] == "проверь mpbacademy через 5 минут"
    assert payload["source"] == "admin/operator_inject"


async def test_inject_empty_text_rejected(admin_client) -> None:
    client, _ = admin_client
    resp = await client.post(
        "/api/operator/inject-message",
        json={"text": "   "},
    )
    assert resp.status == 400


# --- task actions ---


async def test_task_action_fail(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        svc = TaskService(TaskStore(sub), stream=ContinuityStream(sub))
        t = svc.create(title="dead-end", created_by="ivan")
    finally:
        sub.close()
    resp = await client.post(
        f"/api/operator/task/{t.task_id}/action",
        json={"action": "fail", "reason": "unreachable"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "failed"


async def test_task_action_repurpose_resets(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        svc = TaskService(TaskStore(sub), stream=ContinuityStream(sub))
        t = svc.create(title="retry-able", created_by="ivan")
        svc.fail(t.task_id, reason="first attempt died")
    finally:
        sub.close()
    resp = await client.post(
        f"/api/operator/task/{t.task_id}/action",
        json={"action": "repurpose", "reason": "different angle"},
    )
    data = await resp.json()
    assert data["status"] == "pending"

    sub = Substrate.open(cfg.substrate_path)
    try:
        row = sub.connection.execute(
            "SELECT status, blocker, sessions_used FROM tasks WHERE task_id=?",
            (t.task_id,),
        ).fetchone()
    finally:
        sub.close()
    assert row[0] == "pending"
    assert row[1] == ""
    assert row[2] == 0


async def test_task_action_delete(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        svc = TaskService(TaskStore(sub), stream=ContinuityStream(sub))
        t = svc.create(title="trash", created_by="ivan")
    finally:
        sub.close()
    resp = await client.post(
        f"/api/operator/task/{t.task_id}/action",
        json={"action": "delete"},
    )
    data = await resp.json()
    assert data["deleted"] is True

    sub = Substrate.open(cfg.substrate_path)
    try:
        cnt = sub.connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE task_id=?",
            (t.task_id,),
        ).fetchone()[0]
    finally:
        sub.close()
    assert cnt == 0


async def test_task_action_unknown_rejected(admin_client) -> None:
    client, cfg = admin_client
    sub = Substrate.open(cfg.substrate_path, read_only=False)
    try:
        svc = TaskService(TaskStore(sub), stream=ContinuityStream(sub))
        t = svc.create(title="x", created_by="ivan")
    finally:
        sub.close()
    resp = await client.post(
        f"/api/operator/task/{t.task_id}/action",
        json={"action": "explode"},
    )
    assert resp.status == 400


async def test_task_action_not_found(admin_client) -> None:
    client, _ = admin_client
    resp = await client.post(
        "/api/operator/task/task-not-real/action",
        json={"action": "fail"},
    )
    assert resp.status == 404
