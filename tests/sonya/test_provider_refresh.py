from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from sonya.providers.adapters.base import (
    AdapterCapabilities,
    AdapterHealth,
    AdapterInferenceRequest,
    AdapterInferenceResult,
    DiscoveredModel,
    QuotaSnapshot,
)
from sonya.providers.keystore import KeyStore
from sonya.providers.refresh import ProviderRefreshService, RefreshResult
from sonya.state.substrate import Substrate
from sonya.tools.providers_tool import ProvidersTool


@dataclass
class StubAdapter:
    provider_id: str = "stub"
    models: list[DiscoveredModel] = field(default_factory=list)
    quotas: list[QuotaSnapshot] = field(default_factory=list)
    health: AdapterHealth = AdapterHealth(ok=True, status="ok")
    fail_discovery: bool = False
    failing_infer_models: set[str] = field(default_factory=set)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            provider_id=self.provider_id,
            adapter_kind="stub",
            supports_model_discovery=True,
            supports_health_check=True,
            supports_quota=True,
            supports_inference=True,
        )

    async def discover_models(self) -> list[DiscoveredModel]:
        if self.fail_discovery:
            raise RuntimeError("catalog down")
        return self.models

    async def health_check(self) -> AdapterHealth:
        return self.health

    async def fetch_quota(self) -> list[QuotaSnapshot]:
        return self.quotas

    async def infer(self, request: AdapterInferenceRequest) -> AdapterInferenceResult:
        if request.model_id in self.failing_infer_models:
            raise RuntimeError("model unavailable")
        return AdapterInferenceResult(content="ok")


def _seed_provider_and_account(store: KeyStore, provider_id: str = "stub") -> str:
    store.upsert_provider(
        provider_id=provider_id,
        display_name=provider_id,
        adapter_kind="openai_compatible",
        base_url="https://example.test/v1",
    )
    account = store.add_provider_account(
        provider_id=provider_id,
        name="primary",
        secret_ref="manual:test",
    )
    return account.account_id


def _seed_provider_with_two_accounts(store: KeyStore) -> tuple[str, str]:
    store.upsert_provider(
        provider_id="stub",
        display_name="Stub",
        adapter_kind="openai_compatible",
        base_url="https://example.test/v1",
    )
    first = store.add_provider_account(
        provider_id="stub",
        name="first",
        secret_ref="manual:first",
    )
    second = store.add_provider_account(
        provider_id="stub",
        name="second",
        secret_ref="manual:second",
    )
    return first.account_id, second.account_id


