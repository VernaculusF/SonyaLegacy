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
class OpenAICompatibleAdapter:
    provider_id: str
    base_url: str
    api_key: ProviderSecret
    client: httpx.AsyncClient | None = field(default=None, repr=False)
    quota_path: str = ""

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            provider_id=self.provider_id,
            adapter_kind="openai_compatible",
            supports_model_discovery=True,
            supports_health_check=True,
            supports_quota=bool(self.quota_path),
            supports_inference=True,
            supported_modes=("models", "chat_completions"),
        )

    async def discover_models(self) -> list[DiscoveredModel]:
        payload = await self._get_json("/models")
        entries = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            return []
        return [_model_from_openai_entry(self.provider_id, item) for item in entries if isinstance(item, dict)]

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
        if not self.quota_path:
            return []
        payload = await self._get_json(self.quota_path)
        limit_value = _float_or_none(payload.get("limit") if isinstance(payload, dict) else None)
        used_value = _float_or_none(payload.get("used") if isinstance(payload, dict) else None)
        remaining_value = _float_or_none(payload.get("remaining") if isinstance(payload, dict) else None)
        return [
            QuotaSnapshot(
                quota_kind="credits",
                limit_value=limit_value,
                used_value=used_value,
                remaining_value=remaining_value,
                unit="usd",
                resets_at=str(payload.get("resets_at", "")) if isinstance(payload, dict) else "",
                metadata={"raw": payload},
            )
        ]

    async def infer(self, request: AdapterInferenceRequest) -> AdapterInferenceResult:
        payload = await self._post_json(
            "/chat/completions",
            {
                "model": request.model_id,
                "messages": [dict(message) for message in request.messages],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                **dict(request.extra),
            },
        )
        choice = (payload.get("choices") or [{}])[0] if isinstance(payload, dict) else {}
        message = choice.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else ""
        return AdapterInferenceResult(
            content=content if isinstance(content, str) else "",
            finish_reason=str(choice.get("finish_reason", "")),
            usage=payload.get("usage", {}) if isinstance(payload, dict) else {},
            raw=payload if isinstance(payload, dict) else {},
        )

    async def _get_json(self, path: str) -> dict[str, Any] | list[Any]:
        response = await self._request("GET", path)
        return response.json()

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
                headers={
                    "authorization": f"Bearer {self.api_key.get_secret_value()}",
                    "content-type": "application/json",
                },
                timeout=kwargs.pop("timeout", 30.0),
                **kwargs,
            )
            response.raise_for_status()
            return response
        finally:
            if own_client:
                await client.aclose()


def _model_from_openai_entry(provider_id: str, item: dict[str, Any]) -> DiscoveredModel:
    model_id = str(item.get("id") or item.get("name") or "")
    display_name = str(item.get("name") or item.get("display_name") or model_id)
    modalities = _modalities_from_openai_entry(item)
    input_cost, output_cost, free = _pricing_from_openai_entry(model_id, item)
    metadata: dict[str, Any] = {"raw": item}
    if free is not None:
        metadata["free"] = free
    return DiscoveredModel(
        provider_id=provider_id,
        model_id=model_id,
        display_name=display_name,
        context_length=int(item.get("context_length") or item.get("context_window") or 0),
        modalities=modalities,
        input_cost_per_1m=input_cost,
        output_cost_per_1m=output_cost,
        metadata=metadata,
    )


def _modalities_from_openai_entry(item: dict[str, Any]) -> tuple[str, ...]:
    modality = item.get("architecture", {}).get("modality") if isinstance(item.get("architecture"), dict) else ""
    text = str(modality or "").lower()
    out = ["text"]
    if "image" in text or "vision" in text:
        out.append("image")
    return tuple(dict.fromkeys(out))


def _pricing_from_openai_entry(
    model_id: str,
    item: dict[str, Any],
) -> tuple[float, float, bool | None]:
    input_cost = _float_or_none(item.get("input_price"))
    output_cost = _float_or_none(item.get("output_price"))
    pricing = item.get("pricing")
    nested_seen = isinstance(pricing, dict)
    if nested_seen:
        if input_cost is None:
            per_token = _float_or_none(pricing.get("prompt"))
            input_cost = per_token * 1_000_000 if per_token is not None else None
        if output_cost is None:
            per_token = _float_or_none(pricing.get("completion"))
            output_cost = per_token * 1_000_000 if per_token is not None else None
    free: bool | None = None
    if input_cost is not None or output_cost is not None:
        free = (input_cost or 0.0) == 0.0 and (output_cost or 0.0) == 0.0
    elif model_id.endswith(":free"):
        free = True
    if free is True and not model_id.endswith(":free") and not _is_text_output_model(item):
        free = False
    return input_cost or 0.0, output_cost or 0.0, free


def _is_text_output_model(item: dict[str, Any]) -> bool:
    architecture = item.get("architecture")
    if not isinstance(architecture, dict):
        return True
    output_modalities = architecture.get("output_modalities")
    if isinstance(output_modalities, list):
        return set(str(item).lower() for item in output_modalities) <= {"text"}
    modality = str(architecture.get("modality") or "").lower()
    if "->" not in modality:
        return True
    output = modality.split("->", 1)[1]
    return all(part.strip() == "text" for part in output.split("+") if part.strip())


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
