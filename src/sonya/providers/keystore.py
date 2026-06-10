"""Substrate-backed key store and rotation.

Holds the rotating pool of provider API keys (Fireworks / OpenRouter / etc).
Survives restarts. Manageable through admin UI (POST /api/providers/keys).

`KeyStatus`:
  active   — eligible for rotation
  cooldown — auto-suspended for N seconds after 429 / 5xx
  banned   — auto on 401/403; manual unban required
  disabled — manual off

Selection rule: among `active` keys for the requested provider, pick the
LEAST-RECENTLY-USED one whose cooldown has expired. Round-robin balanced.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from sonya.providers.secrets import ProviderSecret, ProviderSecretStore, mask_secret
from sonya.state.substrate import Substrate


class KeyStatus(str, Enum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    BANNED = "banned"
    DISABLED = "disabled"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class ProviderKey:
    key_id: str
    provider: str
    name: str
    api_key: str
    base_url: str
    model: str           # empty = use provider_settings.default_model
    status: KeyStatus
    priority: int
    cooldown_until: str
    last_used_at: str
    last_error: str
    last_error_at: str
    request_count: int
    success_count: int
    error_count: int
    created_at: str
    updated_at: str
    # v11 additions
    account_id: str = ""
    balance_json: str = "{}"
    balance_checked_at: str = ""
    # v17: routing slot — what purpose this key serves
    # values: text, vision, voice, video, image_gen
    slot: str = "text"

    def is_eligible(self, now: datetime | None = None) -> bool:
        if self.status is not KeyStatus.ACTIVE:
            if self.status is KeyStatus.COOLDOWN:
                # Re-eligible once cooldown elapsed
                until = _parse_iso(self.cooldown_until)
                if until is None or (now or datetime.now(timezone.utc)) >= until:
                    return True
            return False
        return True

    def masked(self) -> str:
        return self.api_key[:6] + "..." + self.api_key[-4:] if len(self.api_key) > 12 else "***"

    def balance(self) -> dict:
        """Decoded balance snapshot. Empty dict if never refreshed."""
        try:
            import json as _json
            return _json.loads(self.balance_json or "{}")
        except Exception:
            return {}


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    active_provider: str
    default_model: str
    default_base_url: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class Provider:
    provider_id: str
    display_name: str
    adapter_kind: str
    status: str
    base_url: str
    capabilities_json: str
    constraints_json: str
    metadata_json: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    account_id: str
    provider_id: str
    name: str
    secret_ref: str
    masked_secret: str
    legacy_key_id: str
    status: str
    priority: int
    constraints_json: str
    metadata_json: str
    created_at: str
    updated_at: str
    default_model: str = ""


@dataclass(frozen=True, slots=True)
class ProviderQuotaWindow:
    quota_window_id: str
    account_id: str
    quota_kind: str
    limit_value: float | None
    used_value: float | None
    remaining_value: float | None
    unit: str
    window_started_at: str
    resets_at: str
    observed_at: str
    metadata_json: str


@dataclass(frozen=True, slots=True)
class ProviderObservation:
    observation_id: str
    provider_id: str
    account_id: str
    model_id: str
    observation_kind: str
    success: int
    latency_ms: int
    value_json: str
    observed_at: str


@dataclass(frozen=True, slots=True)
class ProviderModel:
    model_id: str
    provider: str
    model_name: str
    base_url: str
    api_key_ref: str
    context_length: int
    modalities_json: str
    cost_per_1m_input_tokens: float
    cost_per_1m_output_tokens: float
    is_free: int
    latency_tier: str
    strength_json: str
    role_preference: str
    enabled: int
    text_loop_ok: int = 1
    last_checked_at: str = ''
    discovery_source: str = 'manual'
    metadata_json: str = '{}'
    created_at: str = ''
    updated_at: str = ''

    def modalities(self) -> list[str]:
        try:
            import json as _json
            return _json.loads(self.modalities_json or '["text"]')
        except Exception:
            return ["text"]

    def strengths(self) -> dict[str, float]:
        try:
            import json as _json
            return _json.loads(self.strength_json or '{}')
        except Exception:
            return {}

    def metadata(self) -> dict:
        try:
            import json as _json
            return _json.loads(self.metadata_json or '{}')
        except Exception:
            return {}


class KeyStore:
    """SQLite-backed CRUD + rotation. Thread-safe via asyncio.Lock."""

    def __init__(self, substrate: Substrate, *, secret_encryption_key: str | bytes | None = None) -> None:
        self._sub = substrate
        self._lock = asyncio.Lock()
        self._secrets = ProviderSecretStore(substrate, encryption_key=secret_encryption_key)

    # ---------- settings ----------

    def get_settings(self) -> ProviderSettings:
        row = self._sub.connection.execute(
            "SELECT active_provider, default_model, default_base_url, updated_at "
            "FROM provider_settings WHERE id = 1"
        ).fetchone()
        if row is None:
            return ProviderSettings("openrouter", "", "https://openrouter.ai/api/v1", "")
        return ProviderSettings(
            active_provider=row[0],
            default_model=row[1],
            default_base_url=row[2],
            updated_at=row[3],
        )

    def set_settings(
        self,
        *,
        active_provider: str | None = None,
        default_model: str | None = None,
        default_base_url: str | None = None,
    ) -> ProviderSettings:
        cur = self.get_settings()
        ap = active_provider if active_provider is not None else cur.active_provider
        dm = default_model if default_model is not None else cur.default_model
        bu = default_base_url if default_base_url is not None else cur.default_base_url
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_settings(id, active_provider, default_model, default_base_url, updated_at) "
            "VALUES (1, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET active_provider=excluded.active_provider, "
            "default_model=excluded.default_model, default_base_url=excluded.default_base_url, "
            "updated_at=excluded.updated_at",
            (ap, dm, bu, now),
        )
        self._sub.connection.commit()
        return self.get_settings()

    # ---------- provider registry / accounts ----------

    def upsert_provider(
        self,
        *,
        provider_id: str,
        display_name: str,
        adapter_kind: str,
        status: str = "active",
        base_url: str = "",
        capabilities_json: str = "{}",
        constraints_json: str = "{}",
        metadata_json: str = "{}",
    ) -> Provider:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO providers "
            "(provider_id, display_name, adapter_kind, status, base_url, capabilities_json, "
            "constraints_json, metadata_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(provider_id) DO UPDATE SET display_name=excluded.display_name, "
            "adapter_kind=excluded.adapter_kind, status=excluded.status, base_url=excluded.base_url, "
            "capabilities_json=excluded.capabilities_json, constraints_json=excluded.constraints_json, "
            "metadata_json=excluded.metadata_json, updated_at=excluded.updated_at",
            (
                provider_id, display_name, adapter_kind, status, base_url,
                capabilities_json, constraints_json, metadata_json, now, now,
            ),
        )
        self._sub.connection.commit()
        return self.get_provider(provider_id)  # type: ignore[return-value]

    def get_provider(self, provider_id: str) -> Provider | None:
        row = self._sub.connection.execute(
            "SELECT provider_id, display_name, adapter_kind, status, base_url, "
            "capabilities_json, constraints_json, metadata_json, created_at, updated_at "
            "FROM providers WHERE provider_id = ?",
            (provider_id,),
        ).fetchone()
        return _row_to_provider(row) if row else None

    def list_providers(self, *, enabled_only: bool = False) -> list[Provider]:
        where = "WHERE status IN ('active', 'degraded')" if enabled_only else ""
        rows = self._sub.connection.execute(
            "SELECT provider_id, display_name, adapter_kind, status, base_url, "
            "capabilities_json, constraints_json, metadata_json, created_at, updated_at "
            f"FROM providers {where} ORDER BY provider_id"
        ).fetchall()
        return [_row_to_provider(row) for row in rows]

    def delete_provider(self, provider_id: str) -> None:
        self._sub.connection.execute("DELETE FROM providers WHERE provider_id = ?", (provider_id,))
        self._sub.connection.commit()

    def add_provider_account(
        self,
        *,
        provider_id: str,
        name: str,
        secret_ref: str = "",
        secret_value: str = "",
        status: str = "active",
        priority: int = 0,
        constraints_json: str = "{}",
        metadata_json: str = "{}",
        account_id: str = "",
        legacy_key_id: str = "",
    ) -> ProviderAccount:
        if self.get_provider(provider_id) is None:
            raise ValueError(f"unknown provider: {provider_id}")
        account_id = account_id or f"pa-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_accounts "
            "(account_id, provider_id, name, secret_ref, secret_masked, legacy_key_id, status, priority, "
            "constraints_json, metadata_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                account_id, provider_id, name, secret_ref, "", legacy_key_id, status,
                priority, constraints_json, metadata_json, now, now,
            ),
        )
        if secret_value:
            record = self._secrets.store_secret(
                provider_id=provider_id,
                account_id=account_id,
                secret_kind="api_key",
                raw_value=secret_value,
            )
            self._sub.connection.execute(
                "UPDATE provider_accounts SET secret_ref = ?, secret_masked = ?, updated_at = ? "
                "WHERE account_id = ?",
                (record.secret_ref, record.masked_value, _utc_now_iso(), account_id),
            )
        self._sub.connection.commit()
        return self.get_provider_account(account_id)  # type: ignore[return-value]

    def get_provider_account(self, account_id: str) -> ProviderAccount | None:
        row = self._sub.connection.execute(
            "SELECT account_id, provider_id, name, secret_ref, secret_masked, legacy_key_id, status, "
            "priority, constraints_json, metadata_json, created_at, updated_at "
            "FROM provider_accounts WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        return _row_to_provider_account(row) if row else None

    def list_provider_accounts(self, provider_id: str | None = None) -> list[ProviderAccount]:
        if provider_id:
            rows = self._sub.connection.execute(
                "SELECT account_id, provider_id, name, secret_ref, secret_masked, legacy_key_id, status, "
                "priority, constraints_json, metadata_json, created_at, updated_at "
                "FROM provider_accounts WHERE provider_id = ? ORDER BY priority DESC, created_at",
                (provider_id,),
            ).fetchall()
        else:
            rows = self._sub.connection.execute(
                "SELECT account_id, provider_id, name, secret_ref, secret_masked, legacy_key_id, status, "
                "priority, constraints_json, metadata_json, created_at, updated_at "
                "FROM provider_accounts ORDER BY provider_id, priority DESC, created_at"
            ).fetchall()
        return [_row_to_provider_account(row) for row in rows]

    def resolve_account_secret(self, account_id: str) -> ProviderSecret:
        account = self.get_provider_account(account_id)
        if account is None:
            raise KeyError(account_id)
        if account.secret_ref.startswith("provider-secret:"):
            return self._secrets.resolve(account.secret_ref)
        if account.secret_ref.startswith("legacy-provider-key:"):
            key_id = account.secret_ref.split(":", 1)[1]
            key = self.get_key(key_id)
            if key is None:
                raise KeyError(account.secret_ref)
            return ProviderSecret(key.api_key)
        raise ValueError(f"unsupported account secret ref: {account.secret_ref}")

    def rotate_account_secret(
        self,
        account_id: str,
        raw_value: str,
        *,
        secret_kind: str = "api_key",
    ) -> ProviderAccount:
        account = self.get_provider_account(account_id)
        if account is None:
            raise KeyError(account_id)
        record = self._secrets.rotate_secret(
            provider_id=account.provider_id,
            account_id=account_id,
            secret_kind=secret_kind,
            raw_value=raw_value,
        )
        self._sub.connection.execute(
            "UPDATE provider_accounts SET secret_ref = ?, secret_masked = ?, updated_at = ? "
            "WHERE account_id = ?",
            (record.secret_ref, record.masked_value, _utc_now_iso(), account_id),
        )
        self._sub.connection.commit()
        return self.get_provider_account(account_id)  # type: ignore[return-value]

    def migrate_legacy_account_secret(self, account_id: str) -> ProviderAccount:
        """Encrypt an account's legacy provider-key secret without exposing it."""
        account = self.get_provider_account(account_id)
        if account is None:
            raise KeyError(account_id)
        if account.secret_ref.startswith("provider-secret:"):
            return account
        if not account.secret_ref.startswith("legacy-provider-key:"):
            raise ValueError(f"account is not backed by a legacy provider key: {account_id}")
        key_id = account.secret_ref.split(":", 1)[1]
        key = self.get_key(key_id)
        if key is None:
            raise KeyError(account.secret_ref)
        migrated = self.rotate_account_secret(account_id, key.api_key)
        self._sub.connection.execute(
            "UPDATE provider_keys SET api_key = '', updated_at = ? WHERE key_id = ?",
            (_utc_now_iso(), key_id),
        )
        self._sub.connection.commit()
        return migrated

    def update_provider_account_status(self, account_id: str, status: str) -> None:
        self._sub.connection.execute(
            "UPDATE provider_accounts SET status = ?, updated_at = ? WHERE account_id = ?",
            (status, _utc_now_iso(), account_id),
        )
        self._sub.connection.commit()

    def update_provider_account(
        self,
        account_id: str,
        *,
        name: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        constraints_json: str | None = None,
        metadata_json: str | None = None,
    ) -> ProviderAccount:
        fields: list[str] = []
        params: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            params.append(name)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if priority is not None:
            fields.append("priority = ?")
            params.append(int(priority))
        if constraints_json is not None:
            fields.append("constraints_json = ?")
            params.append(constraints_json)
        if metadata_json is not None:
            fields.append("metadata_json = ?")
            params.append(metadata_json)
        if fields:
            fields.append("updated_at = ?")
            params.append(_utc_now_iso())
            params.append(account_id)
            self._sub.connection.execute(
                f"UPDATE provider_accounts SET {', '.join(fields)} WHERE account_id = ?",
                params,
            )
            self._sub.connection.commit()
        account = self.get_provider_account(account_id)
        if account is None:
            raise KeyError(account_id)
        return account

    def delete_provider_account(self, account_id: str) -> None:
        self._sub.connection.execute(
            "DELETE FROM provider_account_offerings WHERE account_id = ?",
            (account_id,),
        )
        self._sub.connection.execute(
            "DELETE FROM provider_quota_windows WHERE account_id = ?",
            (account_id,),
        )
        self._sub.connection.execute(
            "DELETE FROM provider_secrets WHERE account_id = ?",
            (account_id,),
        )
        self._sub.connection.execute(
            "DELETE FROM provider_accounts WHERE account_id = ?",
            (account_id,),
        )
        self._sub.connection.commit()

    def set_account_offering(
        self,
        account_id: str,
        model_id: str,
        *,
        enabled: bool = True,
        metadata_json: str = "{}",
    ) -> None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_account_offerings "
            "(account_id, model_id, enabled, metadata_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(account_id, model_id) DO UPDATE SET enabled=excluded.enabled, "
            "metadata_json=excluded.metadata_json, updated_at=excluded.updated_at",
            (account_id, model_id, int(enabled), metadata_json, now, now),
        )
        self._sub.connection.commit()

    def get_account_offering_metadata(self, account_id: str, model_id: str) -> dict[str, Any]:
        row = self._sub.connection.execute(
            "SELECT metadata_json FROM provider_account_offerings WHERE account_id = ? AND model_id = ?",
            (account_id, model_id),
        ).fetchone()
        if row is None:
            return {}
        try:
            payload = json.loads(row[0] or "{}")
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def list_available_provider_models(self, provider_id: str | None = None) -> list[ProviderModel]:
        params: list[Any] = []
        provider_clause = ""
        if provider_id:
            provider_clause = "AND pm.provider = ?"
            params.append(provider_id)
        rows = self._sub.connection.execute(
            "SELECT DISTINCT pm.model_id, pm.provider, pm.model_name, pm.base_url, pm.api_key_ref, "
            "pm.context_length, pm.modalities_json, pm.cost_per_1m_input_tokens, "
            "pm.cost_per_1m_output_tokens, pm.is_free, pm.latency_tier, pm.strength_json, "
            "pm.role_preference, pm.enabled, pm.text_loop_ok, pm.last_checked_at, "
            "pm.discovery_source, pm.metadata_json, pm.created_at, pm.updated_at "
            "FROM provider_models pm "
            "JOIN provider_account_offerings pao ON pao.model_id = pm.model_id AND pao.enabled = 1 "
            "JOIN provider_accounts pa ON pa.account_id = pao.account_id AND pa.status = 'active' "
            "JOIN providers p ON p.provider_id = pa.provider_id "
            "AND p.status IN ('active', 'degraded') "
            "WHERE pm.enabled = 1 AND pm.provider = pa.provider_id "
            f"{provider_clause} ORDER BY pm.provider, pm.model_name",
            params,
        ).fetchall()
        return [_row_to_provider_model(row) for row in rows]

    def upsert_quota_window(
        self,
        *,
        account_id: str,
        quota_kind: str,
        limit_value: float | None = None,
        used_value: float | None = None,
        remaining_value: float | None = None,
        unit: str = "",
        window_started_at: str = "",
        resets_at: str = "",
        metadata_json: str = "{}",
        quota_window_id: str = "",
    ) -> ProviderQuotaWindow:
        quota_window_id = quota_window_id or f"pqw-{uuid4().hex[:12]}"
        observed_at = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_quota_windows "
            "(quota_window_id, account_id, quota_kind, limit_value, used_value, remaining_value, "
            "unit, window_started_at, resets_at, observed_at, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(quota_window_id) DO UPDATE SET limit_value=excluded.limit_value, "
            "used_value=excluded.used_value, remaining_value=excluded.remaining_value, "
            "unit=excluded.unit, window_started_at=excluded.window_started_at, "
            "resets_at=excluded.resets_at, observed_at=excluded.observed_at, "
            "metadata_json=excluded.metadata_json",
            (
                quota_window_id, account_id, quota_kind, limit_value, used_value,
                remaining_value, unit, window_started_at, resets_at, observed_at,
                metadata_json,
            ),
        )
        self._sub.connection.commit()
        return self.list_quota_windows(account_id, quota_window_id=quota_window_id)[0]

    def list_quota_windows(
        self,
        account_id: str,
        *,
        quota_window_id: str = "",
    ) -> list[ProviderQuotaWindow]:
        if quota_window_id:
            rows = self._sub.connection.execute(
                "SELECT quota_window_id, account_id, quota_kind, limit_value, used_value, "
                "remaining_value, unit, window_started_at, resets_at, observed_at, metadata_json "
                "FROM provider_quota_windows WHERE account_id = ? AND quota_window_id = ?",
                (account_id, quota_window_id),
            ).fetchall()
        else:
            rows = self._sub.connection.execute(
                "SELECT quota_window_id, account_id, quota_kind, limit_value, used_value, "
                "remaining_value, unit, window_started_at, resets_at, observed_at, metadata_json "
                "FROM provider_quota_windows WHERE account_id = ? ORDER BY observed_at DESC",
                (account_id,),
            ).fetchall()
        return [_row_to_quota_window(row) for row in rows]

    def record_provider_observation(
        self,
        *,
        provider_id: str,
        observation_kind: str,
        account_id: str = "",
        model_id: str = "",
        success: bool = True,
        latency_ms: int = 0,
        value_json: str = "{}",
    ) -> ProviderObservation:
        observation_id = f"po-{uuid4().hex[:12]}"
        observed_at = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_observations "
            "(observation_id, provider_id, account_id, model_id, observation_kind, success, "
            "latency_ms, value_json, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                observation_id, provider_id, account_id, model_id, observation_kind,
                int(success), latency_ms, value_json, observed_at,
            ),
        )
        self._sub.connection.commit()
        return self.list_provider_observations(observation_id=observation_id)[0]

    def list_provider_observations(
        self,
        *,
        provider_id: str = "",
        observation_id: str = "",
    ) -> list[ProviderObservation]:
        clauses: list[str] = []
        params: list[Any] = []
        if provider_id:
            clauses.append("provider_id = ?")
            params.append(provider_id)
        if observation_id:
            clauses.append("observation_id = ?")
            params.append(observation_id)
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self._sub.connection.execute(
            "SELECT observation_id, provider_id, account_id, model_id, observation_kind, "
            "success, latency_ms, value_json, observed_at FROM provider_observations "
            f"WHERE {where} ORDER BY observed_at DESC",
            params,
        ).fetchall()
        return [_row_to_provider_observation(row) for row in rows]

    # ---------- provider model pool ----------

    def list_provider_models(self, provider: str | None = None, *, enabled_only: bool = True) -> list[ProviderModel]:
        clauses = []
        params: list[Any] = []
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if enabled_only:
            clauses.append("enabled = 1")
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self._sub.connection.execute(
            f"SELECT model_id, provider, model_name, base_url, api_key_ref, context_length, "
            f"modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens, is_free, "
            f"latency_tier, strength_json, role_preference, enabled, text_loop_ok, last_checked_at, "
            f"discovery_source, metadata_json, created_at, updated_at "
            f"FROM provider_models WHERE {where} ORDER BY provider, model_name",
            params,
        ).fetchall()
        return [_row_to_provider_model(r) for r in rows]

    def get_provider_model(self, model_id: str) -> ProviderModel | None:
        row = self._sub.connection.execute(
            "SELECT model_id, provider, model_name, base_url, api_key_ref, context_length, "
            "modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens, is_free, "
            "latency_tier, strength_json, role_preference, enabled, text_loop_ok, last_checked_at, "
            "discovery_source, metadata_json, created_at, updated_at "
            "FROM provider_models WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        return _row_to_provider_model(row) if row else None

    def upsert_provider_model(
        self,
        *,
        model_id: str,
        provider: str,
        model_name: str,
        base_url: str = "",
        api_key_ref: str = "",
        context_length: int = 131072,
        modalities_json: str = '["text"]',
        cost_per_1m_input_tokens: float = 0.0,
        cost_per_1m_output_tokens: float = 0.0,
        is_free: int = 0,
        latency_tier: str = "medium",
        strength_json: str = '{}',
        role_preference: str = 'auto',
        enabled: int = 1,
        text_loop_ok: int = 1,
        last_checked_at: str = '',
        discovery_source: str = 'manual',
        metadata_json: str = '{}',
    ) -> ProviderModel:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_models "
            "(model_id, provider, model_name, base_url, api_key_ref, context_length, "
            "modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens, is_free, "
            "latency_tier, strength_json, role_preference, enabled, text_loop_ok, last_checked_at, "
            "discovery_source, metadata_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(model_id) DO UPDATE SET provider=excluded.provider, model_name=excluded.model_name, "
            "base_url=excluded.base_url, api_key_ref=excluded.api_key_ref, context_length=excluded.context_length, "
            "modalities_json=excluded.modalities_json, cost_per_1m_input_tokens=excluded.cost_per_1m_input_tokens, "
            "cost_per_1m_output_tokens=excluded.cost_per_1m_output_tokens, is_free=excluded.is_free, "
            "latency_tier=excluded.latency_tier, strength_json=excluded.strength_json, "
            "role_preference=excluded.role_preference, enabled=excluded.enabled, text_loop_ok=excluded.text_loop_ok, "
            "last_checked_at=excluded.last_checked_at, discovery_source=excluded.discovery_source, "
            "metadata_json=excluded.metadata_json, updated_at=excluded.updated_at",
            (model_id, provider, model_name, base_url, api_key_ref, context_length,
             modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens, is_free,
             latency_tier, strength_json, role_preference, enabled, text_loop_ok, last_checked_at,
             discovery_source, metadata_json, now, now),
        )
        self._sub.connection.commit()
        return self.get_provider_model(model_id)  # type: ignore[return-value]

    # ---------- keys CRUD ----------

    def add_key(
        self,
        *,
        provider: str,
        name: str,
        api_key: str,
        base_url: str,
        model: str = "",
        priority: int = 0,
        slot: str = "text",
    ) -> ProviderKey:
        key_id = f"pk-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO provider_keys (key_id, provider, name, api_key, base_url, model, "
            "status, priority, cooldown_until, last_used_at, last_error, last_error_at, "
            "request_count, success_count, error_count, created_at, updated_at, slot) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, '', '', '', '', 0, 0, 0, ?, ?, ?)",
            (key_id, provider, name, api_key, base_url, model, priority, now, now, slot or "text"),
        )
        self._sub.connection.execute(
            "INSERT INTO providers "
            "(provider_id, display_name, adapter_kind, status, base_url, created_at, updated_at) "
            "VALUES (?, ?, 'openai_compatible', 'active', ?, ?, ?) "
            "ON CONFLICT(provider_id) DO UPDATE SET "
            "base_url=CASE WHEN providers.base_url = '' THEN excluded.base_url ELSE providers.base_url END, "
            "updated_at=excluded.updated_at",
            (provider, provider, base_url, now, now),
        )
        self._sub.connection.execute(
            "INSERT INTO provider_accounts "
            "(account_id, provider_id, name, secret_ref, secret_masked, legacy_key_id, status, priority, "
            "constraints_json, metadata_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'active', ?, '{}', '{}', ?, ?) "
            "ON CONFLICT(account_id) DO UPDATE SET provider_id=excluded.provider_id, "
            "name=excluded.name, status=excluded.status, priority=excluded.priority, "
            "secret_masked=excluded.secret_masked, updated_at=excluded.updated_at",
            (
                key_id, provider, name, f"legacy-provider-key:{key_id}", mask_secret(api_key), key_id,
                priority, now, now,
            ),
        )
        self._sub.connection.commit()
        return self.get_key(key_id)  # type: ignore[return-value]

    def get_key(self, key_id: str) -> ProviderKey | None:
        row = self._sub.connection.execute(
            "SELECT key_id, provider, name, api_key, base_url, model, status, priority, "
            "cooldown_until, last_used_at, last_error, last_error_at, request_count, "
            "success_count, error_count, created_at, updated_at, "
            "account_id, balance_json, balance_checked_at, "
            "COALESCE(slot, 'text') "
            "FROM provider_keys WHERE key_id = ?",
            (key_id,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_key(row)

    def list_keys(self, provider: str | None = None) -> list[ProviderKey]:
        if provider:
            rows = self._sub.connection.execute(
                "SELECT key_id, provider, name, api_key, base_url, model, status, priority, "
                "cooldown_until, last_used_at, last_error, last_error_at, request_count, "
                "success_count, error_count, created_at, updated_at, "
                "account_id, balance_json, balance_checked_at, "
                "COALESCE(slot, 'text') "
                "FROM provider_keys WHERE provider = ? ORDER BY priority DESC, created_at ASC",
                (provider,),
            ).fetchall()
        else:
            rows = self._sub.connection.execute(
                "SELECT key_id, provider, name, api_key, base_url, model, status, priority, "
                "cooldown_until, last_used_at, last_error, last_error_at, request_count, "
                "success_count, error_count, created_at, updated_at, "
                "account_id, balance_json, balance_checked_at, "
                "COALESCE(slot, 'text') "
                "FROM provider_keys ORDER BY provider, priority DESC, created_at ASC"
            ).fetchall()
        return [_row_to_key(r) for r in rows]

    def update_status(self, key_id: str, status: KeyStatus, *, last_error: str = "", cooldown_seconds: int = 0) -> None:
        now = datetime.now(timezone.utc)
        cooldown_until = ""
        if cooldown_seconds > 0:
            cooldown_until = (now + timedelta(seconds=cooldown_seconds)).isoformat()
        self._sub.connection.execute(
            "UPDATE provider_keys SET status = ?, cooldown_until = ?, "
            "last_error = COALESCE(NULLIF(?, ''), last_error), "
            "last_error_at = CASE WHEN ? != '' THEN ? ELSE last_error_at END, "
            "updated_at = ? WHERE key_id = ?",
            (status.value, cooldown_until, last_error, last_error, now.isoformat(), now.isoformat(), key_id),
        )
        self._sub.connection.execute(
            "UPDATE provider_accounts SET status = ?, updated_at = ? WHERE legacy_key_id = ?",
            (status.value, now.isoformat(), key_id),
        )
        self._sub.connection.commit()

    def sync_legacy_account_statuses_from_keys(self, provider: str | None = None) -> int:
        """Repair mirrored account status for legacy provider_keys rows."""
        params: list[Any] = []
        where = "WHERE legacy_key_id != ''"
        if provider:
            where += " AND provider_id = ?"
            params.append(provider)
        now = _utc_now_iso()
        cur = self._sub.connection.execute(
            "UPDATE provider_accounts "
            "SET status = (SELECT status FROM provider_keys WHERE provider_keys.key_id = provider_accounts.legacy_key_id), "
            "updated_at = ? "
            f"{where} "
            "AND EXISTS (SELECT 1 FROM provider_keys WHERE provider_keys.key_id = provider_accounts.legacy_key_id) "
            "AND status != (SELECT status FROM provider_keys WHERE provider_keys.key_id = provider_accounts.legacy_key_id)",
            (now, *params),
        )
        self._sub.connection.commit()
        return int(cur.rowcount or 0)

    def set_status(self, key_id: str, status: KeyStatus, *, last_error: str = "", cooldown_seconds: int = 0) -> None:
        """Compatibility alias used by provider management tools."""
        self.update_status(
            key_id,
            status,
            last_error=last_error,
            cooldown_seconds=cooldown_seconds,
        )

    def delete_key(self, key_id: str) -> None:
        self._sub.connection.execute("DELETE FROM provider_keys WHERE key_id = ?", (key_id,))
        self._sub.connection.commit()

    def update_metadata(
        self,
        key_id: str,
        *,
        name: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        priority: int | None = None,
        slot: str | None = None,
    ) -> None:
        fields = []
        params: list[Any] = []
        if name is not None:
            fields.append("name = ?"); params.append(name)
        if base_url is not None:
            fields.append("base_url = ?"); params.append(base_url)
        if model is not None:
            fields.append("model = ?"); params.append(model)
        if priority is not None:
            fields.append("priority = ?"); params.append(int(priority))
        if slot is not None:
            fields.append("slot = ?"); params.append(slot)
        if not fields:
            return
        fields.append("updated_at = ?"); params.append(_utc_now_iso())
        params.append(key_id)
        self._sub.connection.execute(
            f"UPDATE provider_keys SET {', '.join(fields)} WHERE key_id = ?",
            params,
        )
        self._sub.connection.commit()

    def update_balance(self, key_id: str, *, account_id: str, balance: dict) -> None:
        """Persist a fresh balance snapshot for a key."""
        import json as _json
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE provider_keys SET account_id = ?, balance_json = ?, "
            "balance_checked_at = ?, updated_at = ? WHERE key_id = ?",
            (account_id or "", _json.dumps(balance, ensure_ascii=False), now, now, key_id),
        )
        self._sub.connection.commit()

    # ---------- rotation ----------

    async def acquire(self, provider: str) -> ProviderKey | None:
        """Pick the best eligible key for `provider`.

        Strategy: highest priority among eligible, then least-recently-used.
        Returns None if all keys are banned/disabled/cooldown.

        2026-06-02: slot filtering removed per Ivan's directive. All keys
        are ``slot=text``. Model selection is done by the caller (Sonya
        picks model via purpose hint or explicit _model kwarg).
        """
        async with self._lock:
            all_keys = [k for k in self.list_keys(provider) if k.is_eligible()]
            if not all_keys:
                return None
            # Sort: priority desc, then last_used_at asc (LRU)
            all_keys.sort(key=lambda k: (-k.priority, k.last_used_at or ""))
            chosen = all_keys[0]
            return self._touch_acquired_key_locked(chosen)

    async def acquire_for_model(self, provider: str, model_id: str) -> ProviderKey | None:
        """Pick an eligible legacy key whose mirrored account offers model_id."""
        async with self._lock:
            rows = self._sub.connection.execute(
                "SELECT DISTINCT pa.legacy_key_id "
                "FROM provider_accounts pa "
                "JOIN provider_account_offerings pao ON pao.account_id = pa.account_id "
                "WHERE pa.provider_id = ? AND pa.status = 'active' "
                "AND pa.legacy_key_id != '' AND pao.model_id = ? AND pao.enabled = 1",
                (provider, model_id),
            ).fetchall()
            eligible_key_ids = {row[0] for row in rows if row[0]}
            if not eligible_key_ids:
                return None
            all_keys = [
                key for key in self.list_keys(provider)
                if key.key_id in eligible_key_ids and key.is_eligible()
            ]
            if not all_keys:
                return None
            all_keys.sort(key=lambda k: (-k.priority, k.last_used_at or ""))
            return self._touch_acquired_key_locked(all_keys[0])

    async def acquire_strict(self, provider: str) -> ProviderKey | None:
        """Like acquire() — pick the best eligible key for `provider`.

        2026-06-02: slot parameter removed. All keys are slot=text.
        This is now effectively the same as acquire() but kept for
        backward compatibility with existing callers.
        """
        return await self.acquire(provider)

    async def acquire_by_slot(self, slot: str) -> ProviderKey | None:
        """Pick the best eligible key with the given slot, across ALL providers.

        Used for vision/voice/etc where the key might be on a different provider
        than the active text provider.
        """
        async with self._lock:
            all_keys = [k for k in self.list_keys() if k.is_eligible()]
            slot_keys = [k for k in all_keys if slot in k.slot.split(",")]
            if not slot_keys:
                return None
            slot_keys.sort(key=lambda k: (-k.priority, k.last_used_at or ""))
            chosen = slot_keys[0]
            return self._touch_acquired_key_locked(chosen)

    def _touch_acquired_key_locked(self, chosen: ProviderKey) -> ProviderKey | None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE provider_keys SET last_used_at = ?, request_count = request_count + 1, "
            "updated_at = ? "
            "WHERE key_id = ?",
            (now, now, chosen.key_id),
        )
        if chosen.status is KeyStatus.COOLDOWN:
            self._sub.connection.execute(
                "UPDATE provider_keys SET status = 'active', cooldown_until = '' WHERE key_id = ?",
                (chosen.key_id,),
            )
        self._sub.connection.execute(
            "UPDATE provider_accounts SET status = 'active', updated_at = ? WHERE legacy_key_id = ?",
            (now, chosen.key_id),
        )
        self._sub.connection.commit()
        return self.get_key(chosen.key_id)

    async def report_success(self, key_id: str) -> None:
        async with self._lock:
            self._sub.connection.execute(
                "UPDATE provider_keys SET success_count = success_count + 1, updated_at = ? WHERE key_id = ?",
                (_utc_now_iso(), key_id),
            )
            self._sub.connection.commit()

    async def report_failure(
        self,
        key_id: str,
        *,
        kind: str,            # rate_limit | server_error | auth_error | other
        error_message: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        async with self._lock:
            cooldown = 0
            new_status: KeyStatus | None = None
            if kind == "rate_limit":
                cooldown = retry_after_seconds or 60
                new_status = KeyStatus.COOLDOWN
            elif kind == "server_error":
                cooldown = 30
                new_status = KeyStatus.COOLDOWN
            elif kind == "auth_error":
                new_status = KeyStatus.BANNED
            elif kind == "config_error":
                cooldown = 3600
                new_status = KeyStatus.COOLDOWN
            else:
                cooldown = 15
                new_status = KeyStatus.COOLDOWN

            self._sub.connection.execute(
                "UPDATE provider_keys SET error_count = error_count + 1, "
                "last_error = ?, last_error_at = ?, updated_at = ? WHERE key_id = ?",
                (error_message[:500], _utc_now_iso(), _utc_now_iso(), key_id),
            )
            self._sub.connection.commit()
            if new_status is not None:
                self.update_status(key_id, new_status, last_error=error_message[:500], cooldown_seconds=cooldown)


def _row_to_key(row: Iterable[Any]) -> ProviderKey:
    r = list(row)
    return ProviderKey(
        key_id=r[0], provider=r[1], name=r[2], api_key=r[3], base_url=r[4],
        model=r[5], status=KeyStatus(r[6]), priority=int(r[7] or 0),
        cooldown_until=r[8] or "", last_used_at=r[9] or "",
        last_error=r[10] or "", last_error_at=r[11] or "",
        request_count=int(r[12] or 0), success_count=int(r[13] or 0),
        error_count=int(r[14] or 0), created_at=r[15], updated_at=r[16],
        account_id=(r[17] if len(r) > 17 else "") or "",
        balance_json=(r[18] if len(r) > 18 else "{}") or "{}",
        balance_checked_at=(r[19] if len(r) > 19 else "") or "",
        slot=(r[20] if len(r) > 20 else "text") or "text",
    )


def _row_to_provider(row: Iterable[Any]) -> Provider:
    r = list(row)
    return Provider(
        provider_id=r[0],
        display_name=r[1],
        adapter_kind=r[2],
        status=r[3],
        base_url=r[4],
        capabilities_json=r[5],
        constraints_json=r[6],
        metadata_json=r[7],
        created_at=r[8],
        updated_at=r[9],
    )


def _row_to_provider_account(row: Iterable[Any]) -> ProviderAccount:
    r = list(row)
    return ProviderAccount(
        account_id=r[0],
        provider_id=r[1],
        name=r[2],
        secret_ref=r[3],
        masked_secret=r[4],
        legacy_key_id=r[5],
        status=r[6],
        priority=int(r[7] or 0),
        constraints_json=r[8],
        metadata_json=r[9],
        created_at=r[10],
        updated_at=r[11],
    )


def _row_to_quota_window(row: Iterable[Any]) -> ProviderQuotaWindow:
    r = list(row)
    return ProviderQuotaWindow(
        quota_window_id=r[0],
        account_id=r[1],
        quota_kind=r[2],
        limit_value=float(r[3]) if r[3] is not None else None,
        used_value=float(r[4]) if r[4] is not None else None,
        remaining_value=float(r[5]) if r[5] is not None else None,
        unit=r[6],
        window_started_at=r[7],
        resets_at=r[8],
        observed_at=r[9],
        metadata_json=r[10],
    )


def _row_to_provider_observation(row: Iterable[Any]) -> ProviderObservation:
    r = list(row)
    return ProviderObservation(
        observation_id=r[0],
        provider_id=r[1],
        account_id=r[2],
        model_id=r[3],
        observation_kind=r[4],
        success=int(r[5] or 0),
        latency_ms=int(r[6] or 0),
        value_json=r[7],
        observed_at=r[8],
    )


def _row_to_provider_model(row: Iterable[Any]) -> ProviderModel:
    r = list(row)
    return ProviderModel(
        model_id=r[0],
        provider=r[1],
        model_name=r[2],
        base_url=r[3],
        api_key_ref=r[4],
        context_length=int(r[5] or 131072),
        modalities_json=r[6],
        cost_per_1m_input_tokens=float(r[7] or 0.0),
        cost_per_1m_output_tokens=float(r[8] or 0.0),
        is_free=int(r[9] or 0),
        latency_tier=r[10] or "medium",
        strength_json=r[11] or '{}',
        role_preference=r[12] or 'auto',
        enabled=int(r[13] or 0),
        text_loop_ok=int(r[14] if len(r) > 14 and r[14] is not None else 1),
        last_checked_at=r[15] if len(r) > 15 else '',
        discovery_source=r[16] if len(r) > 16 else 'manual',
        metadata_json=r[17] if len(r) > 17 else '{}',
        created_at=r[18] if len(r) > 18 else '',
        updated_at=r[19] if len(r) > 19 else '',
    )
