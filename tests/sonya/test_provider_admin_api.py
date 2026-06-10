from __future__ import annotations

import json

from cryptography.fernet import Fernet
from aiohttp.test_utils import TestClient, TestServer

from sonya.admin.server import create_app
from sonya.providers.keystore import KeyStore
from sonya.providers.adapters.base import AdapterHealth
from sonya.providers.adapters.openai_compatible import OpenAICompatibleAdapter
from sonya.state.substrate import Substrate


async def _client(tmp_path, monkeypatch) -> TestClient:
    db = tmp_path / "admin-providers.db"
    token = "test-admin-token"
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(db))
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", token)
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    app = create_app()
    client = TestClient(TestServer(app), headers={"X-Atrium-Token": token})
    await client.start_server()
    return client


async def test_admin_provider_registry_payload_and_create_flow(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        resp = await client.post("/api/providers/registry", json={
            "provider_id": "nous",
            "display_name": "Nous Research",
            "adapter_kind": "openai_compatible",
            "base_url": "https://inference-api.nousresearch.com/v1",
        })
        assert resp.status == 200
        data = await resp.json()
        assert data["provider"]["provider_id"] == "nous"

        resp = await client.post("/api/providers/accounts", json={
            "provider_id": "nous",
            "name": "primary",
            "secret_ref": "pending:protected-ingestion",
        })
        assert resp.status == 200
        data = await resp.json()
        account_id = data["account"]["account_id"]

        raw_secret = "raw-secret-visible-only-to-ingestion-handler"
        resp = await client.put(
            f"/api/providers/accounts/{account_id}/secret",
            data=raw_secret,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert resp.status == 200
        secret_data = await resp.json()
        assert secret_data["account"]["secret_masked"]
        assert secret_data["account"]["secret_ref"].startswith("provider-secret:")
        assert raw_secret not in str(secret_data)

        sub = Substrate.open(tmp_path / "admin-providers.db")
        try:
            store = KeyStore(sub)
            store.upsert_provider_model(
                model_id="nvidia/nemotron-3-ultra:free",
                provider="nous",
                model_name="Nemotron 3 Ultra",
                context_length=1_000_000,
                is_free=1,
            )
        finally:
            sub.close()

        resp = await client.post("/api/providers/accounts/offerings", json={
            "account_id": account_id,
            "model_id": "nvidia/nemotron-3-ultra:free",
            "enabled": True,
        })
        assert resp.status == 200

        resp = await client.get("/api/providers")
        assert resp.status == 200
        data = await resp.json()
        assert data["providers"][0]["provider_id"] == "nous"
        assert data["accounts"][0]["account_id"] == account_id
        assert data["models"][0]["model_id"] == "nvidia/nemotron-3-ultra:free"
        assert raw_secret not in str(data)
    finally:
        await client.close()


async def test_admin_provider_refresh_runs_lifecycle_service(tmp_path, monkeypatch) -> None:
    async def health_check(self):
        return AdapterHealth(ok=True, status="ok", latency_ms=12)

    async def discover_models(self):
        return []

    async def fetch_quota(self):
        return []

    client = await _client(tmp_path, monkeypatch)
    try:
        await client.post("/api/providers/registry", json={
            "provider_id": "nous",
            "display_name": "Nous",
            "adapter_kind": "openai_compatible",
        })
        account_response = await client.post("/api/providers/accounts", json={
            "provider_id": "nous",
            "name": "main",
            "secret_ref": "pending:protected-ingestion",
        })
        account = (await account_response.json())["account"]
        await client.put(
            f"/api/providers/accounts/{account['account_id']}/secret",
            data="opaque-test-secret",
            headers={"Content-Type": "application/octet-stream"},
        )
        monkeypatch.setattr(OpenAICompatibleAdapter, "health_check", health_check)
        monkeypatch.setattr(OpenAICompatibleAdapter, "discover_models", discover_models)
        monkeypatch.setattr(OpenAICompatibleAdapter, "fetch_quota", fetch_quota)

        response = await client.post("/api/providers/registry/nous/refresh")

        body = await response.text()
        assert response.status == 200, body
        payload = json.loads(body)
        assert payload == {
            "provider_id": "nous",
            "ok": True,
            "models_seen": 0,
            "quotas_seen": 0,
            "error": "",
        }
    finally:
        await client.close()


async def test_admin_provider_refresh_builds_adapter_per_active_account(tmp_path, monkeypatch) -> None:
    async def health_check(self):
        return AdapterHealth(ok=True, status="ok")

    async def discover_models(self):
        return []

    async def fetch_quota(self):
        return []

    resolved_for: list[str] = []
    original_resolve = KeyStore.resolve_account_secret

    client = await _client(tmp_path, monkeypatch)
    try:
        await client.post("/api/providers/registry", json={
            "provider_id": "nous",
            "display_name": "Nous",
            "adapter_kind": "openai_compatible",
        })
        first = await (await client.post("/api/providers/accounts", json={
            "provider_id": "nous",
            "name": "first",
            "secret_ref": "pending:protected-ingestion",
        })).json()
        second = await (await client.post("/api/providers/accounts", json={
            "provider_id": "nous",
            "name": "second",
            "secret_ref": "pending:protected-ingestion",
        })).json()
        await client.put(
            f"/api/providers/accounts/{first['account']['account_id']}/secret",
            data="first-secret",
            headers={"Content-Type": "application/octet-stream"},
        )
        await client.put(
            f"/api/providers/accounts/{second['account']['account_id']}/secret",
            data="second-secret",
            headers={"Content-Type": "application/octet-stream"},
        )

        def resolve_account_secret(self, account_id):
            resolved_for.append(account_id)
            return original_resolve(self, account_id)

        monkeypatch.setattr(KeyStore, "resolve_account_secret", resolve_account_secret)
        monkeypatch.setattr(OpenAICompatibleAdapter, "health_check", health_check)
        monkeypatch.setattr(OpenAICompatibleAdapter, "discover_models", discover_models)
        monkeypatch.setattr(OpenAICompatibleAdapter, "fetch_quota", fetch_quota)

        response = await client.post("/api/providers/registry/nous/refresh")

        body = await response.text()
        assert response.status == 200, body
        assert sorted(resolved_for) == sorted([
            first["account"]["account_id"],
            second["account"]["account_id"],
        ])
    finally:
        await client.close()


async def test_admin_account_status_and_provider_delete_guard(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        await client.post("/api/providers/registry", json={
            "provider_id": "agentrouter",
            "display_name": "AgentRouter",
            "adapter_kind": "openai_compatible",
        })
        resp = await client.post("/api/providers/accounts", json={
            "provider_id": "agentrouter",
            "name": "main",
            "secret_ref": "manual:test",
        })
        account_id = (await resp.json())["account"]["account_id"]

        resp = await client.post(f"/api/providers/registry/agentrouter/delete")
        assert resp.status == 409

        resp = await client.post(f"/api/providers/accounts/{account_id}", json={"status": "disabled"})
        assert resp.status == 200
        assert (await resp.json())["account"]["status"] == "disabled"

        resp = await client.post(f"/api/providers/accounts/{account_id}/delete")
        assert resp.status == 200
        resp = await client.post("/api/providers/registry/agentrouter/delete")
        assert resp.status == 200
    finally:
        await client.close()


async def test_admin_regular_account_endpoint_rejects_raw_secret_fields(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        await client.post("/api/providers/registry", json={
            "provider_id": "nous",
            "display_name": "Nous",
            "adapter_kind": "openai_compatible",
        })

        response = await client.post("/api/providers/accounts", json={
            "provider_id": "nous",
            "name": "unsafe",
            "secret_value": "raw-secret-must-not-enter-json-management",
        })

        assert response.status == 400
        payload = await response.json()
        assert "protected secret-ingestion" in payload["error"]
    finally:
        await client.close()


async def test_admin_legacy_key_endpoint_rejects_raw_secret_fields(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        response = await client.post("/api/providers/keys", json={
            "provider": "codexsale",
            "name": "unsafe",
            "api_key": "raw-secret-must-not-enter-legacy-json-management",
        })

        assert response.status == 400
        payload = await response.json()
        assert "protected secret-ingestion" in payload["error"]
    finally:
        await client.close()


async def test_admin_secret_ingestion_is_disabled_without_admin_password(tmp_path, monkeypatch) -> None:
    db = tmp_path / "admin-providers.db"
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(db))
    monkeypatch.setenv("SONYA_PROVIDER_SECRET_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.delenv("SONYA_ADMIN_PASSWORD", raising=False)
    sub = Substrate.open(db)
    try:
        store = KeyStore(sub)
        store.upsert_provider(
            provider_id="nous",
            display_name="Nous",
            adapter_kind="openai_compatible",
        )
        account = store.add_provider_account(
            provider_id="nous",
            name="primary",
            secret_ref="pending:protected-ingestion",
        )
    finally:
        sub.close()

    client = TestClient(TestServer(create_app()))
    await client.start_server()
    try:
        response = await client.put(
            f"/api/providers/accounts/{account.account_id}/secret",
            data="must-not-be-ingested",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert response.status == 503

        sub = Substrate.open(db)
        try:
            assert KeyStore(sub).get_provider_account(account.account_id).secret_ref == "pending:protected-ingestion"
            assert sub.connection.execute("SELECT COUNT(*) FROM provider_secrets").fetchone()[0] == 0
        finally:
            sub.close()
    finally:
        await client.close()


async def test_admin_secret_ingestion_rotates_without_plaintext_leak(tmp_path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    db = tmp_path / "admin-providers.db"
    try:
        await client.post("/api/providers/registry", json={
            "provider_id": "nous",
            "display_name": "Nous",
            "adapter_kind": "openai_compatible",
        })
        response = await client.post("/api/providers/accounts", json={
            "provider_id": "nous",
            "name": "primary",
            "secret_ref": "pending:protected-ingestion",
        })
        account_id = (await response.json())["account"]["account_id"]

        first = "first-opaque-provider-secret"
        response = await client.put(
            f"/api/providers/accounts/{account_id}/secret",
            data=first,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert response.status == 200
        first_payload = await response.json()
        assert first not in str(first_payload)

        second = "second-opaque-provider-secret"
        response = await client.put(
            f"/api/providers/accounts/{account_id}/secret",
            data=second,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert response.status == 200
        second_payload = await response.json()
        assert second not in str(second_payload)
        assert second_payload["account"]["secret_ref"] != first_payload["account"]["secret_ref"]

        sub = Substrate.open(db)
        try:
            store = KeyStore(sub)
            assert store.resolve_account_secret(account_id).get_secret_value() == second
            rows = sub.connection.execute(
                "SELECT encrypted_value, status FROM provider_secrets WHERE account_id = ? ORDER BY created_at",
                (account_id,),
            ).fetchall()
            assert len(rows) == 2
            assert [row[1] for row in rows] == ["inactive", "active"]
            assert all(first not in row[0] and second not in row[0] for row in rows)
            dump = "\n".join(sub.connection.iterdump())
            assert first not in dump
            assert second not in dump
        finally:
            sub.close()
    finally:
        await client.close()
