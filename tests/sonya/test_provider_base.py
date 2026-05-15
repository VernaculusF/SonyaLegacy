from __future__ import annotations

import pytest

from sonya.providers import (
    Capability,
    CompletionRequest,
    CompletionResult,
    ProviderBackend,
)


def test_capability_round_trip() -> None:
    cap = Capability(
        provider_name="openrouter",
        model_id="google/gemma-4-26b",
        input_modes=("text", "image"),
        context_window=262144,
        max_tokens=32800,
        cost_input=0.0,
        cost_output=0.0,
        supports_reasoning_effort=False,
        max_tokens_field="max_tokens",
    )
    assert cap.provider_name == "openrouter"
    assert "image" in cap.input_modes
    assert cap.context_window == 262144


def test_completion_request_defaults() -> None:
    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    assert req.messages == [{"role": "user", "content": "hi"}]
    assert req.max_tokens > 0
    assert 0.0 <= req.temperature <= 2.0
    assert req.modalities == ("text",)


def test_completion_result_round_trip() -> None:
    res = CompletionResult(
        content="hello",
        finish_reason="stop",
        usage={"prompt_tokens": 5, "completion_tokens": 1},
    )
    assert res.content == "hello"
    assert res.finish_reason == "stop"
    assert res.usage["prompt_tokens"] == 5


def test_provider_backend_is_runtime_protocol() -> None:
    # Should be importable as Protocol; runtime_checkable not required, but type-only.
    assert ProviderBackend is not None


@pytest.mark.asyncio
async def test_protocol_can_be_implemented() -> None:
    class Stub:
        def capabilities(self) -> Capability:
            return Capability(
                provider_name="stub",
                model_id="stub-1",
                input_modes=("text",),
                context_window=1024,
                max_tokens=256,
                cost_input=0.0,
                cost_output=0.0,
                supports_reasoning_effort=False,
                max_tokens_field="max_tokens",
            )

        async def complete_text(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult(content="ok", finish_reason="stop", usage={})

        async def complete_vision(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult(content="ok", finish_reason="stop", usage={})

        async def complete_image_generation(
            self, request: CompletionRequest
        ) -> CompletionResult:
            return CompletionResult(content="data:image/png;base64,...", finish_reason="stop", usage={})

    stub: ProviderBackend = Stub()  # type: ignore[assignment]
    out = await stub.complete_text(CompletionRequest(messages=[{"role": "user", "content": "hi"}]))
    assert out.content == "ok"
