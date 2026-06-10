from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Mapping

from sonya.providers.adapters.base import ProviderAdapter
from sonya.providers.keystore import KeyStore


@dataclass(frozen=True, slots=True)
class RefreshResult:
    provider_id: str
    ok: bool
    models_seen: int = 0
    quotas_seen: int = 0
    error: str = ""


class ProviderRefreshService:
    """Refresh provider lifecycle data through structured adapters."""

    def __init__(self, store: KeyStore, adapters: Mapping[str, ProviderAdapter]) -> None:
        self._store = store
        self._adapters = dict(adapters)

    async def refresh_provider(self, provider_id: str) -> RefreshResult:
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            raise KeyError(provider_id)

        ok = True
        error = ""
        models_seen = 0
        quotas_seen = 0

        health = await adapter.health_check()
        self._store.record_provider_observation(
            provider_id=provider_id,
            observation_kind="health",
            success=health.ok,
            latency_ms=health.latency_ms,
            value_json=json.dumps(
                {
                    "status": health.status,
                    "message": health.message,
                    "metadata": dict(health.metadata),
                },
                ensure_ascii=False,
            ),
        )
        ok = ok and health.ok

        try:
            discovered = await adapter.discover_models()
        except Exception as exc:
            ok = False
            error = f"{type(exc).__name__}: {exc}"
            self._store.record_provider_observation(
                provider_id=provider_id,
                observation_kind="model_discovery",
                success=False,
                value_json=json.dumps({"error": error}, ensure_ascii=False),
            )
        else:
            active_accounts = [
                account for account in self._store.list_provider_accounts(provider_id)
                if account.status == "active"
            ]
            for model in discovered:
                metadata = dict(model.metadata)
                self._store.upsert_provider_model(
                    model_id=model.model_id,
                    provider=provider_id,
                    model_name=model.display_name,
                    context_length=model.context_length,
                    modalities_json=json.dumps(list(model.modalities), ensure_ascii=False),
                    cost_per_1m_input_tokens=model.input_cost_per_1m,
                    cost_per_1m_output_tokens=model.output_cost_per_1m,
                    is_free=1 if metadata.get("free") is True else 0,
                    discovery_source="adapter",
                    metadata_json=json.dumps(metadata, ensure_ascii=False),
                )
                for account in active_accounts:
                    self._store.set_account_offering(account.account_id, model.model_id, enabled=True)
                models_seen += 1
            self._store.record_provider_observation(
                provider_id=provider_id,
                observation_kind="model_discovery",
                success=True,
                value_json=json.dumps({"models_seen": models_seen}, ensure_ascii=False),
            )

        quotas = await adapter.fetch_quota()
        active_accounts = [
            account for account in self._store.list_provider_accounts(provider_id)
            if account.status == "active"
        ]
        for account in active_accounts:
            for quota in quotas:
                self._store.upsert_quota_window(
                    account_id=account.account_id,
                    quota_kind=quota.quota_kind,
                    limit_value=quota.limit_value,
                    used_value=quota.used_value,
                    remaining_value=quota.remaining_value,
                    unit=quota.unit,
                    resets_at=quota.resets_at,
                    metadata_json=json.dumps(dict(quota.metadata), ensure_ascii=False),
                )
                quotas_seen += 1

        return RefreshResult(
            provider_id=provider_id,
            ok=ok,
            models_seen=models_seen,
            quotas_seen=quotas_seen,
            error=error,
        )


class ProviderRefreshCoordinator:
    """Refresh active provider pools when their discovery observation is stale."""

    def __init__(
        self,
        store: KeyStore,
        *,
        adapter_factory: Callable[[KeyStore, str], ProviderAdapter] | None = None,
        refresh_provider: Callable[[str], Awaitable[RefreshResult]] | None = None,
        default_ttl_seconds: int = 21600,
    ) -> None:
        if adapter_factory is None:
            from sonya.providers.adapters.factory import build_lifecycle_adapter

            adapter_factory = build_lifecycle_adapter
        self._store = store
        self._adapter_factory = adapter_factory
        self._refresh_provider = refresh_provider
        self._default_ttl_seconds = default_ttl_seconds

    async def refresh_due(self, *, now: datetime | None = None) -> list[RefreshResult]:
        now = now or datetime.now(timezone.utc)
        results: list[RefreshResult] = []
        for provider in self._store.list_providers():
            if provider.status != "active" or not self._is_due(provider.provider_id, now):
                continue
            try:
                if self._refresh_provider is not None:
                    result = await self._refresh_provider(provider.provider_id)
                else:
                    adapter = self._adapter_factory(self._store, provider.provider_id)
                    result = await ProviderRefreshService(
                        self._store,
                        {provider.provider_id: adapter},
                    ).refresh_provider(provider.provider_id)
            except Exception as exc:
                result = RefreshResult(
                    provider_id=provider.provider_id,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            results.append(result)
        return results

    def _is_due(self, provider_id: str, now: datetime) -> bool:
        provider = self._store.get_provider(provider_id)
        if provider is None:
            return False
        try:
            metadata = json.loads(provider.metadata_json or "{}")
        except (TypeError, ValueError):
            metadata = {}
        ttl_seconds = metadata.get("refresh_ttl_seconds", self._default_ttl_seconds)
        if not isinstance(ttl_seconds, (int, float)) or ttl_seconds <= 0:
            ttl_seconds = self._default_ttl_seconds

        for observation in self._store.list_provider_observations(provider_id=provider_id):
            if observation.observation_kind != "model_discovery" or not observation.success:
                continue
            observed_at = datetime.fromisoformat(observation.observed_at.replace("Z", "+00:00"))
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            return now >= observed_at + timedelta(seconds=ttl_seconds)
        return True
