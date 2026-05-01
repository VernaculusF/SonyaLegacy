from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from telegram_userbot.media import parse_openrouter_event_stream


IMAGE_GENERATION_MODEL = "openrouter/google/gemini-3.1-flash-image-preview"


def resolve_model_name(cfg: dict[str, Any]) -> str:
    configured = str((((cfg.get("agents") or {}).get("defaults") or {}).get("model")) or "")
    parts = configured.split("/")
    return "/".join(parts[1:]) if parts and parts[0] == "omniroute" else configured


def build_text_payload(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": 1600,
        "temperature": 0.7,
    }


def build_vision_payload(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": 1600,
        "temperature": 0.4,
    }


def build_image_generation_payload(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": IMAGE_GENERATION_MODEL,
        "messages": messages,
        "modalities": ["image", "text"],
        "stream": True,
    }


def serialize_user_content(prompt_text: str, media_items: list[dict[str, Any]] | None = None) -> str | list[dict[str, Any]]:
    media_items = media_items or []
    if not media_items:
        return prompt_text
    return [
        {"type": "text", "text": prompt_text},
        *[
            {
                "type": "image_url",
                "image_url": {"url": item["data_url"]},
            }
            for item in media_items
        ],
    ]


def parse_model_payload(text: str) -> dict[str, Any] | None:
    import json

    trimmed = str(text or "").strip()
    if not trimmed:
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        pass
    start = trimmed.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(trimmed)):
        char = trimmed[idx]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(trimmed[start : idx + 1])
    return None


def extract_answer_from_payload(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    choice = (payload.get("choices") or [{}])[0]
    content = ((choice.get("message") or {}).get("content"))
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        joined = "".join(part if isinstance(part, str) else str(part.get("text", "")) for part in content)
        return joined.strip()
    text = choice.get("text")
    return str(text).strip() if text else ""


async def _chat_completion(
    provider: dict[str, Any],
    body: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    accept: str | None = None,
) -> str:
    own_client = client is None
    client = client or httpx.AsyncClient()
    try:
        headers = {
            "authorization": f"Bearer {provider['apiKey']}",
            "content-type": "application/json",
        }
        if accept:
            headers["accept"] = accept
        response = await client.post(f"{provider['baseUrl'].rstrip('/')}/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        return response.text
    finally:
        if own_client:
            await client.aclose()


async def complete_text(
    provider: dict[str, Any],
    model: str,
    messages: list[dict[str, Any]],
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    raw = await _chat_completion(provider, build_text_payload(model, messages), client=client)
    return extract_answer_from_payload(parse_model_payload(raw))


async def complete_vision(
    provider: dict[str, Any],
    model: str,
    messages: list[dict[str, Any]],
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    raw = await _chat_completion(provider, build_vision_payload(model, messages), client=client)
    return extract_answer_from_payload(parse_model_payload(raw))


def _ext_from_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime_type, ".jpg")


async def complete_image_generation(
    provider: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    output_dir: Path,
    chat_id: int,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    raw = await _chat_completion(
        provider,
        build_image_generation_payload(messages),
        client=client,
        accept="text/event-stream",
    )
    parsed = parse_openrouter_event_stream(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    for idx, image in enumerate(parsed["images"], start=1):
        url = (((image.get("image_url") or {}).get("url")) or "")
        if not url.startswith("data:"):
            continue
        meta, b64 = url.split(",", 1)
        mime_type = meta.split(";")[0].split(":", 1)[1]
        file_path = output_dir / f"gen-{chat_id}-{idx}{_ext_from_mime(mime_type)}"
        file_path.write_bytes(base64.b64decode(b64))
        image_paths.append(file_path)
    return {
        "answer": parsed["text"] or "Готово.",
        "image_paths": image_paths,
    }
