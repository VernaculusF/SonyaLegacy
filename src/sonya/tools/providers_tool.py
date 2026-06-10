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


def _json_arg(value) -> str:
    if isinstance(value, str):
        return value or "{}"
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


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

    def list_providers(self, _arg: str = "") -> str:
        providers = self._store.list_providers()
        if not providers:
            return "(no providers registered)"
        accounts = self._store.list_provider_accounts()
        models = self._store.list_available_provider_models()
        account_counts: dict[str, int] = {}
        model_counts: dict[str, int] = {}
        for account in accounts:
            account_counts[account.provider_id] = account_counts.get(account.provider_id, 0) + 1
        for model in models:
            model_counts[model.provider] = model_counts.get(model.provider, 0) + 1
        lines = [f"{len(providers)} providers:"]
        for provider in providers:
            lines.append(
                f"  {provider.provider_id} status={provider.status} adapter={provider.adapter_kind} "
                f"accounts={account_counts.get(provider.provider_id, 0)} "
                f"available_models={model_counts.get(provider.provider_id, 0)} "
                f"base_url={provider.base_url or '-'}"
            )
        return "\n".join(lines)

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

    def provider_health(self, provider: str = "") -> str:
        provider = (provider or "").strip()
        if not provider:
            return "[ERROR] providers.health: provider_id required"
        if self._store.get_provider(provider) is None:
            return f"[ERROR] unknown provider: {provider}"
        accounts = self._store.list_provider_accounts(provider)
        available = self._store.list_available_provider_models(provider)
        observations = self._store.list_provider_observations(provider_id=provider)
        lines = [
            f"{provider}: accounts={len(accounts)} available_models={len(available)}",
        ]
        for account in accounts:
            lines.append(f"  account {account.account_id} name={account.name} status={account.status} prio={account.priority}")
            for quota in self._store.list_quota_windows(account.account_id)[:5]:
                remaining = "" if quota.remaining_value is None else f" remaining={quota.remaining_value:g}"
                limit = "" if quota.limit_value is None else f" limit={quota.limit_value:g}"
                lines.append(
                    f"    quota {quota.quota_kind}{remaining}{limit} unit={quota.unit or '-'} resets={quota.resets_at or '-'}"
                )
        for observation in observations[:5]:
            outcome = "ok" if observation.success else "fail"
            lines.append(
                f"  {observation.observation_kind} {outcome} latency_ms={observation.latency_ms} "
                f"model={observation.model_id or '-'}"
            )
        return "\n".join(lines)

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

    def list_models(self, provider: str = "") -> str:
        """List cached/discovered provider model pool data from substrate."""
        provider = (provider or "").strip().lower()

        available = self._store.list_available_provider_models(provider or None)
        cached = self._store.list_provider_models(provider or None, enabled_only=True)
        by_id = {model.model_id: model for model in cached}
        for model in available:
            by_id[model.model_id] = model

        if not by_id:
            suffix = f" for {provider}" if provider else ""
            return f"(no cached provider models{suffix}; run provider discovery refresh)"

        substrate_lines: list[str] = []
        current_provider = ""
        available_ids = {model.model_id for model in available}
        for model in sorted(by_id.values(), key=lambda item: (item.provider, item.model_name, item.model_id)):
            if model.provider != current_provider:
                current_provider = model.provider
                substrate_lines.append(f"--- {current_provider} ---")
            if model.is_free:
                price = "free"
            else:
                price = f"${model.cost_per_1m_input_tokens:g}/${model.cost_per_1m_output_tokens:g}/M"
            availability = "available" if model.model_id in available_ids else "cached"
            substrate_lines.append(
                f"{model.provider} | {model.model_id} | ctx={model.context_length} | "
                f"{price} | {availability} | source={model.discovery_source}"
            )
        return "\n".join(substrate_lines)

    def add_key(self, arg: str) -> str:
        """Reject the legacy plaintext-key tool path."""
        return (
            "[ERROR] providers.add_key: legacy plaintext key ingestion is disabled; "
            "create a provider account and use the protected secret-ingestion admin action"
        )

    def upsert_provider(self, arg: str) -> str:
        try:
            data = json.loads(arg or "{}")
        except json.JSONDecodeError as e:
            return f"[ERROR] providers.upsert_provider: invalid JSON ({e})"
        provider_id = str(data.get("provider_id") or data.get("provider") or "").strip().lower()
        display_name = str(data.get("display_name") or provider_id).strip()
        adapter_kind = str(data.get("adapter_kind") or "openai_compatible").strip()
        if not provider_id:
            return "[ERROR] providers.upsert_provider: provider_id required"
        status = str(data.get("status") or "active").strip().lower()
        base_url = str(data.get("base_url") or "").strip()
        capabilities = data.get("capabilities_json", data.get("capabilities", {}))
        constraints = data.get("constraints_json", data.get("constraints", {}))
        metadata = data.get("metadata_json", data.get("metadata", {}))
        try:
            provider = self._store.upsert_provider(
                provider_id=provider_id,
                display_name=display_name,
                adapter_kind=adapter_kind,
                status=status,
                base_url=base_url,
                capabilities_json=_json_arg(capabilities),
                constraints_json=_json_arg(constraints),
                metadata_json=_json_arg(metadata),
            )
            return f"[OK] provider_id={provider.provider_id} status={provider.status} adapter={provider.adapter_kind}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def delete_provider(self, arg: str) -> str:
        provider_id = (arg or "").strip().lower()
        if not provider_id:
            return "[ERROR] providers.delete_provider: provider_id required"
        if self._store.get_provider(provider_id) is None:
            return f"[ERROR] unknown provider: {provider_id}"
        accounts = self._store.list_provider_accounts(provider_id)
        if accounts:
            return f"[ERROR] provider {provider_id} accounts still exist: {len(accounts)}"
        try:
            self._store.delete_provider(provider_id)
            return f"[OK] provider {provider_id} deleted"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def add_account(self, arg: str) -> str:
        try:
            data = json.loads(arg or "{}")
        except json.JSONDecodeError as e:
            return f"[ERROR] providers.add_account: invalid JSON ({e})"
        provider_id = str(data.get("provider_id") or data.get("provider") or "").strip().lower()
        name = str(data.get("name") or "").strip()
        if not provider_id or not name:
            return "[ERROR] providers.add_account: provider_id and name required"
        if data.get("secret_value") or data.get("api_key"):
            return (
                "[ERROR] providers.add_account: raw credentials require the protected "
                "secret-ingestion admin action"
            )
        secret_ref = str(data.get("secret_ref") or "").strip()
        constraints = data.get("constraints_json", data.get("constraints", {}))
        metadata = data.get("metadata_json", data.get("metadata", {}))
        try:
            account = self._store.add_provider_account(
                provider_id=provider_id,
                name=name,
                secret_ref=secret_ref,
                status=str(data.get("status") or "active").strip().lower(),
                priority=int(data.get("priority") or 0),
                constraints_json=_json_arg(constraints),
                metadata_json=_json_arg(metadata),
            )
            return (
                f"[OK] account_id={account.account_id} provider={account.provider_id} "
                f"name={account.name} status={account.status} secret={account.masked_secret or account.secret_ref}"
            )
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def migrate_legacy_secret(self, arg: str) -> str:
        account_id = (arg or "").strip()
        if not account_id:
            return "[ERROR] providers.migrate_legacy_secret: account_id required"
        try:
            account = self._store.migrate_legacy_account_secret(account_id)
            return (
                f"[OK] account_id={account.account_id} provider={account.provider_id} "
                f"secret_ref={account.secret_ref} secret_masked={account.masked_secret}"
            )
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def update_account(self, arg: str) -> str:
        try:
            data = json.loads(arg or "{}")
        except json.JSONDecodeError as e:
            return f"[ERROR] providers.update_account: invalid JSON ({e})"
        account_id = str(data.get("account_id") or "").strip()
        if not account_id:
            return "[ERROR] providers.update_account: account_id required"
        try:
            account = self._store.update_provider_account(
                account_id,
                name=str(data["name"]).strip() if "name" in data else None,
                status=str(data["status"]).strip().lower() if "status" in data else None,
                priority=int(data["priority"]) if "priority" in data else None,
                constraints_json=_json_arg(data["constraints"]) if "constraints" in data else data.get("constraints_json"),
                metadata_json=_json_arg(data["metadata"]) if "metadata" in data else data.get("metadata_json"),
            )
            return f"[OK] account_id={account.account_id} provider={account.provider_id} status={account.status}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def delete_account(self, arg: str) -> str:
        account_id = (arg or "").strip()
        if not account_id:
            return "[ERROR] providers.delete_account: account_id required"
        if self._store.get_provider_account(account_id) is None:
            return f"[ERROR] unknown account: {account_id}"
        try:
            self._store.delete_provider_account(account_id)
            return f"[OK] account {account_id} deleted"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {e}"

    def set_offering(self, arg: str) -> str:
        try:
            data = json.loads(arg or "{}")
        except json.JSONDecodeError as e:
            return f"[ERROR] providers.set_offering: invalid JSON ({e})"
        account_id = str(data.get("account_id") or "").strip()
        model_id = str(data.get("model_id") or data.get("model") or "").strip()
        if not account_id or not model_id:
            return "[ERROR] providers.set_offering: account_id and model_id required"
        try:
            enabled = bool(data.get("enabled", True))
            metadata = data.get("metadata_json", data.get("metadata", {}))
            self._store.set_account_offering(
                account_id,
                model_id,
                enabled=enabled,
                metadata_json=_json_arg(metadata),
            )
            state = "enabled" if enabled else "disabled"
            return f"[OK] offering {account_id} -> {model_id} {state}"
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
