from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from sonya.admin.server import create_app


async def test_api_without_token_returns_json_401_not_login_redirect(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test-token")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        response = await client.get("/api/projects", allow_redirects=False)
        payload = await response.json()

        assert response.status == 401
        assert response.headers.get("Location") is None
        assert payload == {"error": "auth"}
    finally:
        await client.close()


async def test_html_and_api_responses_carry_security_headers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "security.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test-token")
    client = TestClient(TestServer(create_app()), headers={"X-Atrium-Token": "test-token"})
    await client.start_server()
    try:
        html = await client.get("/")
        api = await client.get("/api/projects")

        for response in (html, api):
            csp = response.headers.get("Content-Security-Policy", "")
            assert "default-src 'self'" in csp
            assert "frame-ancestors 'none'" in csp
            assert response.headers.get("X-Content-Type-Options") == "nosniff"
            assert response.headers.get("Referrer-Policy") == "no-referrer"
            assert response.headers.get("X-Frame-Options") == "DENY"
    finally:
        await client.close()
