from __future__ import annotations

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from sonya.admin.server import api_dashboard
from sonya.config import AppConfig
from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate


async def test_dashboard_reports_substrate_provider_settings(tmp_path) -> None:
    db = tmp_path / "admin.db"
    sub = Substrate.open(db)
    try:
        KeyStore(sub).set_settings(
            active_provider="nous",
            default_model="",
            default_base_url="https://inference-api.nousresearch.com/v1",
        )
    finally:
        sub.close()

    app = web.Application()
    app["config"] = AppConfig(
        substrate_path=db,
        health_path=tmp_path / "health.json",
    )
    app.router.add_get("/api/dashboard", api_dashboard)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        response = await client.get("/api/dashboard")
        payload = await response.json()
        assert payload["provider_settings"]["active_provider"] == "nous"
        assert payload["provider_settings"]["default_model"] == ""
        assert "llm_model" not in payload["config"]
        assert "llm_api_base" not in payload["config"]
    finally:
        await client.close()
