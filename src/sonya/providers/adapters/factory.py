from __future__ import annotations

from sonya.providers.adapters.base import ProviderAdapter
from sonya.providers.adapters.google_native import GoogleNativeAdapter
from sonya.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from sonya.providers.keystore import KeyStore


def build_lifecycle_adapter(store: KeyStore, provider_id: str) -> ProviderAdapter:
    """Build a lifecycle adapter from substrate-owned provider/account state."""
    provider = store.get_provider(provider_id)
    if provider is None:
        raise KeyError(provider_id)

    accounts = [
        account
        for account in store.list_provider_accounts(provider_id)
        if account.status == "active"
    ]
    if not accounts:
        raise RuntimeError(f"provider {provider_id!r} has no active accounts")

    account = sorted(accounts, key=lambda item: (item.priority, item.created_at))[0]
    secret = store.resolve_account_secret(account.account_id)

    if provider.adapter_kind == "google_native":
        return GoogleNativeAdapter(
            provider_id=provider.provider_id,
            api_key=secret,
            base_url=provider.base_url or "https://generativelanguage.googleapis.com/v1beta",
        )
    if provider.adapter_kind in ("openai_compatible", "web_proxy"):
        return OpenAICompatibleAdapter(
            provider_id=provider.provider_id,
            base_url=provider.base_url,
            api_key=secret,
        )
    raise ValueError(f"unsupported lifecycle adapter kind: {provider.adapter_kind}")


def build_lifecycle_adapter_for_account(
    store: KeyStore,
    provider_id: str,
    account_id: str,
) -> ProviderAdapter:
    """Build a lifecycle adapter for one concrete provider account."""
    provider = store.get_provider(provider_id)
    if provider is None:
        raise KeyError(provider_id)
    account = store.get_provider_account(account_id)
    if account is None or account.provider_id != provider_id:
        raise KeyError(account_id)
    if account.status != "active":
        raise RuntimeError(f"provider account {account_id!r} is not active")

    secret = store.resolve_account_secret(account.account_id)

    if provider.adapter_kind == "google_native":
        return GoogleNativeAdapter(
            provider_id=provider.provider_id,
            api_key=secret,
            base_url=provider.base_url or "https://generativelanguage.googleapis.com/v1beta",
        )
    if provider.adapter_kind in ("openai_compatible", "web_proxy"):
        return OpenAICompatibleAdapter(
            provider_id=provider.provider_id,
            base_url=provider.base_url,
            api_key=secret,
        )
    raise ValueError(f"unsupported lifecycle adapter kind: {provider.adapter_kind}")
