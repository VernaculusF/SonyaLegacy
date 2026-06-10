from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from sonya.providers.adapters.base import ProviderAdapter
from sonya.providers.keystore import KeyStore
from sonya.providers.refresh import ProviderRefreshCoordinator, RefreshResult
from sonya.state.substrate import Substrate


def _seed_provider(
    store: KeyStore,
    provider_id: str,
    *,
    status: str = "active",
    account_status: str = "active",
    refresh_ttl_seconds: int | None = None,
) -> None:
    metadata = {}
    if refresh_ttl_seconds is not None:
        metadata["refresh_ttl_seconds"] = refresh_ttl_seconds
    store.upsert_provider(
        provider_id=provider_id,
        display_name=provider_id.title(),
        adapter_kind="openai_compatible",
        status=status,
        base_url="https://example.test/v1",
        metadata_json=json.dumps(metadata),
    )
    store.add_provider_account(
        provider_id=provider_id,
        name="primary",
        secret_ref="manual:test",
        status=account_status,
    )


def _seed_provider_with_accounts(store: KeyStore) -> tuple[str, str]:
    store.upsert_provider(
        provider_id="pool",
        display_name="Pool",
        adapter_kind="openai_compatible",
        status="active",
        base_url="https://example.test/v1",
        metadata_json=json.dumps({"refresh_ttl_seconds": 3600}),
    )
    first = store.add_provider_account(
        provider_id="pool",
        name="first",
        secret_ref="manual:first",
    )
    second = store.add_provider_account(
        provider_id="pool",
        name="second",
        secret_ref="manual:second",
    )
    return first.account_id, second.account_id


@pytest.mark.asyncio
async def test_coordinator_refreshes_due_active_provider(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "coordinator.db")
    try:
        store = KeyStore(sub)
        _seed_provider(store, "due", refresh_ttl_seconds=60)
        refreshed: list[str] = []

        async def refresh(provider_id: str) -> RefreshResult:
            refreshed.append(provider_id)
            return RefreshResult(provider_id=provider_id, ok=True, models_seen=2)

        coordinator = ProviderRefreshCoordinator(
            store,
            adapter_factory=lambda _store, _provider_id: object(),  # type: ignore[arg-type]
            refresh_provider=refresh,
        )

        results = await coordinator.refresh_due(
            now=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        )

        assert refreshed == ["due"]
        assert results == [RefreshResult(provider_id="due", ok=True, models_seen=2)]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_coordinator_skips_provider_with_fresh_successful_discovery(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "coordinator.db")
    try:
        store = KeyStore(sub)
        _seed_provider(store, "fresh", refresh_ttl_seconds=3600)
        observation = store.record_provider_observation(
            provider_id="fresh",
            observation_kind="model_discovery",
            success=True,
        )
        now = datetime.fromisoformat(observation.observed_at)
        refreshed: list[str] = []

        async def refresh(provider_id: str) -> RefreshResult:
            refreshed.append(provider_id)
            return RefreshResult(provider_id=provider_id, ok=True)

        coordinator = ProviderRefreshCoordinator(
            store,
            adapter_factory=lambda _store, _provider_id: object(),  # type: ignore[arg-type]
            refresh_provider=refresh,
        )

        assert await coordinator.refresh_due(now=now) == []
        assert refreshed == []
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_coordinator_ignores_failed_discovery_when_deciding_freshness(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "coordinator.db")
    try:
        store = KeyStore(sub)
        _seed_provider(store, "retry", refresh_ttl_seconds=3600)
        store.record_provider_observation(
            provider_id="retry",
            observation_kind="model_discovery",
            success=False,
        )
        refreshed: list[str] = []

        async def refresh(provider_id: str) -> RefreshResult:
            refreshed.append(provider_id)
            return RefreshResult(provider_id=provider_id, ok=True)

        coordinator = ProviderRefreshCoordinator(
            store,
            adapter_factory=lambda _store, _provider_id: object(),  # type: ignore[arg-type]
            refresh_provider=refresh,
        )

        await coordinator.refresh_due()

        assert refreshed == ["retry"]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_coordinator_continues_after_adapter_factory_failure(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "coordinator.db")
    try:
        store = KeyStore(sub)
        _seed_provider(store, "broken")
        _seed_provider(store, "disabled", status="disabled")

        def build_adapter(_store: KeyStore, provider_id: str) -> ProviderAdapter:
            raise RuntimeError(f"{provider_id} unavailable")

        coordinator = ProviderRefreshCoordinator(store, adapter_factory=build_adapter)

        results = await coordinator.refresh_due()

        assert len(results) == 1
        assert results[0].provider_id == "broken"
        assert results[0].ok is False
        assert results[0].error == "RuntimeError: broken unavailable"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_coordinator_skips_provider_without_active_accounts(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "coordinator.db")
    try:
        store = KeyStore(sub)
        _seed_provider(store, "not-ready", account_status="disabled")

        coordinator = ProviderRefreshCoordinator(
            store,
            adapter_factory=lambda _store, _provider_id: pytest.fail("must not build adapter"),
        )

        assert await coordinator.refresh_due() == []
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_coordinator_refreshes_due_accounts_independently(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "coordinator.db")
    try:
        store = KeyStore(sub)
        fresh_account_id, due_account_id = _seed_provider_with_accounts(store)
        observation = store.record_provider_observation(
            provider_id="pool",
            account_id=fresh_account_id,
            observation_kind="model_discovery",
            success=True,
        )
        now = datetime.fromisoformat(observation.observed_at)
        refreshed: list[tuple[str, str]] = []

        async def refresh_account(provider_id: str, account_id: str) -> RefreshResult:
            refreshed.append((provider_id, account_id))
            return RefreshResult(provider_id=provider_id, account_id=account_id, ok=True)

        coordinator = ProviderRefreshCoordinator(
            store,
            refresh_account=refresh_account,
        )

        results = await coordinator.refresh_due(now=now)

        assert refreshed == [("pool", due_account_id)]
        assert results == [
            RefreshResult(provider_id="pool", account_id=due_account_id, ok=True)
        ]
    finally:
        sub.close()
