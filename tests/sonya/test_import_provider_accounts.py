from __future__ import annotations

import json

from cryptography.fernet import Fernet

from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate
from sonya.tools.import_provider_accounts import (
    ImportProviderAccountsOptions,
    import_provider_accounts,
    parse_key_file,
)


def test_parse_key_file_accepts_one_key_per_line_without_echoing_values(tmp_path) -> None:
    path = tmp_path / "keys.txt"
    path.write_text(
        "\n".join([
            "sk-test-secret-111111111111",
            "",
            "  sk-test-secret-222222222222  ",
        ]),
        encoding="utf-8",
    )

    records = parse_key_file(path)

    assert [record.name for record in records] == ["account-001", "account-002"]
    assert [record.secret for record in records] == [
        "sk-test-secret-111111111111",
        "sk-test-secret-222222222222",
    ]
    assert "sk-test-secret" not in repr(records[0])


def test_parse_key_file_accepts_json_account_records(tmp_path) -> None:
    path = tmp_path / "keys.json"
    path.write_text(
        json.dumps([
            {"name": "kimchi-a", "api_key": "sk-test-secret-aaaa"},
            {"name": "kimchi-b", "secret": "sk-test-secret-bbbb", "priority": 7},
        ]),
        encoding="utf-8",
    )

    records = parse_key_file(path)

    assert [(record.name, record.priority) for record in records] == [
        ("kimchi-a", 0),
        ("kimchi-b", 7),
    ]
    assert records[1].secret == "sk-test-secret-bbbb"


def test_import_provider_accounts_encrypts_secrets_and_reports_only_masks(tmp_path) -> None:
    db = tmp_path / "providers.db"
    keys = tmp_path / "kimchi.txt"
    first = "sk-kimchi-secret-111111111111"
    second = "sk-kimchi-secret-222222222222"
    keys.write_text(f"{first}\n{second}\n", encoding="utf-8")
    sub = Substrate.open(db)
    try:
        result = import_provider_accounts(
            sub,
            ImportProviderAccountsOptions(
                provider_id="kimchi",
                keys_file=keys,
                secret_encryption_key=Fernet.generate_key().decode("ascii"),
            ),
        )

        assert result.imported == 2
        assert result.skipped_existing == 0
        assert "sk-kimchi-secret" not in result.summary()
        store = KeyStore(sub, secret_encryption_key=result.secret_encryption_key)
        accounts = store.list_provider_accounts("kimchi")
        assert len(accounts) == 2
        assert all(account.secret_ref.startswith("provider-secret:") for account in accounts)
        assert store.resolve_account_secret(accounts[0].account_id).get_secret_value() == first
        dump = "\n".join(sub.connection.iterdump())
        assert first not in dump
        assert second not in dump
    finally:
        sub.close()


def test_import_provider_accounts_dry_run_does_not_write(tmp_path) -> None:
    keys = tmp_path / "kimchi.txt"
    keys.write_text("sk-kimchi-secret-111111111111\n", encoding="utf-8")
    sub = Substrate.open(tmp_path / "providers.db")
    try:
        result = import_provider_accounts(
            sub,
            ImportProviderAccountsOptions(
                provider_id="kimchi",
                keys_file=keys,
                dry_run=True,
                secret_encryption_key=Fernet.generate_key().decode("ascii"),
            ),
        )

        assert result.imported == 1
        assert KeyStore(sub).get_provider("kimchi") is None
    finally:
        sub.close()
