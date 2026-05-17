from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from sonya.providers.base import (
    Capability,
    CompletionRequest,
    CompletionResult,
)
from sonya.providers.secrets import ProviderSecret


_TERMINAL_CHARS = {".", "!", "?", ")", "]", "\"", "'", "»", "🖤", "💜", "❤"}


@dataclass(slots=True)
class OpenRouterProvider:
    """OpenAI-completions-compatible client for OpenRouter and similar gateways.

    Provides retry on 429/5xx, continuation when response gets cut off,
    overlap trim between chunks, and event-stream parsing for image generation.

    Notes:
      * api_key is passed as ProviderSecret, not plaintext dict;
      * complete_image_generation returns CompletionResult with raw images list
        in `raw["images"]`; saving to disk is the caller's responsibility;
      * no chat_id / output_dir coupling.
    """

    api_key: ProviderSecret
    model_id: str
    image_model_id: str | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    context_window: int = 262144
    max_tokens: int = 32800
    input_modes: tuple[str, ...] = ("text", "image")
    cost_input: float = 0.0
    cost_output: float = 0.0
    supports_reasoning_effort: bool = False
    max_tokens_field: str = "max_tokens"
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    def capabilities(self) -> Capability:
        return Capability(
            provider_name="openrouter",
            model_id=self.model_id,
            input_modes=self.input_modes,
            context_window=self.context_window,
            max_tokens=self.max_tokens,
            cost_input=self.cost_input,
            cost_output=self.cost_output,
            supports_reasoning_effort=self.supports_reasoning_effort,
            max_tokens_field=self.max_tokens_field,
        )

    async def complete_text(self, request: CompletionRequest) -> CompletionResult:
        request_messages: list[dict[str, Any]] = [dict(m) for m in request.messages]
        answer_parts: list[str] = []
        finish_reason = ""
        empty_retries = 0
        for _ in range(5):
            raw = await self._chat(
                {
                    "model": self.model_id,
                    "messages": request_messages,
                    "max_tokens": request.max_tokens,
                    "temperature": request.temperature,
                }
            )
            payload = _parse_payload(raw)
            part = _extract_answer(payload)
            finish_reason = _extract_finish_reason(payload)
            current_answer = _join_text_parts(answer_parts)
            if part:
                trimmed = _trim_overlap(current_answer, part)
                if trimmed:
                    answer_parts.append(trimmed)
                empty_retries = 0
            elif not answer_parts and finish_reason != "length" and empty_retries < 2:
                empty_retries += 1
                continue
            current_answer = _join_text_parts(answer_parts)
            should_continue = finish_reason == "length" or (
                bool(current_answer) and _looks_incomplete_text(current_answer)
            )
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
        final = _collapse_repeated_paragraphs(_join_text_parts(answer_parts))
        return CompletionResult(content=final, finish_reason=finish_reason)

    async def complete_vision(self, request: CompletionRequest) -> CompletionResult:
        raw = await self._chat(
            {
                "model": self.model_id,
                "messages": [dict(m) for m in request.messages],
                "max_tokens": request.max_tokens,
                "temperature": min(request.temperature, 0.4),
            }
        )
        payload = _parse_payload(raw)
        return CompletionResult(
            content=_extract_answer(payload),
            finish_reason=_extract_finish_reason(payload),
        )

    async def complete_image_generation(
        self, request: CompletionRequest
    ) -> CompletionResult:
        model = self.image_model_id or self.model_id
        stream = bool(request.extra.get("stream", False))
        raw = await self._chat(
            {
                "model": model,
                "messages": [dict(m) for m in request.messages],
                "modalities": ["image", "text"],
                "stream": stream,
            },
            accept="text/event-stream" if stream else "application/json",
            timeout=httpx.Timeout(180.0, connect=20.0, read=180.0, write=60.0),
        )
        if stream:
            parsed = _parse_event_stream(raw)
            answer = parsed["text"]
            images = parsed["images"]
        else:
            payload = _parse_payload(raw)
            answer = _extract_answer(payload)
            images = _extract_images(payload)
        return CompletionResult(
            content=answer,
            finish_reason="stop",
            raw={"images": images},
        )

    # ---- internals ----

    async def _chat(
        self,
        body: Mapping[str, Any],
        *,
        accept: str | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> str:
        own_client = self._client is None
        client = self._client or httpx.AsyncClient()
        try:
            headers = {
                "authorization": f"Bearer {self.api_key.get_secret_value()}",
                "content-type": "application/json",
            }
            if accept:
                headers["accept"] = accept
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    response = await client.post(
                        f"{self.base_url.rstrip('/')}/chat/completions",
                        json=body,
                        headers=headers,
                        timeout=timeout,
                    )
                    response.raise_for_status()
                    return response.text
                except (
                    httpx.ConnectTimeout,
                    httpx.ReadTimeout,
                    httpx.ConnectError,
                    httpx.RemoteProtocolError,
                ) as err:
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


# ---- payload parsing helpers (ported, behavior-preserving) ----


def _parse_payload(text: str) -> dict[str, Any] | None:
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


def _extract_answer(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    choice = (payload.get("choices") or [{}])[0]
    content = ((choice.get("message") or {}).get("content"))
    if isinstance(content, str):
        return content if content.strip() else ""
    if isinstance(content, list):
        joined = "".join(
            part if isinstance(part, str) else str(part.get("text", ""))
            for part in content
        )
        return joined if joined.strip() else ""
    text = choice.get("text")
    if text is None:
        return ""
    raw = str(text)
    return raw if raw.strip() else ""


def _extract_finish_reason(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    choice = (payload.get("choices") or [{}])[0]
    return str(choice.get("finish_reason") or "").strip()


def _extract_images(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    choice = (payload.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    images = message.get("images")
    return images if isinstance(images, list) else []


def _parse_event_stream(raw_text: str) -> dict[str, Any]:
    chunks: list[dict[str, Any]] = []
    normalized = str(raw_text or "").lstrip("\ufeff")
    for line in normalized.splitlines():
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
        "text": "".join(content_parts).strip(),
        "images": images,
        "finishReason": finish_reason,
    }


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
    return stripped[-1] not in _TERMINAL_CHARS


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
    max_raw = min(len(existing_raw), len(new_raw), 1200)
    for size in range(max_raw, 1, -1):
        if existing_raw.endswith(new_raw[:size]):
            return new_raw[size:].lstrip(" ")
    max_norm = min(len(existing_norm), len(new_norm), 1200)
    for size in range(max_norm, 11, -1):
        if existing_norm.endswith(new_norm[:size]):
            return new_norm[size:].lstrip()
    return new_raw


def _collapse_repeated_paragraphs(text: str) -> str:
    parts = [p.strip() for p in str(text or "").split("\n\n")]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if not p:
            continue
        norm = _normalize_for_overlap(p)
        if not norm:
            continue
        if out and norm == _normalize_for_overlap(out[-1]):
            continue
        if norm in seen:
            continue
        out.append(p)
        seen.add(norm)
        if len(seen) > 12:
            seen = {_normalize_for_overlap(item) for item in out[-12:]}
    return "\n\n".join(out).strip()


def _join_text_parts(parts: Sequence[str]) -> str:
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
