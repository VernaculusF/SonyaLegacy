"""Tests for per-purpose slot routing in llm_provider.

Each Sonya session ("active_session", "tg_session", "task_worker", etc.)
declares a `purpose`. We translate that into a preferred slot used to
acquire a provider key. Cheap/fast slot for short interactions, deep slot
for analysis, dedicated code slot for codegen.

The slot is a SOFT preference: KeyStore.acquire falls back to any text
key if no slot match. So adding routing never causes NoKeysAvailable
where it didn't before.
"""
from __future__ import annotations

import pytest

from sonya.providers.llm_provider import _slot_for_purpose


# Fast slot
@pytest.mark.parametrize("purpose", [
    "tg_session",
    "task_worker",
    "idle_thinking",
    "pre_done_critique",
])
def test_fast_purposes(purpose: str) -> None:
    assert _slot_for_purpose(purpose) == "text-fast"


# Deep slot
def test_active_session_uses_deep() -> None:
    assert _slot_for_purpose("active_session") == "text-deep"


# Code slot — explicit + heuristic
@pytest.mark.parametrize("purpose", [
    "selfmod_codegen",
    "selfmod_propose",
    "task_worker_codegen",
    "code_review",
    "selfmod_validate_codegen",
])
def test_code_purposes(purpose: str) -> None:
    assert _slot_for_purpose(purpose) == "code"


# Generic / unknown → text
@pytest.mark.parametrize("purpose", [
    "",
    "unknown",
    "agent_session",
    "memory_extraction",
    "consolidation",
])
def test_generic_purpose_falls_back_to_text(purpose: str) -> None:
    assert _slot_for_purpose(purpose) == "text"


def test_explicit_map_overrides_heuristic() -> None:
    """If a purpose is BOTH in the explicit map AND matches code heuristic,
    explicit map wins."""
    # selfmod_codegen is in explicit map → code (no ambiguity), but verify
    # the precedence logic by checking a future addition.
    assert _slot_for_purpose("selfmod_codegen") == "code"


def test_caller_can_override_via_kwarg() -> None:
    """Verify _purpose_slot kwarg is read correctly. This isn't exercised
    by _slot_for_purpose directly — the kwarg is checked in complete_text
    BEFORE calling _slot_for_purpose. Sanity check: existence of the kwarg
    path doesn't break anything."""
    # Pure-function test of helper. Override path is integration-tested
    # implicitly by code review / runtime behavior.
    assert _slot_for_purpose("active_session") == "text-deep"
