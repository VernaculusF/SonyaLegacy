from __future__ import annotations

import base64
import asyncio
from pathlib import Path
from typing import Any

import httpx

from tg_bridge.media import parse_openrouter_event_stream


def _strip_omniroute_prefix(model_name: str) -> str:
    parts = str(model_name or "").split("/")
    return "/".join(parts[1:]) if parts and parts[0] == "omniroute" else str(model_name or "")


def resolve_model_name(cfg: dict[str, Any]) -> str:
    configured = (((cfg.get("agents") or {}).get("defaults") or {}).get("model")) or ""
    return _strip_omniroute_prefix(str(configured))


def resolve_image_model_name(cfg: dict[str, Any]) -> str:
    defaults = ((cfg.get("agents") or {}).get("defaults") or {})
    configured = defaults.get("imageModel") or defaults.get("model") or ""
    return _strip_omniroute_prefix(str(configured))


def build_text_payload(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": 3200,
        "temperature": 0.7,
    }


def build_vision_payload(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "max_tokens": 3200,
        "temperature": 0.4,
    }


def build_image_generation_payload(model: str, messages: list[dict[str, Any]], *, stream: bool = False) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "modalities": ["image", "text"],
        "stream": stream,
    }


def serialize_user_content(prompt_text: str, media_items: list[dict[str, Any]] | None = None) -> str | list[dict[str, Any]]:
    media_items = media_items or []
    if not media_items:
        return prompt_text
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    for item in media_items:
        mime_type = str(item.get("mime_type") or "")
        if mime_type.startswith("video/") or item.get("kind") in {"video", "document_video", "video_note"}:
            content.append(
                {
                    "type": "video_url",
                    "videoUrl": {"url": item["data_url"]},
                }
            )
            continue
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": item["data_url"]},
            }
        )
    return content


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
    if isinstance(content, str):
        return content if content.strip() else ""
    if isinstance(content, list):
        joined = "".join(part if isinstance(part, str) else str(part.get("text", "")) for part in content)
        return joined if joined.strip() else ""
    text = choice.get("text")
    if text is None:
        return ""
    raw_text = str(text)
    return raw_text if raw_text.strip() else ""


