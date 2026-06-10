from cryptography.fernet import Fernet

from sonya.providers.adapters.factory import (
    build_lifecycle_adapter,
    build_lifecycle_adapter_for_account,
)
from sonya.providers.adapters.google_native import GoogleNativeAdapter
from sonya.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate


def test_factory_builds_adapter_from_active_encrypted_account(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    sub = Substrate.open(tmp_path / "factory.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous",
            adapter_kind="openai_compatible",
            base_url="https://example.test/v1",
        )
        account = store.add_provider_account(provider_id="nous", name="main")
        store.rotate_account_secret(account.account_id, "opaque-test-secret")

        adapter = build_lifecycle_adapter(store, "nous")

        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert adapter.provider_id == "nous"
        assert adapter.base_url == "https://example.test/v1"
        assert adapter.api_key.get_secret_value() == "opaque-test-secret"
    finally:
        sub.close()


def test_factory_builds_google_native_adapter(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    sub = Substrate.open(tmp_path / "factory.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="google",
            display_name="Google",
            adapter_kind="google_native",
        )
        account = store.add_provider_account(provider_id="google", name="main")
        store.rotate_account_secret(account.account_id, "opaque-test-secret")

        assert isinstance(build_lifecycle_adapter(store, "google"), GoogleNativeAdapter)
    finally:
        sub.close()


def test_factory_builds_adapter_for_specific_account(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    sub = Substrate.open(tmp_path / "factory.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous",
            adapter_kind="openai_compatible",
            base_url="https://example.test/v1",
        )
        first = store.add_provider_account(provider_id="nous", name="first")
        second = store.add_provider_account(provider_id="nous", name="second")
        store.rotate_account_secret(first.account_id, "first-secret")
        store.rotate_account_secret(second.account_id, "second-secret")

        adapter = build_lifecycle_adapter_for_account(store, "nous", second.account_id)

        assert isinstance(adapter, OpenAICompatibleAdapter)
        assert adapter.api_key.get_secret_value() == "second-secret"
    finally:
        sub.close()
