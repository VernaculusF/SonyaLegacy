from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

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