def extract_finish_reason_from_payload(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    choice = (payload.get("choices") or [{}])[0]
    return str(choice.get("finish_reason") or "").strip()


def extract_images_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    images = message.get("images")
    return images if isinstance(images, list) else []


def _looks_incomplete_text(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return True
    if len(stripped) < 250:
        return False
    if stripped.endswith(("...", "…")):
        return True
    if stripped[-1].isalnum():
        return True
    terminal_chars = {".", "!", "?", ")", "]", "\"", "'", "»", "🖤", "💜", "❤"}
    return stripped[-1] not in terminal_chars


def _normalize_for_overlap(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _trim_overlap(existing: str, new_part: str) -> str:
    existing_raw = str(existing or "")
    new_raw = str(new_part or "")
    existing_norm = _normalize_for_overlap(existing)
    new_norm = _normalize_for_overlap(new_part)
    if not new_raw:
        return ""
    if not existing_raw:
        return new_raw
    if new_norm in existing_norm:
        return ""

    max_raw_overlap = min(len(existing_raw), len(new_raw), 1200)
    for size in range(max_raw_overlap, 1, -1):
        if existing_raw.endswith(new_raw[:size]):
            return new_raw[size:].lstrip(" ")

    max_overlap = min(len(existing_norm), len(new_norm), 1200)
    for size in range(max_overlap, 11, -1):
        if existing_norm.endswith(new_norm[:size]):
            return new_norm[size:].lstrip()
    return new_raw


def _collapse_repeated_paragraphs(text: str) -> str:
    parts = [part.strip() for part in str(text or "").split("\n\n")]
    result: list[str] = []
    seen_tail: set[str] = set()
    for part in parts:
        if not part:
            continue
        normalized = _normalize_for_overlap(part)
        if not normalized:
            continue
        if result and normalized == _normalize_for_overlap(result[-1]):
            continue
        if normalized in seen_tail:
            continue
        result.append(part)
        seen_tail.add(normalized)
        if len(seen_tail) > 12:
            seen_tail = set(_normalize_for_overlap(item) for item in result[-12:])
    return "\n\n".join(result).strip()


def _join_text_parts(parts: list[str]) -> str:
    result = ""
    for part in parts:
        if not part:
            continue
        if not result:
            result = part
            continue
        prev = result[-1]
        nxt = part[0]
        needs_space = (
            not prev.isspace()
            and not nxt.isspace()
            and prev not in "([{\n\t"
            and nxt not in ".,!?;:)]}\n\t"
        )
        result += (" " if needs_space else "") + part
    return result.strip()


async def _chat_completion(
    provider: dict[str, Any],
    body: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    accept: str | None = None,
    timeout: httpx.Timeout | float | None = None,
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
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                response = await client.post(
                    f"{provider['baseUrl'].rstrip('/')}/chat/completions",
                    json=body,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.text
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as err:
                last_err = err
            except httpx.HTTPStatusError as err:
                last_err = err
                if err.response is None or err.response.status_code < 500:
                    raise
            if attempt < 2:
                await asyncio.sleep(1.0 * (attempt + 1))
        assert last_err is not None
        raise last_err
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
    request_messages = list(messages)
    answer_parts: list[str] = []
    empty_retries = 0
    for _ in range(5):
        raw = await _chat_completion(provider, build_text_payload(model, request_messages), client=client)
        payload = parse_model_payload(raw)
        part = extract_answer_from_payload(payload)
        finish_reason = extract_finish_reason_from_payload(payload)
        current_answer = _join_text_parts(answer_parts)
        if part:
            trimmed_part = _trim_overlap(current_answer, part)
            if trimmed_part:
                answer_parts.append(trimmed_part)
            empty_retries = 0
        elif not answer_parts and finish_reason != "length" and empty_retries < 2:
            empty_retries += 1
            continue
        current_answer = _join_text_parts(answer_parts)
        should_continue = finish_reason == "length" or (bool(current_answer) and _looks_incomplete_text(current_answer))
        if not should_continue:
            break
        request_messages = [
            *request_messages,
            {"role": "assistant", "content": current_answer or part},
            {
                "role": "user",
                "content": "Continue exactly from where you stopped. Do not repeat. Finish the same reply naturally.",
            },
        ]
    final_answer = _join_text_parts(answer_parts)
    return _collapse_repeated_paragraphs(final_answer)


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
    model: str,
    messages: list[dict[str, Any]],
    *,
    output_dir: Path,
    chat_id: int,
    client: httpx.AsyncClient | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    raw = await _chat_completion(
        provider,
        build_image_generation_payload(model, messages, stream=stream),
        client=client,
        accept="text/event-stream" if stream else "application/json",
        timeout=httpx.Timeout(180.0, connect=20.0, read=180.0, write=60.0),
    )
    if stream:
        parsed = parse_openrouter_event_stream(raw)
        answer = parsed["text"]
        images = parsed["images"]
    else:
        payload = parse_model_payload(raw)
        answer = extract_answer_from_payload(payload)
        images = extract_images_from_payload(payload)

    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    for idx, image in enumerate(images, start=1):
        url = (((image.get("image_url") or {}).get("url")) or "")
        if not url.startswith("data:"):
            continue
        meta, b64 = url.split(",", 1)
        mime_type = meta.split(";")[0].split(":", 1)[1]
        file_path = output_dir / f"gen-{chat_id}-{idx}{_ext_from_mime(mime_type)}"
        file_path.write_bytes(base64.b64decode(b64))
        image_paths.append(file_path)
    return {
        "answer": answer or "Готово.",
        "image_paths": image_paths,
    }

