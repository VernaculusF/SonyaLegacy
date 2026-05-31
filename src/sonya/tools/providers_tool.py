"""ProvidersTool — она управляет своим LLM-pool сама.

Соня видит и управляет своими провайдерами через `providers.*`. Может:
- посмотреть список ключей и их состояние (`providers.list`)
- проверить баланс (`providers.balance`)
- получить health-отчёт ("сколько осталось работать", `providers.health_report`)
- отключить сдохший ключ (`providers.disable_key`)
- добавить новый ключ который у неё есть в руках (`providers.add_key`)
- активировать ранее отключённый (`providers.enable_key`)
- сменить активного провайдера (`providers.set_active`)

Регистрация **новых аккаунтов** на free tier — через `BrowserTool` +
`plugins.create` для скрипта-регистратора. Это выходит за рамки этого тула.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sonya.providers.keystore import KeyStatus, KeyStore, ProviderSettings
from sonya.state.substrate import Substrate


def _key_balance_amount(k) -> float | None:
    """Extract a numeric balance amount from a ProviderKey snapshot.

    Returns None if no snapshot was ever taken or the snapshot has no
    money-shaped field. ProviderKey.balance() returns the decoded JSON
    snapshot dict; common keys are 'balance' / 'usd' / 'remaining' /
    'credits'. For Fireworks the snapshot has a nested
    `monthly_spend_usd: {usage, limit, remaining}` dict — check that too.
    Anything that can be cast to float wins.
    """
    bal = k.balance() if callable(getattr(k, "balance", None)) else (k.balance or {})
    if not isinstance(bal, dict) or not bal:
        return None
    # Top-level money fields
    for field in ("balance", "usd", "remaining", "credits"):
        v = bal.get(field)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    # Nested fireworks shape: monthly_spend_usd.{remaining, limit, usage}
    spend = bal.get("monthly_spend_usd")
    if isinstance(spend, dict):
        # Prefer 'remaining' (limit - usage). Fall back to limit.
        for field in ("remaining", "limit"):
            v = spend.get(field)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def _fmt_key(k) -> str:
    """One-line summary of a provider key."""
    bits = [
        f"{k.key_id} [{k.provider}]",
        f"name={k.name!r}",
        f"status={k.status.value}",
        f"prio={k.priority}",
        f"slot={k.slot or '-'}",
        f"req={k.request_count}/err={k.error_count}",
    ]
    amount = _key_balance_amount(k)
    if amount is not None:
        bits.append(f"balance=${amount:.2f}")
    if k.cooldown_until:
        bits.append(f"cooldown_until={k.cooldown_until[:19]}")
    return " ".join(bits)


class ProvidersTool:
    """Agent-facing wrapper. All methods return strings."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._store = KeyStore(substrate)

    # ---------- read ----------

    def list_keys(self, _arg: str = "") -> str:
        """List all keys with status / balance / counters."""
        keys = self._store.list_keys()
        if not keys:
            return "(нет ключей в pool)"
        lines = [f"{len(keys)} ключей:"]
        for k in keys:
            lines.append(f"  {_fmt_key(k)}")
        return "\n".join(lines)

    def settings(self, _arg: str = "") -> str:
        s = self._store.get_settings()
        return (
            f"active_provider: {s.active_provider}\n"
            f"default_model:   {s.default_model}\n"
            f"default_base_url:{s.default_base_url}\n"
            f"updated_at:      {s.updated_at}"
        )

    def balance(self, _arg: str = "") -> str:
        """Sum balance across active keys, by provider."""
        keys = self._store.list_keys()
        active = [k for k in keys if k.status == KeyStatus.ACTIVE]
        if not active:
            return "(нет активных ключей)"
        by_provider: dict[str, list[float]] = {}
        keys_with_balance = 0
        for k in active:
            amount = _key_balance_amount(k)
            if amount is None:
                continue
            keys_with_balance += 1
            by_provider.setdefault(k.provider, []).append(amount)
        if not by_provider:
            return (
                f"{len(active)} active keys, balance unknown for all "
                "(refresh via providers.balance/refresh on admin or в течение "
                "часа watchdog подтянет)"
            )
        lines = [f"Balance ({keys_with_balance}/{len(active)} active keys reported):"]
        total = 0.0
        for prov, values in by_provider.items():
            s = sum(values)
            total += s
            lines.append(f"  {prov}: ${s:.2f} ({len(values)} keys)")
        lines.append(f"  total: ${total:.2f}")
        return "\n".join(lines)

    def health_report(self, _arg: str = "") -> str:
        """Synthesised view: are we ok, in trouble, or critical?

        Heuristic:
          - 0 active keys                 → CRITICAL (без LLM нет работы)
          - balance < $1 (когда известен) → CRITICAL
          - balance < $5                  → WARNING
          - balance >= $5                 → OK
        """
        keys = self._store.list_keys()
        active = [k for k in keys if k.status == KeyStatus.ACTIVE]
        banned = [k for k in keys if k.status == KeyStatus.BANNED]
        disabled = [k for k in keys if k.status == KeyStatus.DISABLED]

        if not active:
            return (
                "[CRITICAL] 0 активных ключей.\n"
                f"  banned={len(banned)} disabled={len(disabled)}\n"
                "  Без работающего LLM ничего не сделать. Зарегистрировать новый "
                "аккаунт у текущего провайдера / переключиться на резервного / "
                "уведомить Ивана."
            )

        balances = [
            amount for amount in (_key_balance_amount(k) for k in active)
            if amount is not None
        ]
        if not balances:
            return (
                f"[UNKNOWN] {len(active)} active keys, balance не известен "
                "(никто не запросил refresh). Запусти "
                "`providers.balance/refresh` через admin или подожди час."
            )
        total = sum(balances)
        if total < 1.0:
            level = "CRITICAL"
        elif total < 5.0:
            level = "WARNING"
        else:
            level = "OK"
        return (
            f"[{level}] суммарный баланс ${total:.2f} по {len(balances)}/"
            f"{len(active)} active keys.\n"
            "  banned={banned} disabled={disabled}\n"
            "  Если CRITICAL — пора регать новый аккаунт или просить Ивана."
        ).format(banned=len(banned), disabled=len(disabled))

    # ---------- write ----------

    def disable_key(self, arg: str) -> str:
        key_id = arg.strip()
        if not key_id:
            return "[ERROR] providers.disable_key: укажи key_id"
        try:
            self._store.set_status(key_id, KeyStatus.DISABLED)
            return f"[OK] {key_id} → disabled"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def enable_key(self, arg: str) -> str:
        key_id = arg.strip()
        if not key_id:
            return "[ERROR] providers.enable_key: укажи key_id"
        try:
            self._store.set_status(key_id, KeyStatus.ACTIVE)
            return f"[OK] {key_id} → active"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def add_key(self, arg: str) -> str:
        """Add a new provider key.

        JSON: {provider, name, api_key, base_url?, model?, priority?, slot?}.
        Returns the new key_id.
        """
        try:
            data = json.loads(arg or "{}")
        except json.JSONDecodeError as e:
            return f"[ERROR] providers.add_key: invalid JSON ({e})"
        provider = str(data.get("provider", "")).strip()
        name = str(data.get("name", "")).strip()
        api_key = str(data.get("api_key", "")).strip()
        if not (provider and name and api_key):
            return "[ERROR] providers.add_key: provider, name, api_key обязательны"
        base_url = str(data.get("base_url", "")).strip()
        model = str(data.get("model", "")).strip()
        priority = int(data.get("priority", 0) or 0)
        slot = str(data.get("slot", "text")).strip() or "text"
        try:
            key_id = self._store.add_key(
                provider=provider,
                name=name,
                api_key=api_key,
                base_url=base_url,
                model=model,
                priority=priority,
                slot=slot,
            )
            return f"[OK] added key_id={key_id} ({provider}/{name}, slot={slot})"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def set_active(self, arg: str) -> str:
        """Switch active provider. arg = provider_name (e.g. 'fireworks')."""
        provider = (arg or "").strip()
        if not provider:
            return "[ERROR] providers.set_active: укажи имя провайдера"
        try:
            self._store.update_settings(active_provider=provider)
            return f"[OK] active_provider → {provider}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"
