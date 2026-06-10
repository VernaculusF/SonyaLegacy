"""Secret-safe import of provider accounts from ignored local files.

The importer reads raw credentials from a file or stdin, but never prints them
and never writes them to provider JSON management paths. Each account is
created with a pending secret reference and immediately rotated into encrypted
provider secret storage.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sonya.config import load_config
from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate


_PRESETS: dict[str, dict[str, Any]] = {
    "kimchi": {
        "display_name": "Kimchi",
        "adapter_kind": "openai_compatible",
        "base_url": "https://llm.kimchi.dev/openai/v1",
        "metadata": {"source": "operator_import"},
    },
    "nous": {
        "display_name": "Nous Research",
        "adapter_kind": "openai_compatible",
        "base_url": "https://inference-api.nousresearch.com/v1",
        "metadata": {"source": "operator_import"},
    },
    "agentrouter": {
        "display_name": "AgentRouter",
        "adapter_kind": "openai_compatible",
        "base_url": "https://agentrouter.org/v1",
        "metadata": {"source": "operator_import"},
    },
    "codexsale": {
        "display_name": "Codex Sale",
        "adapter_kind": "openai_compatible",
        "base_url": "https://codex.sale/v1",
        "metadata": {"source": "operator_import", "premium": True},
    },
    "openrouter": {
        "display_name": "OpenRouter",
        "adapter_kind": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "metadata": {"source": "operator_import"},
    },
    "google": {
        "display_name": "Google AI Studio",
        "adapter_kind": "google_native",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "metadata": {"source": "operator_import"},
    },
}


@dataclass(frozen=True, slots=True)
class ImportAccountRecord:
    name: str
    secret: str = field(repr=False)
    priority: int = 0
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImportProviderAccountsOptions:
    provider_id: str
    keys_file: Path
    display_name: str = ""
    adapter_kind: str = ""
    base_url: str = ""
    name_prefix: str = ""
    priority: int = 0
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
    secret_encryption_key: str = ""


@dataclass(frozen=True, slots=True)
class ImportProviderAccountsResult:
    provider_id: str
    imported: int
    skipped_existing: int
    skipped_empty: int
    account_masks: tuple[str, ...]
    dry_run: bool
    secret_encryption_key: str = field(default="", repr=False)

    def summary(self) -> str:
        prefix = "DRY RUN " if self.dry_run else ""
        masks = ", ".join(self.account_masks) if self.account_masks else "-"
        return (
            f"{prefix}provider={self.provider_id} imported={self.imported} "
            f"skipped_existing={self.skipped_existing} skipped_empty={self.skipped_empty} "
            f"masks={masks}"
        )


def parse_key_file(path: Path, *, name_prefix: str = "account") -> list[ImportAccountRecord]:
    raw = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    stripped = raw.strip()
    if not stripped:
        return []
    if stripped[0] in "[{":
        payload = json.loads(stripped)
        entries = payload if isinstance(payload, list) else payload.get("accounts", [])
        if not isinstance(entries, list):
            raise ValueError("JSON payload must be a list or an object with accounts[]")
        records: list[ImportAccountRecord] = []
        for index, item in enumerate(entries, start=1):
            if not isinstance(item, dict):
                continue
            secret = str(item.get("secret") or item.get("api_key") or item.get("key") or "").strip()
            if not secret:
                continue
            records.append(
                ImportAccountRecord(
                    name=str(item.get("name") or f"{name_prefix}-{index:03d}").strip(),
                    secret=secret,
                    priority=int(item.get("priority") or 0),
                    status=str(item.get("status") or "active").strip().lower(),
                    metadata=dict(item.get("metadata") or {}),
                    constraints=dict(item.get("constraints") or {}),
                )
            )
        return records

    records = []
    for index, line in enumerate(raw.splitlines(), start=1):
        secret = line.strip()
        if not secret or secret.startswith("#"):
            continue
        records.append(
            ImportAccountRecord(
                name=f"{name_prefix}-{len(records) + 1:03d}",
                secret=secret,
            )
        )
    return records


def import_provider_accounts(
    substrate: Substrate,
    options: ImportProviderAccountsOptions,
) -> ImportProviderAccountsResult:
    provider_id = options.provider_id.strip().lower()
    if not provider_id:
        raise ValueError("provider_id is required")
    preset = _PRESETS.get(provider_id, {})
    display_name = options.display_name or str(preset.get("display_name") or provider_id)
    adapter_kind = options.adapter_kind or str(preset.get("adapter_kind") or "openai_compatible")
    base_url = options.base_url if options.base_url else str(preset.get("base_url") or "")
    name_prefix = options.name_prefix or provider_id
    provider_metadata = {**dict(preset.get("metadata") or {}), **dict(options.metadata)}
    provider_constraints = dict(options.constraints)
    records = parse_key_file(options.keys_file, name_prefix=name_prefix)
    skipped_empty = 0 if records else 1

    secret_key = options.secret_encryption_key or os.environ.get("SONYA_PROVIDER_SECRET_KEY", "")
    store = KeyStore(substrate, secret_encryption_key=secret_key)
    existing_values = set()
    for account in store.list_provider_accounts(provider_id):
        try:
            existing_values.add(store.resolve_account_secret(account.account_id).get_secret_value())
        except Exception:
            continue

    imported = 0
    skipped_existing = 0
    masks: list[str] = []
    if options.dry_run:
        for record in records:
            if record.secret in existing_values:
                skipped_existing += 1
            else:
                imported += 1
                masks.append(_mask(record.secret))
        return ImportProviderAccountsResult(
            provider_id=provider_id,
            imported=imported,
            skipped_existing=skipped_existing,
            skipped_empty=skipped_empty,
            account_masks=tuple(masks),
            dry_run=True,
            secret_encryption_key=secret_key,
        )

    store.upsert_provider(
        provider_id=provider_id,
        display_name=display_name,
        adapter_kind=adapter_kind,
        status="active",
        base_url=base_url,
        constraints_json=json.dumps(provider_constraints, ensure_ascii=False),
        metadata_json=json.dumps(provider_metadata, ensure_ascii=False),
    )
    for record in records:
        if record.secret in existing_values:
            skipped_existing += 1
            continue
        account = store.add_provider_account(
            provider_id=provider_id,
            name=record.name,
            secret_ref="pending:protected-ingestion",
            status=record.status or options.status,
            priority=record.priority or options.priority,
            constraints_json=json.dumps(record.constraints, ensure_ascii=False),
            metadata_json=json.dumps(record.metadata, ensure_ascii=False),
        )
        account = store.rotate_account_secret(account.account_id, record.secret)
        masks.append(account.masked_secret)
        existing_values.add(record.secret)
        imported += 1

    return ImportProviderAccountsResult(
        provider_id=provider_id,
        imported=imported,
        skipped_existing=skipped_existing,
        skipped_empty=skipped_empty,
        account_masks=tuple(masks),
        dry_run=False,
        secret_encryption_key=secret_key,
    )


def _mask(secret: str) -> str:
    if len(secret) <= 12:
        return "***"
    return f"{secret[:6]}...{secret[-4:]}"


def _json_object(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import provider accounts from a secret file")
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--keys-file", required=True, type=Path, help="Ignored file path, or '-' for stdin")
    parser.add_argument("--display-name", default="")
    parser.add_argument("--adapter-kind", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--name-prefix", default="")
    parser.add_argument("--priority", type=int, default=0)
    parser.add_argument("--status", default="active")
    parser.add_argument("--metadata-json", default="")
    parser.add_argument("--constraints-json", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sub = Substrate.open(load_config().substrate_path)
    try:
        result = import_provider_accounts(
            sub,
            ImportProviderAccountsOptions(
                provider_id=args.provider_id,
                keys_file=args.keys_file,
                display_name=args.display_name,
                adapter_kind=args.adapter_kind,
                base_url=args.base_url,
                name_prefix=args.name_prefix,
                priority=args.priority,
                status=args.status,
                metadata=_json_object(args.metadata_json),
                constraints=_json_object(args.constraints_json),
                dry_run=args.dry_run,
            ),
        )
        print(result.summary())
        return 0
    finally:
        sub.close()


if __name__ == "__main__":
    raise SystemExit(main())
