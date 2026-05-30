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

    async def acquire(self, provider: str, slot: str = "text") -> ProviderKey | None:
        """Pick the best eligible key for `provider` whose slots include `slot`.

        Strategy: highest priority among eligible, then least-recently-used.
        Fallback: if no keys match the requested slot, try any eligible key
        for that provider (universal fallback).
        Returns None if all keys are banned/disabled/cooldown.
        """
        async with self._lock:
            all_keys = [k for k in self.list_keys(provider) if k.is_eligible()]
            # Filter to keys whose slot list includes the requested slot
            slot_keys = [k for k in all_keys if slot in k.slot.split(",")]
            keys = slot_keys if slot_keys else all_keys
            if not keys:
                return None
            # Sort: priority desc, then last_used_at asc (LRU)
            keys.sort(key=lambda k: (-k.priority, k.last_used_at or ""))
            chosen = keys[0]
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

    async def acquire_strict(self, provider: str, slot: str) -> ProviderKey | None:
        """Like acquire() but DOES NOT fall back to non-matching slots.

        Used by the LLM provider to enforce slot routing — for example when
        ``active_session`` requests ``text-fast`` we'd rather try a
        different provider that has a fast key than burn a deep key on a
        latency-sensitive turn.
        """
        async with self._lock:
            all_keys = [k for k in self.list_keys(provider) if k.is_eligible()]
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
