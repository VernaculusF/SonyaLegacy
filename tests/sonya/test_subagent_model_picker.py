from __future__ import annotations

from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate
from sonya.tools.subagent_model_picker import pick_subagent_model


def _seed_key(store: KeyStore, provider: str, *, model: str = "") -> None:
    base_url = {
        "openrouter": "https://openrouter.ai/api/v1",
        "codexsale": "https://codex.sale/v1",
        "fireworks": "https://api.fireworks.ai/inference/v1",
        "kr": "http://127.0.0.1:20128/v1",
    }.get(provider, "https://example.test/v1")
    store.add_key(provider=provider, name=f"{provider}-1", api_key=f"{provider}-key", base_url=base_url, model=model)


def test_picker_prefers_free_fast_model_for_summary(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        _seed_key(store, "openrouter")
        _seed_key(store, "codexsale")
        pick = pick_subagent_model("summarize and clean this output quickly", store)
        assert pick.provider == "openrouter"
        assert pick.model == "google/gemma-4-26b-a4b-it:free"
    finally:
        sub.close()


def test_picker_prefers_owl_for_research(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        _seed_key(store, "openrouter")
        pick = pick_subagent_model("research and analyze a huge codebase with long context", store)
        assert pick.provider == "openrouter"
        assert pick.model == "openrouter/owl-alpha"
    finally:
        sub.close()


def test_picker_prefers_laguna_for_coding_when_free_available(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        _seed_key(store, "openrouter")
        _seed_key(store, "codexsale")
        pick = pick_subagent_model("debug this python module and refactor the failing code", store)
        assert pick.provider == "openrouter"
        assert pick.model == "poolside/laguna-m.1:free"
    finally:
        sub.close()


def test_picker_uses_premium_for_critical_review(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        _seed_key(store, "openrouter")
        _seed_key(store, "codexsale")
        pick = pick_subagent_model("critical production code review for a high risk change", store)
        assert pick.provider == "codexsale"
        assert pick.model == "gpt-5.5"
    finally:
        sub.close()


def test_picker_respects_explicit_provider_and_auto_selects_model_within_it(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "pick.db")
    try:
        store = KeyStore(sub)
        _seed_key(store, "codexsale")
        pick = pick_subagent_model("quick cleanup and summarize", store, requested_provider="codexsale")
        assert pick.provider == "codexsale"
        assert pick.model == "gpt-5.4-mini"
    finally:
        sub.close()