@pytest.mark.asyncio
async def test_refresh_discovers_models_and_account_offerings(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store)
        adapter = StubAdapter(
            models=[
                DiscoveredModel(
                    provider_id="stub",
                    model_id="stub/code",
                    display_name="Stub Code",
                    context_length=131072,
                    modalities=("text",),
                    metadata={"free": True},
                )
            ]
        )

        result = await ProviderRefreshService(store, {"stub": adapter}).refresh_provider("stub")

        assert result == RefreshResult(provider_id="stub", ok=True, models_seen=1, quotas_seen=0)
        model = store.get_provider_model("stub/code")
        assert model is not None
        assert model.provider == "stub"
        assert model.context_length == 131072
        assert model.is_free == 1
        assert [m.model_id for m in store.list_available_provider_models("stub")] == ["stub/code"]
        offerings = sub.connection.execute(
            "SELECT account_id, model_id, enabled FROM provider_account_offerings"
        ).fetchall()
        assert offerings == [(account_id, "stub/code", 1)]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_refresh_preserves_last_good_models_on_discovery_failure(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        _seed_provider_and_account(store)
        service = ProviderRefreshService(
            store,
            {
                "stub": StubAdapter(
                    models=[DiscoveredModel("stub", "stub/good", "Good", 32768)]
                )
            },
        )
        await service.refresh_provider("stub")

        failing = ProviderRefreshService(store, {"stub": StubAdapter(fail_discovery=True)})
        result = await failing.refresh_provider("stub")

        assert result.ok is False
        assert [m.model_id for m in store.list_available_provider_models("stub")] == ["stub/good"]
        observations = store.list_provider_observations(provider_id="stub")
        assert observations[0].observation_kind == "model_discovery"
        assert observations[0].success == 0
        assert "catalog down" in observations[0].value_json
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_openrouter_refresh_auto_enables_only_free_models(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store, provider_id="openrouter")
        adapter = StubAdapter(
            provider_id="openrouter",
            models=[
                DiscoveredModel(
                    provider_id="openrouter",
                    model_id="openrouter/free-model:free",
                    display_name="Free Model",
                    context_length=131072,
                    metadata={"free": True},
                ),
                DiscoveredModel(
                    provider_id="openrouter",
                    model_id="openrouter/paid-model",
                    display_name="Paid Model",
                    context_length=131072,
                    metadata={"free": False},
                ),
            ],
        )

        result = await ProviderRefreshService(store, {"openrouter": adapter}).refresh_provider("openrouter")

        assert result.models_seen == 2
        assert store.get_provider_model("openrouter/free-model:free") is not None
        assert store.get_provider_model("openrouter/paid-model") is not None
        assert [m.model_id for m in store.list_available_provider_models("openrouter")] == [
            "openrouter/free-model:free"
        ]
        offerings = sub.connection.execute(
            "SELECT account_id, model_id, enabled FROM provider_account_offerings ORDER BY model_id"
        ).fetchall()
        assert offerings == [
            (account_id, "openrouter/free-model:free", 1),
            (account_id, "openrouter/paid-model", 0),
        ]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_nous_refresh_auto_enables_only_free_models(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store, provider_id="nous")
        adapter = StubAdapter(
            provider_id="nous",
            models=[
                DiscoveredModel(
                    provider_id="nous",
                    model_id="nous/free-model",
                    display_name="Free Model",
                    context_length=1_000_000,
                    metadata={"free": True},
                ),
                DiscoveredModel(
                    provider_id="nous",
                    model_id="nous/paid-model",
                    display_name="Paid Model",
                    context_length=131072,
                    metadata={"free": False},
                ),
            ],
        )

        result = await ProviderRefreshService(store, {"nous": adapter}).refresh_provider("nous")

        assert result.models_seen == 2
        assert [m.model_id for m in store.list_available_provider_models("nous")] == [
            "nous/free-model"
        ]
        offerings = sub.connection.execute(
            "SELECT account_id, model_id, enabled FROM provider_account_offerings ORDER BY model_id"
        ).fetchall()
        assert offerings == [
            (account_id, "nous/free-model", 1),
            (account_id, "nous/paid-model", 0),
        ]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_google_refresh_disables_models_without_text_generation(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store, provider_id="google")
        adapter = StubAdapter(
            provider_id="google",
            models=[
                DiscoveredModel(
                    provider_id="google",
                    model_id="gemini-text",
                    display_name="Gemini Text",
                    context_length=250000,
                    modalities=("text",),
                    metadata={"raw": {"supportedGenerationMethods": ["generateContent"]}},
                ),
                DiscoveredModel(
                    provider_id="google",
                    model_id="imagen-only",
                    display_name="Imagen",
                    context_length=0,
                    modalities=(),
                    metadata={"raw": {"supportedGenerationMethods": ["predict"]}},
                ),
            ],
        )

        await ProviderRefreshService(store, {"google": adapter}).refresh_provider("google")

        assert [m.model_id for m in store.list_available_provider_models("google")] == [
            "gemini-text"
        ]
        assert store.get_provider_model("imagen-only", provider="google").text_loop_ok == 0
        offerings = sub.connection.execute(
            "SELECT account_id, model_id, enabled FROM provider_account_offerings ORDER BY model_id"
        ).fetchall()
        assert offerings == [
            (account_id, "gemini-text", 1),
            (account_id, "imagen-only", 0),
        ]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_nvidia_refresh_keeps_special_workers_out_of_text_loop(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "nvidia-special.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store, provider_id="nvidia")
        adapter = StubAdapter(
            provider_id="nvidia",
            models=[
                DiscoveredModel(
                    provider_id="nvidia",
                    model_id="nvidia/nemotron-3-ultra-550b-a55b",
                    display_name="Nemotron Ultra",
                    modalities=("text",),
                ),
                DiscoveredModel(
                    provider_id="nvidia",
                    model_id="nvidia/llama-nemotron-rerank-vl-1b-v2",
                    display_name="Nemotron Rerank",
                    modalities=("text",),
                ),
                DiscoveredModel(
                    provider_id="nvidia",
                    model_id="nvidia/nv-embed-v1",
                    display_name="NV Embed",
                    modalities=("text",),
                ),
            ],
        )

        await ProviderRefreshService(store, {"nvidia": adapter}).refresh_provider("nvidia")

        assert store.get_provider_model(
            "nvidia/nemotron-3-ultra-550b-a55b", provider="nvidia"
        ).text_loop_ok == 1
        assert store.get_provider_model(
            "nvidia/llama-nemotron-rerank-vl-1b-v2", provider="nvidia"
        ).text_loop_ok == 0
        assert store.get_provider_model("nvidia/nv-embed-v1", provider="nvidia").text_loop_ok == 0
        assert [model.model_id for model in store.list_available_provider_models("nvidia")] == [
            "nvidia/nemotron-3-ultra-550b-a55b"
        ]
        offerings = sub.connection.execute(
            "SELECT model_id, enabled FROM provider_account_offerings "
            "WHERE account_id = ? ORDER BY model_id",
            (account_id,),
        ).fetchall()
        assert offerings == [
            ("nvidia/llama-nemotron-rerank-vl-1b-v2", 0),
            ("nvidia/nemotron-3-ultra-550b-a55b", 1),
            ("nvidia/nv-embed-v1", 0),
        ]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_codexsale_refresh_removes_stale_prefixed_manual_alias(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        _seed_provider_and_account(store, provider_id="codexsale")
        store.upsert_provider_model(
            model_id="codexsale/gpt-5.4",
            provider="codexsale",
            model_name="Legacy prefixed GPT-5.4",
            discovery_source="manual",
        )
        store.upsert_provider_model(
            model_id="codexsale/gpt-image-2",
            provider="codexsale",
            model_name="GPT Image 2",
            discovery_source="manual",
        )
        adapter = StubAdapter(
            provider_id="codexsale",
            models=[
                DiscoveredModel(
                    provider_id="codexsale",
                    model_id="gpt-5.4",
                    display_name="GPT-5.4",
                    context_length=131072,
                    modalities=("text",),
                )
            ],
        )

        await ProviderRefreshService(store, {"codexsale": adapter}).refresh_provider("codexsale")

        assert store.get_provider_model("codexsale/gpt-5.4", provider="codexsale") is None
        assert store.get_provider_model("codexsale/gpt-image-2", provider="codexsale") is None
        assert store.get_provider_model("gpt-5.4", provider="codexsale") is not None
        assert store.get_provider_model("gpt-image-2", provider="codexsale").text_loop_ok == 0
        assert sorted(m.model_id for m in store.list_provider_models("codexsale", enabled_only=False)) == [
            "gpt-5.4",
            "gpt-image-2",
        ]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_openrouter_refresh_probes_free_models_before_enabling(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store, provider_id="openrouter")
        adapter = StubAdapter(
            provider_id="openrouter",
            models=[
                DiscoveredModel(
                    provider_id="openrouter",
                    model_id="qwen/qwen3-coder:free",
                    display_name="Qwen Coder",
                    context_length=131072,
                    metadata={"free": True},
                ),
                DiscoveredModel(
                    provider_id="openrouter",
                    model_id="google/gemma-4-31b-it:free",
                    display_name="Gemma",
                    context_length=262144,
                    metadata={"free": True},
                ),
            ],
            failing_infer_models={"qwen/qwen3-coder:free"},
        )

        await ProviderRefreshService(store, {"openrouter": adapter}).refresh_provider("openrouter")

        assert [m.model_id for m in store.list_available_provider_models("openrouter")] == [
            "google/gemma-4-31b-it:free"
        ]
        offerings = sub.connection.execute(
            "SELECT account_id, model_id, enabled FROM provider_account_offerings ORDER BY model_id"
        ).fetchall()
        assert offerings == [
            (account_id, "google/gemma-4-31b-it:free", 1),
            (account_id, "qwen/qwen3-coder:free", 0),
        ]
        observations = store.list_provider_observations(provider_id="openrouter")
        failed_probe = next(
            item for item in observations
            if item.observation_kind == "model_probe" and item.model_id == "qwen/qwen3-coder:free"
        )
        assert failed_probe.success == 0
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_openrouter_refresh_disables_stale_non_requested_offerings(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store, provider_id="openrouter")
        store.upsert_provider_model(
            model_id="google/lyria-3-clip-preview",
            provider="openrouter",
            model_name="Lyria",
            is_free=1,
            discovery_source="adapter",
        )
        store.upsert_provider_model(
            model_id="vendor/requested-paid",
            provider="openrouter",
            model_name="Requested Paid",
            is_free=0,
            discovery_source="adapter",
        )
        store.set_account_offering(account_id, "google/lyria-3-clip-preview", enabled=True)
        store.set_account_offering(
            account_id,
            "vendor/requested-paid",
            enabled=True,
            metadata_json='{"source":"manual_admin","requested":true}',
        )
        adapter = StubAdapter(
            provider_id="openrouter",
            models=[
                DiscoveredModel(
                    provider_id="openrouter",
                    model_id="google/lyria-3-clip-preview",
                    display_name="Lyria",
                    context_length=131072,
                    metadata={"free": False},
                ),
                DiscoveredModel(
                    provider_id="openrouter",
                    model_id="vendor/requested-paid",
                    display_name="Requested Paid",
                    context_length=131072,
                    metadata={"free": False},
                ),
            ],
        )

        await ProviderRefreshService(store, {"openrouter": adapter}).refresh_provider("openrouter")

        offerings = sub.connection.execute(
            "SELECT model_id, enabled FROM provider_account_offerings ORDER BY model_id"
        ).fetchall()
        assert offerings == [
            ("google/lyria-3-clip-preview", 0),
            ("vendor/requested-paid", 1),
        ]
        assert [m.model_id for m in store.list_available_provider_models("openrouter")] == [
            "vendor/requested-paid"
        ]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_refresh_records_health_and_quota_windows(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        account_id = _seed_provider_and_account(store)
        adapter = StubAdapter(
            health=AdapterHealth(ok=True, status="ok", latency_ms=25, message="ready"),
            quotas=[
                QuotaSnapshot(
                    quota_kind="rpd",
                    limit_value=1000,
                    used_value=10,
                    remaining_value=990,
                    unit="requests",
                    resets_at="2026-06-11T00:00:00+00:00",
                )
            ],
        )

        result = await ProviderRefreshService(store, {"stub": adapter}).refresh_provider("stub")

        assert result.ok is True
        assert result.quotas_seen == 1
        quotas = store.list_quota_windows(account_id)
        assert len(quotas) == 1
        assert quotas[0].quota_kind == "rpd"
        assert quotas[0].remaining_value == 990
        health = [
            item for item in store.list_provider_observations(provider_id="stub")
            if item.observation_kind == "health"
        ]
        assert health and health[0].success == 1
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_refresh_account_scopes_observations_offerings_and_quotas(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "refresh.db")
    try:
        store = KeyStore(sub)
        first_account_id, second_account_id = _seed_provider_with_two_accounts(store)
        adapter = StubAdapter(
            models=[DiscoveredModel("stub", "stub/account-model", "Account Model", 65536)],
            quotas=[
                QuotaSnapshot(
                    quota_kind="tpm",
                    limit_value=500000,
                    used_value=1000,
                    remaining_value=499000,
                    unit="tokens",
                )
            ],
        )

        result = await ProviderRefreshService(
            store,
            {"stub": adapter},
        ).refresh_account("stub", first_account_id)

        assert result == RefreshResult(
            provider_id="stub",
            ok=True,
            models_seen=1,
            quotas_seen=1,
            account_id=first_account_id,
        )
        offerings = sub.connection.execute(
            "SELECT account_id, model_id, enabled FROM provider_account_offerings ORDER BY account_id"
        ).fetchall()
        assert offerings == [(first_account_id, "stub/account-model", 1)]
        assert store.list_quota_windows(first_account_id)
        assert store.list_quota_windows(second_account_id) == []
        observations = store.list_provider_observations(provider_id="stub")
        assert {item.observation_kind for item in observations} == {"health", "model_discovery"}
        assert all(item.account_id == first_account_id for item in observations)
    finally:
        sub.close()


def test_providers_tool_lists_models_from_substrate_pool(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "tool.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="stub",
            display_name="Stub",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="stub",
            name="primary",
            secret_ref="manual:test",
        )
        model = store.upsert_provider_model(
            model_id="stub/listed",
            provider="stub",
            model_name="Listed",
            context_length=64000,
            is_free=1,
            discovery_source="adapter",
        )
        store.set_account_offering(account.account_id, model.model_id, enabled=True)

        out = ProvidersTool(sub).list_models("stub")

        assert "stub | stub/listed | ctx=64000 | free" in out
        assert "unknown provider" not in out
    finally:
        sub.close()
