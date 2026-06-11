from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from sonya.providers.keystore import KeyStatus, KeyStore
from sonya.state.substrate import Substrate


def test_provider_can_exist_without_credentials(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        store = KeyStore(sub)
        provider = store.upsert_provider(
            provider_id="nous",
            display_name="Nous Research",
            adapter_kind="openai_compatible",
            base_url="https://inference-api.nousresearch.com/v1",
        )

        assert provider.provider_id == "nous"
        assert provider.adapter_kind == "openai_compatible"
        assert store.list_provider_accounts("nous") == []
    finally:
        sub.close()


def test_legacy_key_is_mirrored_into_provider_account(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        store = KeyStore(sub)
        key = store.add_key(
            provider="openrouter",
            name="main",
            api_key="test-secret",
            base_url="https://openrouter.ai/api/v1",
            model="legacy-fixed-model",
        )

        provider = store.get_provider("openrouter")
        account = store.get_provider_account(key.key_id)

        assert provider is not None
        assert account is not None
        assert account.provider_id == "openrouter"
        assert account.legacy_key_id == key.key_id
        assert account.default_model == ""
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_expired_legacy_key_cooldown_reactivates_mirrored_account(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        store = KeyStore(sub)
        key = store.add_key(
            provider="openrouter",
            name="main",
            api_key="test-secret",
            base_url="https://openrouter.ai/api/v1",
        )
        past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        sub.connection.execute(
            "UPDATE provider_keys SET status = 'cooldown', cooldown_until = ? WHERE key_id = ?",
            (past, key.key_id),
        )
        sub.connection.execute(
            "UPDATE provider_accounts SET status = 'cooldown' WHERE legacy_key_id = ?",
            (key.key_id,),
        )
        sub.connection.commit()

        acquired = await store.acquire("openrouter")

        assert acquired is not None
        assert acquired.status is KeyStatus.ACTIVE
        account = store.get_provider_account(key.key_id)
        assert account is not None
        assert account.status == "active"
    finally:
        sub.close()


def test_v31_migration_creates_registry_and_mirrors_legacy_key(tmp_path) -> None:
    db = tmp_path / "legacy.db"
    sub = Substrate.open(db)
    sub.close()
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE provider_observations")
        conn.execute("DROP TABLE provider_quota_windows")
        conn.execute("DROP TABLE provider_account_offerings")
        conn.execute("DROP TABLE provider_accounts")
        conn.execute("DROP TABLE providers")
        conn.execute("DROP TABLE provider_secrets")
        conn.execute("DELETE FROM schema_version WHERE version >= 32")
        conn.execute(
            "INSERT INTO schema_version(version, applied_at) VALUES (31, '2026-06-10')"
        )
        conn.execute(
            "INSERT INTO provider_keys "
            "(key_id, provider, name, api_key, base_url, model, status, priority, "
            "cooldown_until, last_used_at, last_error, last_error_at, request_count, "
            "success_count, error_count, created_at, updated_at, account_id, balance_json, "
            "balance_checked_at, slot) "
            "VALUES ('pk-legacy', 'openrouter', 'legacy', 'secret', "
            "'https://openrouter.ai/api/v1', '', 'active', 0, '', '', '', '', 0, 0, 0, "
            "'2026-06-10', '2026-06-10', '', '{}', '', 'text')"
        )
        conn.commit()

    migrated = Substrate.open(db)
    try:
        assert migrated.schema_version == 34
        account = KeyStore(migrated).get_provider_account("pk-legacy")
        assert account is not None
        assert account.secret_ref == "legacy-provider-key:pk-legacy"
        assert account.default_model == ""
    finally:
        migrated.close()
