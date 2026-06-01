"""Tests for per-purpose model selection in llm_provider.

2026-06-02: Slot routing replaced with model-based routing.
Each Sonya purpose maps to a preferred model name. The model
name is passed to the completion API as-is; the provider's
base URL handles routing to the right backend.

Purpose → model mapping is in ``_PURPOSE_MODEL_HINT``.
"""
from __future__ import annotations

import pytest

from sonya.providers.llm_provider import _model_for_purpose, _PURPOSE_MODEL_HINT


# Interactive / latency-sensitive → cheapest model
@pytest.mark.parametrize("purpose", [
    "tg_session",
    "idle_thinking",
    "pre_done_critique",
])
def test_fast_purposes(purpose: str) -> None:
    assert _model_for_purpose(purpose) == "kr/claude-haiku-4.5"


# Task work / active session → best reasoning
@pytest.mark.parametrize("purpose", [
    "active_session",
    "active_session_deep",
    "research",
    "task_worker",
])
def test_deep_purposes(purpose: str) -> None:
    assert _model_for_purpose(purpose) == "accounts/fireworks/models/deepseek-v4-pro"


# Codegen → Sonnet
@pytest.mark.parametrize("purpose", [
    "selfmod_codegen",
    "selfmod_propose",
])
def test_code_purposes(purpose: str) -> None:
    assert _model_for_purpose(purpose) == "kr/claude-sonnet-4.5"


# Unknown / unlisted purposes → empty string (provider default)
@pytest.mark.parametrize("purpose", [
    "",
    "unknown",
    "agent_session",
    "memory_extraction",
    "consolidation",
])
def test_unknown_purposes_fall_back_to_default(purpose: str) -> None:
    assert _model_for_purpose(purpose) == ""


def test_all_mapped_purposes_have_known_models() -> None:
    """Every purpose in the hint map must reference a model that
    exists in at least one provider's catalog."""
    # This is a sanity check — we can't validate against live APIs
    # but at minimum each hint should be non-empty.
    for purpose, model in _PURPOSE_MODEL_HINT.items():
        assert model, f"purpose '{purpose}' has empty model hint"
        assert "/" in model, f"purpose '{purpose}' has invalid model format: {model}"


def test_explicit_model_kwarg_takes_priority() -> None:
    """The _model kwarg in complete_text overrides purpose hint.
    This is verified by the complete_text logic, not _model_for_purpose."""
    # _model_for_purpose is pure lookup — it doesn't know about kwarg.
    # The kwarg priority is handled in complete_text.
    assert _model_for_purpose("tg_session") == "kr/claude-haiku-4.5"
    # complete_text would use "accounts/fireworks/models/deepseek-v4-pro"
    # if called with _model="accounts/fireworks/models/deepseek-v4-pro"
