from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from sonya.providers import (
    Capability,
    CompletionRequest,
    CompletionResult,
    ProviderSecret,
)
from sonya.providers.openrouter import OpenRouterProvider


def _mk_provider(transport: httpx.MockTransport, **overrides: Any) -> OpenRouterProvider:
    client = httpx.AsyncClient(transport=transport)
    return OpenRouterProvider(
        api_key=ProviderSecret("test-key"),
        model_id=overrides.get("model_id", "google/gemma"),
        image_model_id=overrides.get("image_model_id", "google/gemini-image"),
        base_url="https://example.test/api/v1",
        _client=client,
    )


def _ok_text(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"content": content}, "finish_reason": finish_reason}
            ],
            "usage": {},
        },
    )


def test_capability_reports_provider_name_and_modes() -> None:
    provider = _mk_provider(httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    cap = provider.capabilities()
    assert cap.provider_name == "openrouter"
    assert "text" in cap.input_modes


@pytest.mark.asyncio
async def test_complete_text_basic() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return _ok_text("hello world")

    provider = _mk_provider(httpx.MockTransport(handler))
    res = await provider.complete_text(
        CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    )
    assert res.content == "hello world"
    assert res.finish_reason == "stop"
    assert seen[0]["model"] == "google/gemma"
    assert seen[0]["max_tokens"] > 0


@pytest.mark.asyncio
async def test_complete_text_continues_on_length_finish() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _ok_text("part one — this is a long fragment", finish_reason="length")
        return _ok_text(" part two completes the answer.", finish_reason="stop")

    provider = _mk_provider(httpx.MockTransport(handler))
    res = await provider.complete_text(
        CompletionRequest(messages=[{"role": "user", "content": "long?"}])
    )
    assert "part one" in res.content
    assert "part two" in res.content
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_retry_on_5xx_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": "boom"})
        return _ok_text("recovered", finish_reason="stop")

    provider = _mk_provider(httpx.MockTransport(handler))
    res = await provider.complete_text(
        CompletionRequest(messages=[{"role": "user", "content": "ping"}])
    )
    assert res.content == "recovered"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_4xx_error_does_not_retry() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad"})

    provider = _mk_provider(httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete_text(
            CompletionRequest(messages=[{"role": "user", "content": "x"}])
        )
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_complete_vision_uses_lower_temperature() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return _ok_text("describes")

    provider = _mk_provider(httpx.MockTransport(handler))
    res = await provider.complete_vision(
        CompletionRequest(
            messages=[{"role": "user", "content": "describe"}],
            temperature=1.5,
        )
    )
    assert res.content == "describes"
    assert seen[0]["temperature"] <= 0.4


@pytest.mark.asyncio
async def test_complete_image_generation_returns_images_in_raw() -> None:
    image_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                            "images": [{"image_url": {"url": image_url}}],
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    provider = _mk_provider(httpx.MockTransport(handler))
    res = await provider.complete_image_generation(
        CompletionRequest(messages=[{"role": "user", "content": "draw"}])
    )
    assert "images" in res.raw
    assert res.raw["images"][0]["image_url"]["url"] == image_url


@pytest.mark.asyncio
async def test_secret_not_exposed_in_provider_repr() -> None:
    provider = OpenRouterProvider(
        api_key=ProviderSecret("super-secret-abcdef"),
        model_id="m",
    )
    assert "super-secret" not in repr(provider)
    assert "abcdef" not in repr(provider)
