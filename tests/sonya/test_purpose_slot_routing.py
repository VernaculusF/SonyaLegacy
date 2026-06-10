from __future__ import annotations

import pytest

from sonya.providers.keystore import KeyStore, KeyStatus
from sonya.providers.llm_provider import (
    _PURPOSE_MODEL_HINT,
    _model_for_purpose,
    _provider_fallback_chain,
)
from sonya.state.substrate import Substrate


@pytest.mark.parametrize(
    "purpose",
    [
        "tg_session",
        "idle_thinking",
        "pre_done_critique",
        "active_session",
        "active_session_deep",
        "research",
        "task_worker",
        "selfmod_codegen",
        "selfmod_propose",
        "memory_extraction",
    ],
)
def test_purpose_does_not_force_a_fixed_model(purpose: str) -> None:
    assert _model_for_purpose(purpose) == ""


def test_legacy_purpose_hint_map_is_empty() -> None:
    assert _PURPOSE_MODEL_HINT == {}


def test_fallback_chain_uses_available_key_pool_not_fixed_provider_list(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "fallback.db")
    try:
        store = KeyStore(sub)
        store.add_key(
            provider="nous",
            name="nous-1",
            api_key="nous-key",
            base_url="https://nous.example.test/v1",
            model="",
        )
        store.add_key(
            provider="openrouter",
            name="or-1",
            api_key="or-key",
            base_url="https://openrouter.example.test/v1",
            model="",
        )
        store.add_key(
            provider="codexsale",
            name="cx-disabled",
            api_key="cx-key",
            base_url="https://codex.example.test/v1",
            model="",
        )
        disabled = [key for key in store.list_keys("codexsale")][0]
        store.set_status(disabled.key_id, KeyStatus.DISABLED)

        assert _provider_fallback_chain(store, "nous", explicit_provider=False) == [
            "nous",
            "openrouter",
        ]
    finally:
        sub.close()


def test_explicit_provider_disables_provider_fallbacks(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "fallback.db")
    try:
        store = KeyStore(sub)
        store.add_key(
            provider="nous",
            name="nous-1",
            api_key="nous-key",
            base_url="https://nous.example.test/v1",
            model="",
        )
        store.add_key(
            provider="openrouter",
            name="or-1",
            api_key="or-key",
            base_url="https://openrouter.example.test/v1",
            model="",
        )

        assert _provider_fallback_chain(store, "nous", explicit_provider=True) == ["nous"]
    finally:
        sub.close()
