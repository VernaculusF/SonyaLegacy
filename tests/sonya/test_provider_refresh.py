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
        return AdapterInferenceResult(content="ok")


def _seed_provider_and_account(store: KeyStore) -> str:
    store.upsert_provider(
        provider_id="stub",
        display_name="Stub",
        adapter_kind="openai_compatible",
        base_url="https://example.test/v1",
    )
    account = store.add_provider_account(
        provider_id="stub",
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
