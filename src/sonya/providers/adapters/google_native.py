from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from sonya.providers.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AdapterInferenceRequest,
    AdapterInferenceResult,
    DiscoveredModel,
    QuotaSnapshot,
)
from sonya.providers.secrets import ProviderSecret


@dataclass(slots=True)
class GoogleNativeAdapter:
    provider_id: str
    api_key: ProviderSecret
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    client: httpx.AsyncClient | None = field(default=None, repr=False)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            provider_id=self.provider_id,
            adapter_kind="google_native",
            supports_model_discovery=True,
            supports_health_check=True,
            supports_quota=False,
            supports_inference=True,
            supported_modes=("models", "generate_content"),
        )

    async def discover_models(self) -> list[DiscoveredModel]:
        payload = await self._get_json("/models")
        entries = payload.get("models", []) if isinstance(payload, dict) else []
        return [_model_from_google_entry(self.provider_id, item) for item in entries if isinstance(item, dict)]

    async def health_check(self) -> AdapterHealth:
        start = time.perf_counter()
        try:
            await self.discover_models()
        except Exception as exc:
            return AdapterHealth(
                ok=False,
                status="error",
                latency_ms=int((time.perf_counter() - start) * 1000),
                message=f"{type(exc).__name__}: {exc}",
            )
        return AdapterHealth(
            ok=True,
            status="ok",
            latency_ms=int((time.perf_counter() - start) * 1000),
            message="models endpoint reachable",
        )

    async def fetch_quota(self) -> list[QuotaSnapshot]:
        return []

    async def infer(self, request: AdapterInferenceRequest) -> AdapterInferenceResult:
        payload = await self._post_json(
            f"/models/{request.model_id}:generateContent",
            {
                "contents": [_google_content(message) for message in request.messages],
                "generationConfig": {
                    "maxOutputTokens": request.max_tokens,
                    "temperature": request.temperature,
                },
                **dict(request.extra),
            },
        )
        candidate = (payload.get("candidates") or [{}])[0] if isinstance(payload, dict) else {}
        parts = ((candidate.get("content") or {}).get("parts") or []) if isinstance(candidate, dict) else []
        content = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        usage_meta = payload.get("usageMetadata", {}) if isinstance(payload, dict) else {}
        usage = {
            "prompt_tokens": int(usage_meta.get("promptTokenCount", 0) or 0),
            "completion_tokens": int(usage_meta.get("candidatesTokenCount", 0) or 0),
            "total_tokens": int(usage_meta.get("totalTokenCount", 0) or 0),
        }
        return AdapterInferenceResult(
            content=content,
            finish_reason=str(candidate.get("finishReason", "")),
            usage=usage,
            raw=payload if isinstance(payload, dict) else {},
        )

    async def _get_json(self, path: str) -> dict[str, Any]:
        response = await self._request("GET", path)
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", path, json=body)
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        own_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            response = await client.request(
                method,
                f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
                params={"key": self.api_key.get_secret_value()},
                headers={"content-type": "application/json"},
                timeout=kwargs.pop("timeout", 30.0),
                **kwargs,
            )
            response.raise_for_status()
            return response
        finally:
            if own_client:
                await client.aclose()


def _model_from_google_entry(provider_id: str, item: dict[str, Any]) -> DiscoveredModel:
    raw_name = str(item.get("name") or "")
    model_id = raw_name.removeprefix("models/")
    methods = item.get("supportedGenerationMethods") or []
    modalities = ("text",) if "generateContent" in methods else ()
    return DiscoveredModel(
        provider_id=provider_id,
        model_id=model_id,
        display_name=str(item.get("displayName") or model_id),
        context_length=int(item.get("inputTokenLimit") or 0),
        modalities=modalities,
        metadata={"raw": item},
    )


def _google_content(message: Any) -> dict[str, Any]:
    item = dict(message)
    role = "model" if item.get("role") == "assistant" else str(item.get("role") or "user")
    content = item.get("content", "")
    if isinstance(content, list):
        parts = content
    else:
        parts = [{"text": str(content)}]
    return {"role": role, "parts": parts}
