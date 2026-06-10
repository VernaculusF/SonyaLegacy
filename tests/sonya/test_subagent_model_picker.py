from __future__ import annotations

import json

from sonya.memory.tool_experience import ToolExperience
from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate
from sonya.tools.subagent_model_picker import (
    PickPolicy,
    is_text_loop_model,
    list_known_profiles,
    pick_subagent_model,
)


def _seed_provider(store: KeyStore, provider: str, *, status: str = "active") -> str:
    store.upsert_provider(
        provider_id=provider,
        display_name=provider.title(),
        adapter_kind="openai_compatible",
        status=status,
        base_url=f"https://{provider}.example.test/v1",
    )
    account = store.add_provider_account(
        provider_id=provider,
        name=f"{provider}-primary",
        secret_ref=f"manual:{provider}",
    )
    return account.account_id


def _seed_available_model(
    store: KeyStore,
    account_id: str,
    *,
    provider: str,
    model_id: str,
    name: str = "",
    context_length: int = 131072,
    is_free: int = 1,
    latency_tier: str = "medium",
    strengths: dict[str, float] | None = None,
    role_preference: str = "auto",
    text_loop_ok: int = 1,
) -> None:
    store.upsert_provider_model(
        model_id=model_id,
        provider=provider,
        model_name=name or model_id,
        context_length=context_length,
        is_free=is_free,
        latency_tier=latency_tier,
        strength_json=json.dumps(strengths or {}),
        role_preference=role_preference,
        text_loop_ok=text_loop_ok,
        discovery_source="test",
    )
    store.set_account_offering(account_id, model_id, enabled=True)


def test_picker_uses_only_available_substrate_offerings(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "openrouter")
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/cheap-cleaner",
            latency_tier="very_fast",
            strengths={"summary": 0.9, "cleanup": 0.9},
        )
        store.upsert_provider_model(
            model_id="fireworks/dead-hardcoded-profile",
            provider="fireworks",
            model_name="Dead Fireworks",
            strength_json=json.dumps({"coding": 1.0}),
        )

        pick = pick_subagent_model("summarize and clean this output quickly", store)

        assert pick.provider == "openrouter"
        assert pick.model == "openrouter/cheap-cleaner"
        assert "substrate" in pick.reason
        assert all(profile.model != "fireworks/dead-hardcoded-profile" for profile in list_known_profiles())
    finally:
        sub.close()


def test_picker_filters_models_without_active_account_offering(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "openrouter")
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/available-coder",
            strengths={"coding": 0.8},
        )
        store.upsert_provider_model(
            model_id="openrouter/unoffered-strong-coder",
            provider="openrouter",
            model_name="Unavailable Strong Coder",
            strength_json=json.dumps({"coding": 1.0}),
            enabled=1,
        )

        pick = pick_subagent_model("debug this python module", store)

        assert pick.model == "openrouter/available-coder"
    finally:
        sub.close()


def test_picker_uses_experience_as_soft_ranking_signal(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "openrouter")
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/new-coder",
            strengths={"coding": 0.8},
        )
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/proven-coder",
            strengths={"coding": 0.8},
        )
        tx = ToolExperience(sub)
        for _ in range(6):
            tx.record(
                tool_name="subagent.spawn",
                outcome="success",
                provider="openrouter",
                model="openrouter/proven-coder",
                latency_ms=500,
            )

        pick = pick_subagent_model("debug this python module", store, substrate=sub)

        assert pick.model == "openrouter/proven-coder"
    finally:
        sub.close()


def test_explicit_provider_auto_selects_available_model_within_provider(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "codexsale")
        _seed_available_model(
            store,
            account_id,
            provider="codexsale",
            model_id="gpt-fast-cleaner",
            is_free=0,
            latency_tier="fast",
            strengths={"summary": 0.8, "cleanup": 0.8},
        )

        pick = pick_subagent_model(
            "quick cleanup and summarize",
            store,
            requested_provider="codexsale",
        )

        assert pick.provider == "codexsale"
        assert pick.model == "gpt-fast-cleaner"
    finally:
        sub.close()


def test_explicit_provider_still_honors_free_preference(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "openrouter")
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/free-coder",
            is_free=1,
            strengths={"coding": 0.8},
        )
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/paid-coder",
            is_free=0,
            strengths={"coding": 0.8},
        )

        pick = pick_subagent_model(
            "debug this python module",
            store,
            requested_provider="openrouter",
        )

        assert pick.model == "openrouter/free-coder"
    finally:
        sub.close()


def test_special_worker_models_are_not_text_loop_capable_from_substrate(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "codexsale")
        _seed_available_model(
            store,
            account_id,
            provider="codexsale",
            model_id="gpt-image-2",
            text_loop_ok=0,
        )

        assert is_text_loop_model("gpt-image-2", "codexsale", store=store) is False
    finally:
        sub.close()


def test_role_policy_biases_to_matching_role_preference(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider(store, "openrouter")
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/executor",
            strengths={"coding": 0.8},
            role_preference="executor",
            latency_tier="fast",
        )
        _seed_available_model(
            store,
            account_id,
            provider="openrouter",
            model_id="openrouter/reviewer",
            strengths={"coding": 0.8, "critical_review": 0.9},
            role_preference="reviewer",
            latency_tier="medium",
        )

        pick = pick_subagent_model(
            "review this production code change",
            store,
            policy=PickPolicy(role="reviewer"),
        )

        assert pick.model == "openrouter/reviewer"
    finally:
        sub.close()
