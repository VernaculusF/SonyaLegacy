from pathlib import Path

import httpx
import pytest

from tg_bridge.telegram_api import download_telegram_attachment, get_updates


@pytest.mark.asyncio
async def test_get_updates_calls_telegram_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.telegram.org/bottoken/getUpdates")
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 1}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_updates("token", 5, client=client)
    assert result == [{"update_id": 1}]


@pytest.mark.asyncio
async def test_download_telegram_attachment_downloads_and_wraps_media(tmp_path: Path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url == httpx.URL("https://api.telegram.org/bottoken/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "photos/file.jpg"}})
        if request.url == httpx.URL("https://api.telegram.org/file/bottoken/photos/file.jpg"):
            return httpx.Response(200, content=b"fake-jpg")
        raise AssertionError(f"unexpected url {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        attachment = await download_telegram_attachment(
            "token",
            {"kind": "photo", "file_id": "photo-id", "file_unique_id": "uniq", "mime_type": "image/jpeg", "ext": ".jpg"},
            tmp_path,
            client=client,
        )
    assert len(calls) == 2
    assert attachment["local_path"].exists()
    assert attachment["data_url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_download_telegram_attachment_preserves_video_mime_type(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == httpx.URL("https://api.telegram.org/bottoken/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "videos/file.mp4"}})
        if request.url == httpx.URL("https://api.telegram.org/file/bottoken/videos/file.mp4"):
            return httpx.Response(200, content=b"fake-mp4")
        raise AssertionError(f"unexpected url {request.url}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        attachment = await download_telegram_attachment(
            "token",
            {"kind": "video", "file_id": "video-id", "file_unique_id": "uniq", "mime_type": "video/mp4", "ext": ".mp4"},
            tmp_path,
            client=client,
        )
    assert attachment["local_path"].suffix == ".mp4"
    assert attachment["mime_type"] == "video/mp4"
    assert attachment["data_url"].startswith("data:video/mp4;base64,")

