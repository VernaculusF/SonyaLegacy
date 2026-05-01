from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _maybe_fix_mojibake(text: str) -> str:
    if not isinstance(text, str):
        return text
    try:
        repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return text

    def cyr_count(value: str) -> int:
        return sum(1 for char in value if "\u0400" <= char <= "\u04ff")

    repaired_cyr = cyr_count(repaired)
    original_cyr = cyr_count(text)
    return repaired if repaired_cyr > original_cyr else text


def classify_prompt(text: str, has_image: bool = False) -> str:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return "vision" if has_image else "text"
    if re.match(r"^/(?:img|image|imagine)(?:\s|$)", normalized):
        return "image_generation"
    if re.search(
        r"(?:^|[\s])(?:РЅР°СЂРёСЃСѓР№|СЃРіРµРЅРµСЂРёСЂСѓР№(?:\s+РєР°СЂС‚РёРЅРє[Р°СѓРµРё])?|СЃРѕР·РґР°Р№(?:\s+РёР·РѕР±СЂР°Р¶РµРЅРёРµ)?|generate\s+an?\s+image|draw|create\s+an?\s+image)\b",
        normalized,
    ):
        return "image_generation"
    return "vision" if has_image else "text"


def _mime_type_to_ext(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime_type, ".jpg")


def _normalized_prompt_for_mode(text: str, mode: str, attachments: list[dict[str, Any]]) -> str:
    if mode == "image_generation":
        return re.sub(r"^/(img|image|imagine)\s*", "", str(text or ""), flags=re.I).strip()
    if str(text or "").strip():
        return str(text).strip()
    sticker = next((item for item in attachments if item["kind"] == "sticker"), None)
    if sticker:
        return "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРёСЃР»Р°Р» СЃС‚РёРєРµСЂ. РћРїСЂРµРґРµР»Рё, С‡С‚Рѕ РЅР° РЅС‘Рј РёР·РѕР±СЂР°Р¶РµРЅРѕ, Рё РѕС‚РІРµС‚СЊ РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ РїРѕ РєРѕРЅС‚РµРєСЃС‚Сѓ."
    if attachments:
        return "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРёСЃР»Р°Р» РёР·РѕР±СЂР°Р¶РµРЅРёРµ. РћРїСЂРµРґРµР»Рё, С‡С‚Рѕ РЅР° РЅС‘Рј, Рё РѕС‚РІРµС‚СЊ РµСЃС‚РµСЃС‚РІРµРЅРЅРѕ РїРѕ РєРѕРЅС‚РµРєСЃС‚Сѓ."
    return ""


@dataclass(slots=True)
class TelegramInput:
    message: dict[str, Any]
    chat_id: int | None
    from_id: int | None
    text: str
    prompt_text: str
    attachments: list[dict[str, Any]]
    has_image: bool
    mode: str


def extract_telegram_input(update: dict[str, Any]) -> TelegramInput | None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None

    text = _maybe_fix_mojibake(str(message.get("text") or message.get("caption") or "").strip())
    chat_id = (message.get("chat") or {}).get("id")
    from_id = (message.get("from") or {}).get("id")
    attachments: list[dict[str, Any]] = []

    photo = message.get("photo")
    if isinstance(photo, list) and photo:
        best = sorted(photo, key=lambda item: item.get("file_size", 0), reverse=True)[0]
        attachments.append(
            {
                "kind": "photo",
                "file_id": best["file_id"],
                "file_unique_id": best.get("file_unique_id"),
                "width": best.get("width"),
                "height": best.get("height"),
                "mime_type": "image/jpeg",
                "ext": ".jpg",
            }
        )

    sticker = message.get("sticker")
    if sticker:
        thumb = sticker.get("thumbnail") or sticker.get("thumb") or {}
        sticker_file_id = (
            sticker["file_id"]
            if not sticker.get("is_animated") and not sticker.get("is_video")
            else thumb.get("file_id") or sticker["file_id"]
        )
        attachments.append(
            {
                "kind": "sticker",
                "file_id": sticker_file_id,
                "file_unique_id": sticker.get("file_unique_id"),
                "emoji": sticker.get("emoji"),
                "is_animated": bool(sticker.get("is_animated")),
                "is_video": bool(sticker.get("is_video")),
                "mime_type": (
                    "image/webp"
                    if not sticker.get("is_animated") and not sticker.get("is_video")
                    else "image/jpeg"
                ),
                "ext": (
                    ".webp"
                    if not sticker.get("is_animated") and not sticker.get("is_video")
                    else ".jpg"
                ),
            }
        )

    document = message.get("document")
    if document and str(document.get("mime_type", "")).startswith("image/"):
        attachments.append(
            {
                "kind": "document_image",
                "file_id": document["file_id"],
                "file_unique_id": document.get("file_unique_id"),
                "mime_type": document["mime_type"],
                "ext": Path(document.get("file_name") or "").suffix or _mime_type_to_ext(document["mime_type"]),
                "file_name": document.get("file_name"),
            }
        )

    has_image = bool(attachments)
    mode = classify_prompt(text, has_image)
    prompt_text = _normalized_prompt_for_mode(text, mode, attachments)
    return TelegramInput(
        message=message,
        chat_id=chat_id,
        from_id=from_id,
        text=text,
        prompt_text=prompt_text,
        attachments=attachments,
        has_image=has_image,
        mode=mode,
    )


def parse_openrouter_event_stream(raw_text: str) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    for line in str(raw_text or "").splitlines():
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if not data or data == "[DONE]":
            continue
        try:
            chunks.append(json.loads(data))
        except json.JSONDecodeError:
            continue

    content_parts: list[str] = []
    images: list[dict[str, Any]] = []
    finish_reason = None
    for chunk in chunks:
        choice = (chunk.get("choices") or [{}])[0]
        delta = choice.get("delta") or {}
        if isinstance(delta.get("content"), str) and delta["content"]:
            content_parts.append(delta["content"])
        if isinstance(delta.get("images"), list):
            images.extend(delta["images"])
        if choice.get("finish_reason"):
            finish_reason = choice["finish_reason"]
    return {
        "chunks": chunks,
        "text": "".join(content_parts).strip(),
        "images": images,
        "finishReason": finish_reason,
    }
