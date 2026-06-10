from __future__ import annotations

from cryptography.fernet import Fernet

from sonya.providers import ProviderSecret
from sonya.providers.keystore import KeyStore
from sonya.providers.llm_provider import _resolve_key_secret
from sonya.providers.secrets import ProviderSecretStore
from sonya.state.substrate import Substrate


def test_secret_repr_redacts_value() -> None:
    s = ProviderSecret("super-secret-key-abcdef")
    assert "super-secret" not in repr(s)
    assert "abcdef" not in repr(s)


def test_secret_get_returns_value() -> None:
    s = ProviderSecret("k1")
    assert s.get_secret_value() == "k1"


def test_secret_str_redacts_value() -> None:
    s = ProviderSecret("k1")
    assert "k1" not in str(s)


def test_provider_secret_store_encrypts_and_masks_value(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "secrets.db")
    try:
        KeyStore(sub).upsert_provider(
            provider_id="nous",
            display_name="Nous Research",
            adapter_kind="openai_compatible",
        )
        KeyStore(sub).add_provider_account(
            account_id="acct-1",
            provider_id="nous",
            name="primary",
            secret_ref="manual:test",
        )
        store = ProviderSecretStore(sub, encryption_key=Fernet.generate_key().decode("ascii"))
        record = store.store_secret(
            provider_id="nous",
            account_id="acct-1",
            secret_kind="api_key",
            raw_value="sk-test-secret-abcdef123456",
        )

        row = sub.connection.execute(
            "SELECT encrypted_value, masked_value FROM provider_secrets WHERE secret_id = ?",
            (record.secret_id,),
        ).fetchone()
        assert row is not None
        assert "sk-test-secret" not in row[0]
        assert row[1] == "sk-tes...3456"
        assert store.resolve(record.secret_ref).get_secret_value() == "sk-test-secret-abcdef123456"
    finally:
        sub.close()


def test_provider_account_with_secret_value_exposes_only_ref_and_mask(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "account-secret.db")
    try:
        store = KeyStore(sub, secret_encryption_key=Fernet.generate_key().decode("ascii"))
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous Research",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="nous",
            name="primary",
            secret_value="sk-nous-secret-abcdef123456",
        )

        assert account.secret_ref.startswith("provider-secret:")
        assert account.masked_secret == "sk-nou...3456"
        assert "sk-nous-secret" not in repr(account)
        assert "sk-nous-secret" not in account.secret_ref
        assert store.resolve_account_secret(account.account_id).get_secret_value() == "sk-nous-secret-abcdef123456"
    finally:
        sub.close()


def test_legacy_provider_key_secret_resolution_is_explicit(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "legacy-secret.db")
    try:
        store = KeyStore(sub)
        key = store.add_key(
            provider="openrouter",
            name="legacy",
            api_key="sk-legacy-secret-abcdef123456",
            base_url="https://openrouter.ai/api/v1",
        )
        account = store.get_provider_account(key.key_id)

        assert account is not None
        assert account.secret_ref == f"legacy-provider-key:{key.key_id}"
        assert account.masked_secret == key.masked()
        assert store.resolve_account_secret(account.account_id).get_secret_value() == "sk-legacy-secret-abcdef123456"
    finally:
        sub.close()


def test_legacy_provider_key_can_migrate_without_returning_plaintext(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "legacy-secret-migration.db")
    try:
        store = KeyStore(sub, secret_encryption_key=Fernet.generate_key().decode("ascii"))
        key = store.add_key(
            provider="openrouter",
            name="legacy",
            api_key="sk-legacy-secret-abcdef123456",
            base_url="https://openrouter.ai/api/v1",
        )

        account = store.migrate_legacy_account_secret(key.key_id)

        assert account.secret_ref.startswith("provider-secret:")
        assert account.masked_secret == key.masked()
        assert account.legacy_key_id == key.key_id
        assert "sk-legacy-secret" not in repr(account)
        assert store.resolve_account_secret(account.account_id).get_secret_value() == "sk-legacy-secret-abcdef123456"
        assert sub.connection.execute(
            "SELECT COUNT(*) FROM provider_secrets WHERE account_id = ? AND status = 'active'",
            (account.account_id,),
        ).fetchone()[0] == 1
        assert store.get_key(key.key_id).api_key == ""
        assert _resolve_key_secret(store, store.get_key(key.key_id)) == "sk-legacy-secret-abcdef123456"
        dump = "\n".join(sub.connection.iterdump())
        assert "sk-legacy-secret-abcdef123456" not in dump
    finally:
        sub.close()
