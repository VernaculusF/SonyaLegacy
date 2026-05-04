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


def classify_prompt(text: str, has_media: bool = False) -> str:
    normalized = _maybe_fix_mojibake(str(text or "").strip()).lower()
    if not normalized:
        return "vision" if has_media else "text"
    if re.match(r"^/(?:img|image|imagine)(?:\s|$)", normalized):
        return "image_generation"
    if re.search(
        r"(?:^|[\s])(?:нарисуй|сгенерируй(?:\s+картинк[ауеи])?|создай(?:\s+изображение)?|generate\s+an?\s+image|draw|create\s+an?\s+image)\b",
        normalized,
    ):
        return "image_generation"
    return "vision" if has_media else "text"


def _mime_type_to_ext(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "video/mp4": ".mp4",
        "video/mpeg": ".mpeg",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
    }.get(mime_type, ".jpg")


def _normalized_prompt_for_mode(text: str, mode: str, attachments: list[dict[str, Any]]) -> str:
    if mode == "image_generation":
        return re.sub(r"^/(img|image|imagine)\s*", "", str(text or ""), flags=re.I).strip()
    if str(text or "").strip():
        return str(text).strip()
    sticker = next((item for item in attachments if item["kind"] == "sticker"), None)
    if sticker:
        return "Пользователь прислал стикер. Определи, что на нём изображено, и ответь естественно по контексту."
    video = next((item for item in attachments if item["kind"] in {"video", "document_video", "video_note"}), None)
    if video:
        return "Пользователь прислал видео. Определи, что происходит в ролике, и ответь естественно по контексту."
    if attachments:
        return "Пользователь прислал изображение. Определи, что на нём, и ответь естественно по контексту."
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

    video = message.get("video")
    if video:
        attachments.append(
            {
                "kind": "video",
                "file_id": video["file_id"],
                "file_unique_id": video.get("file_unique_id"),
                "mime_type": str(video.get("mime_type") or "video/mp4"),
                "ext": _mime_type_to_ext(str(video.get("mime_type") or "video/mp4")),
                "duration": video.get("duration"),
                "width": video.get("width"),
                "height": video.get("height"),
            }
        )

    video_note = message.get("video_note")
    if video_note:
        attachments.append(
            {
                "kind": "video_note",
                "file_id": video_note["file_id"],
                "file_unique_id": video_note.get("file_unique_id"),
                "mime_type": "video/mp4",
                "ext": ".mp4",
                "duration": video_note.get("duration"),
                "length": video_note.get("length"),
            }
        )

    document = message.get("document")
    if document:
        mime_type = str(document.get("mime_type", ""))
        if mime_type.startswith("image/"):
            attachments.append(
                {
                    "kind": "document_image",
                    "file_id": document["file_id"],
                    "file_unique_id": document.get("file_unique_id"),
                    "mime_type": mime_type,
                    "ext": Path(document.get("file_name") or "").suffix or _mime_type_to_ext(mime_type),
                    "file_name": document.get("file_name"),
                }
            )
        elif mime_type.startswith("video/"):
            attachments.append(
                {
                    "kind": "document_video",
                    "file_id": document["file_id"],
                    "file_unique_id": document.get("file_unique_id"),
                    "mime_type": mime_type,
                    "ext": Path(document.get("file_name") or "").suffix or _mime_type_to_ext(mime_type),
                    "file_name": document.get("file_name"),
                }
            )

    has_media = bool(attachments)
    mode = classify_prompt(text, has_media)
    prompt_text = _normalized_prompt_for_mode(text, mode, attachments)
    return TelegramInput(
        message=message,
        chat_id=chat_id,
        from_id=from_id,
        text=text,
        prompt_text=prompt_text,
        attachments=attachments,
        has_image=has_media,
        mode=mode,
    )


def parse_openrouter_event_stream(raw_text: str) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    normalized_text = str(raw_text or "").lstrip("\ufeff")
    for line in normalized_text.splitlines():
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

