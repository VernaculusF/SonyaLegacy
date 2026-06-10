from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    provider_id: str
    adapter_kind: str
    supports_model_discovery: bool
    supports_health_check: bool
    supports_quota: bool
    supports_inference: bool
    supported_modes: tuple[str, ...] = ("chat_completions",)


@dataclass(frozen=True, slots=True)
class DiscoveredModel:
    provider_id: str
    model_id: str
    display_name: str
    context_length: int
    modalities: tuple[str, ...] = ("text",)
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    ok: bool
    status: str
    latency_ms: int = 0
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    quota_kind: str
    limit_value: float | None
    used_value: float | None
    remaining_value: float | None
    unit: str
    resets_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdapterInferenceRequest:
    model_id: str
    messages: Sequence[Mapping[str, Any]]
    max_tokens: int = 3200
    temperature: float = 0.7
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AdapterInferenceResult:
    content: str
    finish_reason: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class ProviderAdapter(Protocol):
    def capabilities(self) -> AdapterCapabilities:
        ...

    async def discover_models(self) -> list[DiscoveredModel]:
        ...

    async def health_check(self) -> AdapterHealth:
        ...

    async def fetch_quota(self) -> list[QuotaSnapshot]:
        ...

    async def infer(self, request: AdapterInferenceRequest) -> AdapterInferenceResult:
        ...
