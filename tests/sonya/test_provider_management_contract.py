from __future__ import annotations

import json

from cryptography.fernet import Fernet

from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate
from sonya.tools.providers_tool import ProvidersTool


def test_providers_tool_manages_provider_account_and_offering(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        tool = ProvidersTool(sub)

        out = tool.upsert_provider(json.dumps({
            "provider_id": "nous",
            "display_name": "Nous Research",
            "adapter_kind": "openai_compatible",
            "base_url": "https://inference-api.nousresearch.com/v1",
            "capabilities": {"openai_compatible": True},
        }))
        assert "[OK]" in out

        out = tool.add_account(json.dumps({
            "provider_id": "nous",
            "name": "primary",
            "secret_ref": "pending:protected-ingestion",
            "priority": 10,
        }))
        assert "[OK]" in out
        account_id = out.split("account_id=", 1)[1].split()[0]

        store = KeyStore(sub)
        account = store.get_provider_account(account_id)
        assert account is not None
        assert account.secret_ref == "pending:protected-ingestion"

        model = store.upsert_provider_model(
            model_id="nvidia/nemotron-3-ultra:free",
            provider="nous",
            model_name="Nemotron 3 Ultra",
            context_length=1_000_000,
            is_free=1,
            discovery_source="manual",
        )
        out = tool.set_offering(json.dumps({
            "account_id": account_id,
            "model_id": model.model_id,
            "enabled": True,
        }))
        assert "[OK]" in out
        assert [m.model_id for m in store.list_available_provider_models("nous")] == [model.model_id]

        out = tool.list_providers()
        assert "nous" in out
        assert "accounts=1" in out
        assert "available_models=1" in out
    finally:
        sub.close()


def test_providers_tool_rejects_raw_secret_ingestion(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        tool = ProvidersTool(sub)
        tool.upsert_provider(json.dumps({
            "provider_id": "nous",
            "display_name": "Nous",
            "adapter_kind": "openai_compatible",
        }))

        out = tool.add_account(json.dumps({
            "provider_id": "nous",
            "name": "primary",
            "secret_value": "raw-secret-must-not-enter-tool-trace",
        }))

        assert "[ERROR]" in out
        assert "protected secret-ingestion" in out
        assert KeyStore(sub).list_provider_accounts("nous") == []
    finally:
        sub.close()


def test_providers_tool_legacy_add_key_rejects_raw_secret_ingestion(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        out = ProvidersTool(sub).add_key(json.dumps({
            "provider": "codexsale",
            "name": "unsafe",
            "api_key": "raw-secret-must-not-enter-legacy-tool-trace",
        }))

        assert "[ERROR]" in out
        assert "protected secret-ingestion" in out
        assert KeyStore(sub).list_keys("codexsale") == []
    finally:
        sub.close()


def test_providers_tool_migrates_legacy_account_secret_without_plaintext(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        store = KeyStore(sub)
        key = store.add_key(
            provider="openrouter",
            name="legacy",
            api_key="sk-legacy-secret-abcdef123456",
            base_url="https://openrouter.ai/api/v1",
        )

        out = ProvidersTool(sub).migrate_legacy_secret(key.key_id)

        assert "[OK]" in out
        assert "provider-secret:" in out
        assert "sk-legacy-secret" not in out
        assert store.get_provider_account(key.key_id).secret_ref.startswith("provider-secret:")
    finally:
        sub.close()


def test_providers_tool_updates_account_status_and_reports_health(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        store = KeyStore(sub)
        tool = ProvidersTool(sub)
        store.upsert_provider(
            provider_id="openrouter",
            display_name="OpenRouter",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="openrouter",
            name="main",
            secret_ref="manual:test",
        )
        model = store.upsert_provider_model(
            model_id="openrouter/test",
            provider="openrouter",
            model_name="Test",
            is_free=1,
        )
        store.set_account_offering(account.account_id, model.model_id, enabled=True)
        store.upsert_quota_window(
            account_id=account.account_id,
            quota_kind="rpd",
            limit_value=1000,
            used_value=100,
            remaining_value=900,
            unit="requests",
            resets_at="2026-06-11T00:00:00+00:00",
        )
        store.record_provider_observation(
            provider_id="openrouter",
            account_id=account.account_id,
            model_id=model.model_id,
            observation_kind="health",
            success=True,
            latency_ms=123,
            value_json='{"status":"ok"}',
        )

        out = tool.provider_health("openrouter")
        assert "openrouter" in out
        assert "rpd" in out
        assert "remaining=900" in out
        assert "health ok" in out

        out = tool.update_account(json.dumps({
            "account_id": account.account_id,
            "status": "disabled",
        }))
        assert "[OK]" in out
        assert store.list_available_provider_models("openrouter") == []
    finally:
        sub.close()


def test_providers_tool_deletes_provider_only_after_accounts_removed(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        store = KeyStore(sub)
        tool = ProvidersTool(sub)
        store.upsert_provider(
            provider_id="agentrouter",
            display_name="AgentRouter",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="agentrouter",
            name="main",
            secret_ref="manual:test",
        )

        out = tool.delete_provider("agentrouter")
        assert "[ERROR]" in out
        assert "accounts still exist" in out

        out = tool.delete_account(account.account_id)
        assert "[OK]" in out
        assert store.get_provider_account(account.account_id) is None

        out = tool.delete_provider("agentrouter")
        assert "[OK]" in out
        assert store.get_provider("agentrouter") is None
    finally:
        sub.close()
