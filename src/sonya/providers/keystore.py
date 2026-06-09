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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

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

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._lock = asyncio.Lock()

    # ---------- settings ----------

    def get_settings(self) -> ProviderSettings:
        row = self._sub.connection.execute(
            "SELECT active_provider, default_model, default_base_url, updated_at "
            "FROM provider_settings WHERE id = 1"
        ).fetchone()
        if row is None:
            return ProviderSettings("fireworks", "accounts/fireworks/models/minimax-m2p7",
                                    "https://api.fireworks.ai/inference/v1", "")
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
            f"latency_tier, strength_json, role_preference, enabled, last_checked_at, "
            f"discovery_source, metadata_json, created_at, updated_at "
            f"FROM provider_models WHERE {where} ORDER BY provider, model_name",
            params,
        ).fetchall()
        return [_row_to_provider_model(r) for r in rows]

    def get_provider_model(self, model_id: str) -> ProviderModel | None:
        row = self._sub.connection.execute(
            "SELECT model_id, provider, model_name, base_url, api_key_ref, context_length, "
            "modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens, is_free, "
            "latency_tier, strength_json, role_preference, enabled, last_checked_at, "
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
        self._sub.connection.commit()

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
            now = _utc_now_iso()
            self._sub.connection.execute(
                "UPDATE provider_keys SET last_used_at = ?, request_count = request_count + 1, "
                "updated_at = ? "
                "WHERE key_id = ?",
                (now, now, chosen.key_id),
            )
            # If it was cooldown but expired, flip back to active
            if chosen.status is KeyStatus.COOLDOWN:
                self._sub.connection.execute(
                    "UPDATE provider_keys SET status = 'active', cooldown_until = '' WHERE key_id = ?",
                    (chosen.key_id,),
                )
            self._sub.connection.commit()
            return self.get_key(chosen.key_id)

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
