from __future__ import annotations

import pytest

from sonya.providers import (
    Capability,
    CompletionRequest,
    CompletionResult,
    ProviderRegistry,
)


def _make_stub(name: str, model_id: str, modes: tuple[str, ...]) -> object:
    class Stub:
        def capabilities(self) -> Capability:
            return Capability(
                provider_name=name,
                model_id=model_id,
                input_modes=modes,
                context_window=1024,
                max_tokens=256,
            )

        async def complete_text(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult(content="t")

        async def complete_vision(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult(content="v")

        async def complete_image_generation(
            self, request: CompletionRequest
        ) -> CompletionResult:
            return CompletionResult(content="img")

    return Stub()


def test_register_and_get() -> None:
    reg = ProviderRegistry()
    p = _make_stub("openrouter", "g/m", ("text", "image"))
    reg.register("openrouter", p)
    assert reg.get("openrouter") is p


def test_get_missing_raises() -> None:
    reg = ProviderRegistry()
    with pytest.raises(KeyError):
        reg.get("does-not-exist")


def test_register_duplicate_raises() -> None:
    reg = ProviderRegistry()
    reg.register("a", _make_stub("a", "m", ("text",)))
    with pytest.raises(ValueError):
        reg.register("a", _make_stub("a", "m", ("text",)))


def test_list_returns_registered() -> None:
    reg = ProviderRegistry()
    reg.register("a", _make_stub("a", "m1", ("text",)))
    reg.register("b", _make_stub("b", "m2", ("text", "image")))
    assert sorted(reg.list()) == ["a", "b"]


def test_find_by_capability_intersection() -> None:
    reg = ProviderRegistry()
    reg.register("text-only", _make_stub("text-only", "m1", ("text",)))
    reg.register("vision", _make_stub("vision", "m2", ("text", "image")))
    reg.register("video", _make_stub("video", "m3", ("text", "image", "video")))

    text_capable = reg.find_by_capability(needs_modes={"text"})
    assert sorted(text_capable) == ["text-only", "video", "vision"]

    image_capable = reg.find_by_capability(needs_modes={"image"})
    assert sorted(image_capable) == ["video", "vision"]

    video_capable = reg.find_by_capability(needs_modes={"video"})
    assert video_capable == ["video"]


def test_find_by_capability_empty_when_no_match() -> None:
    reg = ProviderRegistry()
    reg.register("text-only", _make_stub("text-only", "m", ("text",)))
    assert reg.find_by_capability(needs_modes={"video"}) == []
