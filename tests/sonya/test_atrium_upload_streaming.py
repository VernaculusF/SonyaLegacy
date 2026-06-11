from __future__ import annotations

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from sonya.admin.server import create_app


async def _client(tmp_path, monkeypatch, *, max_bytes: int = 1024 * 1024) -> TestClient:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "upload.db"))
    monkeypatch.setenv("SONYA_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test-token")
    monkeypatch.setenv("SONYA_ATRIUM_MAX_UPLOAD_BYTES", str(max_bytes))
    client = TestClient(
        TestServer(create_app()),
        headers={"X-Atrium-Token": "test-token"},
    )
    await client.start_server()
    return client


async def test_streamed_upload_is_atomically_published(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        form = FormData()
        form.add_field(
            "file",
            b"x" * (128 * 1024),
            filename="large.bin",
            content_type="application/octet-stream",
        )
        response = await client.post("/api/atrium/upload", data=form)
        payload = await response.json()

        assert response.status == 200
        assert payload["size"] == 128 * 1024
        media_dir = tmp_path / "media"
        assert (media_dir / payload["name"]).is_file()
        assert not list(media_dir.glob("*.part"))
    finally:
        await client.close()


async def test_streamed_upload_limit_removes_partial_file(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch, max_bytes=64 * 1024)
    try:
        form = FormData()
        form.add_field(
            "file",
            b"x" * (128 * 1024),
            filename="too-large.bin",
            content_type="application/octet-stream",
        )
        response = await client.post("/api/atrium/upload", data=form)

        assert response.status == 413
        assert list((tmp_path / "media").iterdir()) == []
    finally:
        await client.close()


async def test_invalid_workspace_upload_removes_staged_file(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        form = FormData()
        form.add_field("workspace_id", "proj-missing")
        form.add_field("file", b"hello", filename="note.txt", content_type="text/plain")
        response = await client.post("/api/atrium/upload", data=form)

        assert response.status == 404
        assert list((tmp_path / "media").iterdir()) == []
    finally:
        await client.close()
