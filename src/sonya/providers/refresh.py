from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Mapping

from sonya.providers.adapters.base import AdapterInferenceRequest, ProviderAdapter
from sonya.providers.keystore import KeyStore


@dataclass(frozen=True, slots=True)
class RefreshResult:
    provider_id: str
    ok: bool
    models_seen: int = 0
    quotas_seen: int = 0
    error: str = ""
    account_id: str = ""


class ProviderRefreshService:
    """Refresh provider lifecycle data through structured adapters."""

    def __init__(self, store: KeyStore, adapters: Mapping[str, ProviderAdapter]) -> None:
        self._store = store
        self._adapters = dict(adapters)

    async def refresh_provider(self, provider_id: str) -> RefreshResult:
        accounts = [
            account for account in self._store.list_provider_accounts(provider_id)
            if account.status == "active"
        ]
        if not accounts:
            raise RuntimeError(f"provider {provider_id!r} has no active accounts")
        if len(accounts) == 1:
            result = await self.refresh_account(
                provider_id,
                accounts[0].account_id,
                adapter=self._adapters.get(provider_id),
            )
            return RefreshResult(
                provider_id=result.provider_id,
                ok=result.ok,
                models_seen=result.models_seen,
                quotas_seen=result.quotas_seen,
                error=result.error,
            )

        ok = True
        models_seen = 0
        quotas_seen = 0
        error = ""
        for account in accounts:
            result = await self.refresh_account(
                provider_id,
                account.account_id,
                adapter=self._adapters.get(provider_id),
            )
            ok = ok and result.ok
            models_seen += result.models_seen
            quotas_seen += result.quotas_seen
            if result.error and not error:
                error = result.error
        return RefreshResult(
            provider_id=provider_id,
            ok=ok,
            models_seen=models_seen,
            quotas_seen=quotas_seen,
            error=error,
        )

    async def refresh_account(
        self,
        provider_id: str,
        account_id: str,
        *,
        adapter: ProviderAdapter | None = None,
    ) -> RefreshResult:
        adapter = adapter or self._adapters.get(account_id) or self._adapters.get(provider_id)
        if adapter is None:
            raise KeyError(account_id)
        account = self._store.get_provider_account(account_id)
        if account is None or account.provider_id != provider_id:
            raise KeyError(account_id)
        if account.status != "active":
            raise RuntimeError(f"provider account {account_id!r} is not active")

        ok = True
        error = ""
        models_seen = 0
        quotas_seen = 0

        health = await adapter.health_check()
        self._store.record_provider_observation(
            provider_id=provider_id,
            account_id=account_id,
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
                account_id=account_id,
                observation_kind="model_discovery",
                success=False,
                value_json=json.dumps({"error": error}, ensure_ascii=False),
            )
        else:
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
                if _should_auto_enable_offering(provider_id, model.model_id, metadata):
                    probe_ok = await self._probe_model(provider_id, account_id, adapter, model.model_id)
                    if probe_ok:
                        self._store.set_account_offering(
                            account_id,
                            model.model_id,
                            enabled=True,
                            metadata_json=json.dumps({"source": "auto_probe"}, ensure_ascii=False),
                        )
                    else:
                        self._store.set_account_offering(
                            account_id,
                            model.model_id,
                            enabled=False,
                            metadata_json=json.dumps({"source": "auto_probe", "disabled_reason": "probe_failed"}, ensure_ascii=False),
                        )
                models_seen += 1
            self._store.record_provider_observation(
                provider_id=provider_id,
                account_id=account_id,
                observation_kind="model_discovery",
                success=True,
                value_json=json.dumps({"models_seen": models_seen}, ensure_ascii=False),
            )

        quotas = await adapter.fetch_quota()
        for quota in quotas:
            self._store.upsert_quota_window(
                account_id=account_id,
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
            account_id=account_id,
        )

    async def _probe_model(
        self,
        provider_id: str,
        account_id: str,
        adapter: ProviderAdapter,
        model_id: str,
    ) -> bool:
        if provider_id != "openrouter":
            return True
        try:
            result = await adapter.infer(
                AdapterInferenceRequest(
                    model_id=model_id,
                    messages=[{"role": "user", "content": "x"}],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except Exception as exc:
            self._store.record_provider_observation(
                provider_id=provider_id,
                account_id=account_id,
                model_id=model_id,
                observation_kind="model_probe",
                success=False,
                value_json=json.dumps(
                    {"error": f"{type(exc).__name__}: {exc}"},
                    ensure_ascii=False,
                ),
            )
            return False
        ok = bool(result.content.strip() or result.finish_reason or result.usage)
        self._store.record_provider_observation(
            provider_id=provider_id,
            account_id=account_id,
            model_id=model_id,
            observation_kind="model_probe",
            success=ok,
            value_json=json.dumps(
                {
                    "finish_reason": result.finish_reason,
                    "usage": dict(result.usage),
                    "content_seen": bool(result.content.strip()),
                },
                ensure_ascii=False,
            ),
        )
        return ok


def _should_auto_enable_offering(provider_id: str, model_id: str, metadata: Mapping[str, object]) -> bool:
    if provider_id == "openrouter":
        return metadata.get("free") is True or model_id.endswith(":free")
    return True


class ProviderRefreshCoordinator:
    """Refresh active provider pools when their discovery observation is stale."""

    def __init__(
        self,
        store: KeyStore,
        *,
        adapter_factory: Callable[[KeyStore, str], ProviderAdapter] | None = None,
        account_adapter_factory: Callable[[KeyStore, str, str], ProviderAdapter] | None = None,
        refresh_provider: Callable[[str], Awaitable[RefreshResult]] | None = None,
        refresh_account: Callable[[str, str], Awaitable[RefreshResult]] | None = None,
        default_ttl_seconds: int = 21600,
    ) -> None:
        explicit_adapter_factory = adapter_factory is not None
        if adapter_factory is None:
            from sonya.providers.adapters.factory import build_lifecycle_adapter

            adapter_factory = build_lifecycle_adapter
        if account_adapter_factory is None:
            if explicit_adapter_factory:
                account_adapter_factory = (
                    lambda store, provider_id, _account_id: adapter_factory(store, provider_id)
                )
            else:
                from sonya.providers.adapters.factory import build_lifecycle_adapter_for_account

                account_adapter_factory = build_lifecycle_adapter_for_account
        self._store = store
        self._adapter_factory = adapter_factory
        self._account_adapter_factory = account_adapter_factory
        self._refresh_provider = refresh_provider
        self._refresh_account = refresh_account
        self._default_ttl_seconds = default_ttl_seconds

    async def refresh_due(self, *, now: datetime | None = None) -> list[RefreshResult]:
        now = now or datetime.now(timezone.utc)
        results: list[RefreshResult] = []
        for provider in self._store.list_providers():
            if provider.status != "active":
                continue
            active_accounts = [
                account for account in self._store.list_provider_accounts(provider.provider_id)
                if account.status == "active"
            ]
            if not active_accounts:
                continue
            if self._refresh_provider is not None:
                if not self._is_due(provider.provider_id, now):
                    continue
                try:
                    result = await self._refresh_provider(provider.provider_id)
                except Exception as exc:
                    result = RefreshResult(
                        provider_id=provider.provider_id,
                        ok=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                results.append(result)
                continue

            for account in active_accounts:
                if not self._is_account_due(provider.provider_id, account.account_id, now):
                    continue
                try:
                    if self._refresh_account is not None:
                        result = await self._refresh_account(
                            provider.provider_id,
                            account.account_id,
                        )
                    else:
                        if self._account_adapter_factory is not None:
                            adapter = self._account_adapter_factory(
                                self._store,
                                provider.provider_id,
                                account.account_id,
                            )
                        else:
                            adapter = self._adapter_factory(self._store, provider.provider_id)
                        result = await ProviderRefreshService(
                            self._store,
                            {account.account_id: adapter},
                        ).refresh_account(provider.provider_id, account.account_id)
                except Exception as exc:
                    result = RefreshResult(
                        provider_id=provider.provider_id,
                        account_id=account.account_id,
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

    def _is_account_due(self, provider_id: str, account_id: str, now: datetime) -> bool:
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
            if (
                observation.account_id != account_id
                or observation.observation_kind != "model_discovery"
                or not observation.success
            ):
                continue
            observed_at = datetime.fromisoformat(observation.observed_at.replace("Z", "+00:00"))
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            return now >= observed_at + timedelta(seconds=ttl_seconds)
        return True
