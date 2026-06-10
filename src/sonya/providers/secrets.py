from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from sonya.state.substrate import Substrate


@dataclass(frozen=True, slots=True)
class ProviderSecret:
    """Wrapper that prevents accidental leak of secret values via repr/str/log."""

    _value: str

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", value)

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "ProviderSecret('***')"

    def __str__(self) -> str:
        return "***"


@dataclass(frozen=True, slots=True)
class ProviderSecretRecord:
    secret_id: str
    provider_id: str
    account_id: str
    secret_kind: str
    secret_ref: str
    masked_value: str
    value_fingerprint: str
    status: str
    created_at: str
    updated_at: str


def mask_secret(value: str) -> str:
    if len(value) > 12:
        return f"{value[:6]}...{value[-4:]}"
    return "***"


class ProviderSecretStore:
    """Substrate-backed encrypted secret storage.

    Metadata surfaces carry only `provider-secret:<id>` references and masks.
    Raw values are returned only through explicit `resolve()` calls.
    """

    ENV_KEY = "SONYA_PROVIDER_SECRET_KEY"

    def __init__(self, substrate: Substrate, *, encryption_key: str | bytes | None = None) -> None:
        self._sub = substrate
        raw_key = encryption_key or os.environ.get(self.ENV_KEY)
        self._fernet: Fernet | None = Fernet(_normalize_key(raw_key)) if raw_key else None

    def store_secret(
        self,
        *,
        provider_id: str,
        account_id: str,
        secret_kind: str,
        raw_value: str,
    ) -> ProviderSecretRecord:
        if not raw_value:
            raise ValueError("raw_value is required")
        if self._fernet is None:
            raise RuntimeError(f"{self.ENV_KEY} is required to store provider secrets")
        secret_id = f"ps-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        encrypted = self._fernet.encrypt(raw_value.encode("utf-8")).decode("ascii")
        self._sub.connection.execute(
            "INSERT INTO provider_secrets "
            "(secret_id, provider_id, account_id, secret_kind, encrypted_value, "
            "value_fingerprint, masked_value, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
            (
                secret_id, provider_id, account_id, secret_kind, encrypted,
                sha256(raw_value.encode("utf-8")).hexdigest(), mask_secret(raw_value),
                now, now,
            ),
        )
        self._sub.connection.commit()
        return self.get_record(secret_id)  # type: ignore[return-value]

    def get_record(self, secret_id: str) -> ProviderSecretRecord | None:
        row = self._sub.connection.execute(
            "SELECT secret_id, provider_id, account_id, secret_kind, masked_value, "
            "value_fingerprint, status, created_at, updated_at "
            "FROM provider_secrets WHERE secret_id = ?",
            (secret_id,),
        ).fetchone()
        return _row_to_secret_record(row) if row else None

    def resolve(self, secret_ref: str) -> ProviderSecret:
        if not secret_ref.startswith("provider-secret:"):
            raise ValueError(f"unsupported secret ref: {secret_ref}")
        if self._fernet is None:
            raise RuntimeError(f"{self.ENV_KEY} is required to resolve provider secrets")
        secret_id = secret_ref.split(":", 1)[1]
        row = self._sub.connection.execute(
            "SELECT encrypted_value FROM provider_secrets "
            "WHERE secret_id = ? AND status = 'active'",
            (secret_id,),
        ).fetchone()
        if row is None:
            raise KeyError(secret_ref)
        try:
            value = self._fernet.decrypt(str(row[0]).encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("provider secret decryption failed") from exc
        return ProviderSecret(value)

    def rotate_secret(
        self,
        *,
        provider_id: str,
        account_id: str,
        secret_kind: str,
        raw_value: str,
    ) -> ProviderSecretRecord:
        record = self.store_secret(
            provider_id=provider_id,
            account_id=account_id,
            secret_kind=secret_kind,
            raw_value=raw_value,
        )
        self._sub.connection.execute(
            "UPDATE provider_secrets SET status = 'inactive', updated_at = ? "
            "WHERE account_id = ? AND secret_kind = ? AND secret_id != ? AND status = 'active'",
            (datetime.now(timezone.utc).isoformat(), account_id, secret_kind, record.secret_id),
        )
        self._sub.connection.commit()
        return record


def _normalize_key(raw_key: str | bytes) -> bytes:
    if isinstance(raw_key, bytes):
        return raw_key
    return raw_key.encode("ascii")


def _row_to_secret_record(row: Iterable[object]) -> ProviderSecretRecord:
    r = list(row)
    return ProviderSecretRecord(
        secret_id=str(r[0]),
        provider_id=str(r[1]),
        account_id=str(r[2]),
        secret_kind=str(r[3]),
        secret_ref=f"provider-secret:{r[0]}",
        masked_value=str(r[4]),
        value_fingerprint=str(r[5]),
        status=str(r[6]),
        created_at=str(r[7]),
        updated_at=str(r[8]),
    )
