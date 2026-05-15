from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Capability:
    """Per-model provider capability descriptor.

    Shape comes from OpenClaw `openclaw.json.models.providers.<name>.models[*]`.
    Stored verbatim so future planner can match models by capability without
    reaching into provider-specific config.
    """

    provider_name: str
    model_id: str
    input_modes: tuple[str, ...]
    context_window: int
    max_tokens: int
    cost_input: float = 0.0
    cost_output: float = 0.0
    supports_reasoning_effort: bool = False
    max_tokens_field: str = "max_tokens"


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """Provider-agnostic completion request."""

    messages: Sequence[Mapping[str, Any]]
    max_tokens: int = 3200
    temperature: float = 0.7
    modalities: tuple[str, ...] = ("text",)
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """Provider-agnostic completion result."""

    content: str
    finish_reason: str = ""
    usage: Mapping[str, int] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class ProviderBackend(Protocol):
    """Stable interface that any LLM/image backend must satisfy."""

    def capabilities(self) -> Capability:
        ...

    async def complete_text(self, request: CompletionRequest) -> CompletionResult:
        ...

    async def complete_vision(self, request: CompletionRequest) -> CompletionResult:
        ...

    async def complete_image_generation(self, request: CompletionRequest) -> CompletionResult:
        ...
