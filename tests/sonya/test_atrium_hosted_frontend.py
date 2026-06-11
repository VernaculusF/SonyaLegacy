from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from sonya.admin import server
from sonya.admin.server import create_app


async def test_hosted_atrium_serves_index_assets_and_spa_fallback(
    tmp_path,
    monkeypatch,
) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>atrium-hosted</html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('atrium')", encoding="utf-8")

    monkeypatch.setattr(server, "_ATRIUM_DIST_DIR", dist)
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "atrium-hosted.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        index = await client.get("/atrium/")
        asset = await client.get("/atrium/assets/app.js")
        fallback = await client.get("/atrium/projects/proj-1")

        assert index.status == 200
        assert "atrium-hosted" in await index.text()
        assert asset.status == 200
        assert "console.log" in await asset.text()
        assert fallback.status == 200
        assert "atrium-hosted" in await fallback.text()
    finally:
        await client.close()


async def test_hosted_atrium_returns_503_when_bundle_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "_ATRIUM_DIST_DIR", tmp_path / "missing")
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "atrium-hosted.db"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "")
    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        response = await client.get("/atrium/")
        payload = await response.json()

        assert response.status == 503
        assert payload["error"] == "atrium_bundle_missing"
    finally:
        await client.close()


def test_vite_build_targets_hosted_atrium_base() -> None:
    source = (server._ATRIUM_DIST_DIR.parent / "vite.config.js").read_text(encoding="utf-8")
    assert "base: '/atrium/'" in source
