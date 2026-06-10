from __future__ import annotations

import sqlite3

from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate


def test_account_can_exist_without_fixed_model(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "offerings.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous Research",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="nous",
            name="primary",
            secret_ref="provider-key:future",
        )

        assert account.provider_id == "nous"
        assert account.default_model == ""
        assert store.list_available_provider_models("nous") == []
    finally:
        sub.close()


def test_model_requires_enabled_eligible_account_offering(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "offerings.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous Research",
            adapter_kind="openai_compatible",
        )
        model = store.upsert_provider_model(
            model_id="nvidia/nemotron-3-ultra:free",
            provider="nous",
            model_name="Nemotron 3 Ultra",
            context_length=1_000_000,
            is_free=1,
        )
        account = store.add_provider_account(
            provider_id="nous",
            name="primary",
            secret_ref="provider-key:future",
        )

        assert store.list_available_provider_models("nous") == []

        store.set_account_offering(account.account_id, model.model_id, enabled=True)
        assert [item.model_id for item in store.list_available_provider_models("nous")] == [
            model.model_id
        ]

        store.update_provider_account_status(account.account_id, "disabled")
        assert store.list_available_provider_models("nous") == []
    finally:
        sub.close()


def test_quota_windows_and_observations_have_typed_round_trip(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "observations.db")
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous Research",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="nous",
            name="primary",
            secret_ref="provider-key:future",
        )

        quota = store.upsert_quota_window(
            account_id=account.account_id,
            quota_kind="tpm",
            limit_value=500_000,
            used_value=100_000,
            remaining_value=400_000,
            unit="tokens",
            resets_at="2026-06-10T20:00:00+00:00",
        )
        observation = store.record_provider_observation(
            provider_id="nous",
            account_id=account.account_id,
            model_id="nvidia/nemotron-3-ultra:free",
            observation_kind="health_probe",
            success=True,
            latency_ms=250,
            value_json='{"ok":true}',
        )

        assert store.list_quota_windows(account.account_id) == [quota]
        assert store.list_provider_observations(provider_id="nous") == [observation]
    finally:
        sub.close()


def test_v33_legacy_provider_models_table_is_repaired_on_open(tmp_path) -> None:
    db = tmp_path / "legacy-v33.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (33, '2026-06-10T00:00:00+00:00');

        CREATE TABLE provider_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            active_provider TEXT NOT NULL DEFAULT 'openrouter',
            default_model TEXT NOT NULL DEFAULT '',
            default_base_url TEXT NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE providers (
            provider_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            adapter_kind TEXT NOT NULL DEFAULT 'openai_compatible',
            status TEXT NOT NULL DEFAULT 'active',
            base_url TEXT NOT NULL DEFAULT '',
            capabilities_json TEXT NOT NULL DEFAULT '{}',
            constraints_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO providers(provider_id, display_name, created_at, updated_at)
        VALUES ('stub', 'Stub', '2026-06-10T00:00:00+00:00', '2026-06-10T00:00:00+00:00');

        CREATE TABLE provider_accounts (
            account_id TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            name TEXT NOT NULL,
            secret_ref TEXT NOT NULL,
            secret_masked TEXT NOT NULL DEFAULT '',
            legacy_key_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            priority INTEGER NOT NULL DEFAULT 0,
            constraints_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            default_model TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO provider_accounts(account_id, provider_id, name, secret_ref, created_at, updated_at)
        VALUES ('pa-1', 'stub', 'primary', 'manual:test', '2026-06-10T00:00:00+00:00', '2026-06-10T00:00:00+00:00');

        CREATE TABLE provider_models (
            model_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            base_url TEXT NOT NULL DEFAULT '',
            api_key_ref TEXT NOT NULL DEFAULT '',
            context_length INTEGER NOT NULL DEFAULT 131072,
            modalities_json TEXT NOT NULL DEFAULT '["text"]',
            cost_per_1m_input_tokens REAL NOT NULL DEFAULT 0.0,
            cost_per_1m_output_tokens REAL NOT NULL DEFAULT 0.0,
            is_free INTEGER NOT NULL DEFAULT 0,
            latency_tier TEXT NOT NULL DEFAULT 'medium',
            strength_json TEXT NOT NULL DEFAULT '{}',
            role_preference TEXT NOT NULL DEFAULT 'auto',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO provider_models(model_id, provider, model_name, created_at, updated_at)
        VALUES ('stub/model', 'stub', 'Stub Model', '2026-06-10T00:00:00+00:00', '2026-06-10T00:00:00+00:00');

        CREATE TABLE provider_account_offerings (
            account_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(account_id, model_id)
        );
        INSERT INTO provider_account_offerings(account_id, model_id, created_at, updated_at)
        VALUES ('pa-1', 'stub/model', '2026-06-10T00:00:00+00:00', '2026-06-10T00:00:00+00:00');
    """)
    conn.close()

    sub = Substrate.open(db)
    try:
        columns = {
            row[1]
            for row in sub.connection.execute("PRAGMA table_info(provider_models)").fetchall()
        }
        assert {"text_loop_ok", "last_checked_at", "discovery_source", "metadata_json"} <= columns
        assert [m.model_id for m in KeyStore(sub).list_available_provider_models("stub")] == ["stub/model"]
    finally:
        sub.close()
