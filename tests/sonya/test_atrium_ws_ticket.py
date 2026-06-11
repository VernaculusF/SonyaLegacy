from __future__ import annotations

import pytest
from aiohttp import WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer

from sonya.admin.server import create_app


@pytest.mark.asyncio
async def test_ws_ticket_endpoint_requires_atrium_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "ws-ticket.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test-token")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        unauth = await client.post("/api/atrium/ws-ticket")
        assert unauth.status == 401

        auth = await client.post(
            "/api/atrium/ws-ticket",
            headers={"X-Atrium-Token": "test-token"},
        )
        payload = await auth.json()

        assert auth.status == 200
        assert payload["ok"] is True
        assert isinstance(payload["ticket"], str)
        assert len(payload["ticket"]) >= 32
        assert payload["ttl_seconds"] <= 60
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ws_feed_accepts_one_time_ticket_and_rejects_reuse(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "ws-ticket.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test-token")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        response = await client.post(
            "/api/atrium/ws-ticket",
            headers={"X-Atrium-Token": "test-token"},
        )
        ticket = (await response.json())["ticket"]

        ws = await client.ws_connect(f"/atrium/feed?since_seq=0&backlog=0&ticket={ticket}")
        await ws.close()

        with pytest.raises(WSServerHandshakeError):
            await client.ws_connect(f"/atrium/feed?since_seq=0&backlog=0&ticket={ticket}")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ws_feed_rejects_admin_token_in_query(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "ws-ticket.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test-token")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        with pytest.raises(WSServerHandshakeError):
            await client.ws_connect("/atrium/feed?since_seq=0&backlog=0&token=test-token")
    finally:
        await client.close()
