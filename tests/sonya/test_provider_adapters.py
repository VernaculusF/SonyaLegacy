from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from sonya.providers.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AdapterInferenceRequest,
    DiscoveredModel,
    QuotaSnapshot,
)
from sonya.providers.adapters.google_native import GoogleNativeAdapter
from sonya.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from sonya.providers.secrets import ProviderSecret


def test_adapter_value_objects_are_stable() -> None:
    capabilities = AdapterCapabilities(
        provider_id="openrouter",
        adapter_kind="openai_compatible",
        supports_model_discovery=True,
        supports_health_check=True,
        supports_quota=True,
        supports_inference=True,
        supported_modes=("chat_completions",),
    )
    model = DiscoveredModel(
        provider_id="openrouter",
        model_id="google/gemma",
        display_name="Gemma",
        context_length=262144,
        modalities=("text",),
        metadata={"free": True},
    )
    health = AdapterHealth(ok=True, status="ok", latency_ms=12, message="ready")
    quota = QuotaSnapshot(
        quota_kind="rpd",
        limit_value=1000,
        used_value=25,
        remaining_value=975,
        unit="requests",
        resets_at="2026-06-11T00:00:00+00:00",
    )

    assert capabilities.provider_id == "openrouter"
    assert model.metadata["free"] is True
    assert health.ok is True
    assert quota.remaining_value == 975


@pytest.mark.asyncio
async def test_openai_compatible_adapter_discovers_models_and_chat() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "google/gemma",
                            "name": "Gemma",
                            "context_length": 262144,
                            "architecture": {"modality": "text->text"},
                        }
                    ]
                },
            )
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "hello"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
                },
            )
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(
        provider_id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=ProviderSecret("sk-test-secret"),
        client=client,
    )

    models = await adapter.discover_models()
    result = await adapter.infer(
        AdapterInferenceRequest(
            model_id="google/gemma",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=128,
        )
    )

    assert models == [
        DiscoveredModel(
            provider_id="openrouter",
            model_id="google/gemma",
            display_name="Gemma",
            context_length=262144,
            modalities=("text",),
            metadata={"raw": {
                "id": "google/gemma",
                "name": "Gemma",
                "context_length": 262144,
                "architecture": {"modality": "text->text"},
            }},
        )
    ]
    assert result.content == "hello"
    assert result.finish_reason == "stop"
    assert result.usage["total_tokens"] == 4
    assert all("sk-test-secret" not in repr(item.headers) for item in seen)
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_compatible_adapter_normalizes_nested_pricing_and_free_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "google/gemma:free",
                        "pricing": {"prompt": "0", "completion": "0"},
                    },
                    {
                        "id": "ai21/jamba",
                        "pricing": {"prompt": "0.000002", "completion": "0.000008"},
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(
        provider_id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=ProviderSecret("sk-test-secret"),
        client=client,
    )

    free_model, paid_model = await adapter.discover_models()

    assert free_model.metadata["free"] is True
    assert free_model.input_cost_per_1m == 0
    assert free_model.output_cost_per_1m == 0
    assert paid_model.metadata["free"] is False
    assert paid_model.input_cost_per_1m == 2
    assert paid_model.output_cost_per_1m == 8
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_compatible_adapter_does_not_mark_audio_models_free() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "google/lyria-3-clip-preview",
                        "pricing": {"prompt": "0", "completion": "0"},
                        "architecture": {
                            "modality": "text+image->text+audio",
                            "output_modalities": ["text", "audio"],
                        },
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(
        provider_id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=ProviderSecret("sk-test-secret"),
        client=client,
    )

    model = (await adapter.discover_models())[0]

    assert model.metadata["free"] is False
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_compatible_health_and_quota_are_structured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        if request.url.path.endswith("/credits"):
            return httpx.Response(200, json={"limit": 10.0, "used": 2.5, "remaining": 7.5})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAICompatibleAdapter(
        provider_id="freelike",
        base_url="https://example.test/v1",
        api_key=ProviderSecret("sk-test"),
        client=client,
        quota_path="/credits",
    )

    health = await adapter.health_check()
    quotas = await adapter.fetch_quota()

    assert health.ok is True
    assert health.status == "ok"
    assert quotas == [
        QuotaSnapshot(
            quota_kind="credits",
            limit_value=10.0,
            used_value=2.5,
            remaining_value=7.5,
            unit="usd",
            resets_at="",
            metadata={"raw": {"limit": 10.0, "used": 2.5, "remaining": 7.5}},
        )
    ]
    await client.aclose()


@pytest.mark.asyncio
async def test_google_native_adapter_discovers_models_and_infers() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-2.5-flash",
                            "displayName": "Gemini 2.5 Flash",
                            "inputTokenLimit": 1000000,
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                },
            )
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "google hello"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 2,
                    "candidatesTokenCount": 3,
                    "totalTokenCount": 5,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = GoogleNativeAdapter(
        provider_id="google",
        api_key=ProviderSecret("google-key"),
        base_url="https://generativelanguage.googleapis.com/v1beta",
        client=client,
    )

    models = await adapter.discover_models()
    result = await adapter.infer(
        AdapterInferenceRequest(
            model_id="gemini-2.5-flash",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=64,
        )
    )

    assert models[0].model_id == "gemini-2.5-flash"
    assert models[0].display_name == "Gemini 2.5 Flash"
    assert models[0].context_length == 1000000
    assert result.content == "google hello"
    assert result.usage["total_tokens"] == 5
    assert requests[0]["contents"][0]["role"] == "user"
    await client.aclose()
