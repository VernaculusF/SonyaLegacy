from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from tg_bridge.formatting import chunk_plain_text, render_telegram_html


class TelegramApiError(RuntimeError):
    pass


def _ext_from_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "video/mp4": ".mp4",
        "video/mpeg": ".mpeg",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
    }.get(mime_type, ".jpg")


def _guess_mime_type(file_path: Path, fallback: str = "image/jpeg") -> str:
    return {
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".mp4": "video/mp4",
        ".mpeg": "video/mpeg",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
    }.get(file_path.suffix.lower(), fallback)


async def telegram_request(
    token: str,
    method: str,
    body: dict[str, str],
    client: httpx.AsyncClient | None = None,
    timeout: float | httpx.Timeout | None = None,
) -> Any:
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/{method}",
            data=body,
            timeout=timeout,
        )
        payload = response.json() if response.content else None
        if not response.is_success or not payload or not payload.get("ok"):
            raise TelegramApiError(f"{method} failed: {(payload or {}).get('description') or response.reason_phrase}")
        return payload["result"]
    finally:
        if own_client:
            await client.aclose()


async def get_updates(
    token: str,
    offset: int,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    return await telegram_request(
        token,
        "getUpdates",
        {
            "offset": str(offset),
            "timeout": "25",
            "allowed_updates": '["message","edited_message"]',
        },
        client=client,
        timeout=httpx.Timeout(35.0, connect=10.0),
    )


async def send_telegram_message(
    token: str,
    chat_id: int,
    text: str,
    client: httpx.AsyncClient | None = None,
    log_error=None,
) -> None:
    for chunk in chunk_plain_text(text, 3500):
        html = render_telegram_html(chunk)
        try:
            await telegram_request(
                token,
                "sendMessage",
                {
                    "chat_id": str(chat_id),
                    "text": html or chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
                client=client,
            )
        except Exception as err:
            if log_error:
                log_error(f"sendMessage HTML fallback: {err}")
            await telegram_request(
                token,
                "sendMessage",
                {
                    "chat_id": str(chat_id),
                    "text": chunk,
                    "disable_web_page_preview": "true",
                },
                client=client,
            )


async def send_telegram_photo(
    token: str,
    chat_id: int,
    file_path: Path,
    caption: str = "",
    client: httpx.AsyncClient | None = None,
) -> Any:
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        files = {"photo": (file_path.name, file_path.read_bytes())}
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption[:1024]
            data["parse_mode"] = "HTML"
        response = await client.post(f"https://api.telegram.org/bot{token}/sendPhoto", data=data, files=files)
        payload = response.json() if response.content else None
        if not response.is_success or not payload or not payload.get("ok"):
            raise TelegramApiError(f"sendPhoto failed: {(payload or {}).get('description') or response.reason_phrase}")
        return payload["result"]
    finally:
        if own_client:
            await client.aclose()


async def download_telegram_attachment(
    token: str,
    attachment: dict[str, Any],
    inbound_media_dir: Path,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        file_info = await telegram_request(
            token,
            "getFile",
            {"file_id": attachment["file_id"]},
            client=client,
        )
        file_path = file_info.get("file_path")
        if not file_path:
            raise TelegramApiError(f"getFile returned no file_path for {attachment.get('kind')}")
        response = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
        if not response.is_success:
            raise TelegramApiError(f"file download failed: {response.status_code} {response.reason_phrase}")

        inbound_media_dir.mkdir(parents=True, exist_ok=True)
        ext = attachment.get("ext") or _ext_from_mime(str(attachment.get("mime_type") or "image/jpeg"))
        local_path = inbound_media_dir / f"{attachment.get('kind', 'file')}---{attachment.get('file_unique_id') or 'tmp'}{ext}"
        local_path.write_bytes(response.content)
        mime_type = str(attachment.get("mime_type") or _guess_mime_type(local_path))
        data_url = f"data:{mime_type};base64,{base64.b64encode(response.content).decode('ascii')}"
        return {
            **attachment,
            "local_path": local_path,
            "mime_type": mime_type,
            "data_url": data_url,
        }
    finally:
        if own_client:
            await client.aclose()

