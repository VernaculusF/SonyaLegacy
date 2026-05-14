from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class Principal:
    principal_id: str
    display_name: str
    trusted_identifiers: tuple[str, ...] = field(default_factory=tuple)
    authority_scope: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = ""


class PrincipalAlreadyExistsError(RuntimeError):
    pass


class PrincipalRegistry:
    """Minimal CRUD over the principals table.

    Real identity resolution from channels is Phase 2; this is the storage layer.
    """

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def register(self, principal: Principal) -> Principal:
        existing = self.get(principal.principal_id)
        if existing is not None:
            raise PrincipalAlreadyExistsError(principal.principal_id)
        created_at = principal.created_at or _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO principals(principal_id, display_name, trusted_identifiers_json, "
            "authority_scope_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                principal.principal_id,
                principal.display_name,
                json.dumps(list(principal.trusted_identifiers), ensure_ascii=False),
                json.dumps(list(principal.authority_scope), ensure_ascii=False),
                created_at,
            ),
        )
        self._sub.connection.commit()
        return Principal(
            principal_id=principal.principal_id,
            display_name=principal.display_name,
            trusted_identifiers=principal.trusted_identifiers,
            authority_scope=principal.authority_scope,
            created_at=created_at,
        )

    def get(self, principal_id: str) -> Principal | None:
        row = self._sub.connection.execute(
            "SELECT principal_id, display_name, trusted_identifiers_json, "
            "authority_scope_json, created_at FROM principals WHERE principal_id = ?",
            (principal_id,),
        ).fetchone()
        return self._row_to_principal(row)

    def resolve_by_trusted_identifier(self, identifier: str) -> Principal | None:
        cursor = self._sub.connection.execute(
            "SELECT principal_id, display_name, trusted_identifiers_json, "
            "authority_scope_json, created_at FROM principals"
        )
        for row in cursor.fetchall():
            ids = json.loads(row[2] or "[]")
            if identifier in ids:
                return self._row_to_principal(row)
        return None

    def list_all(self) -> list[Principal]:
        cursor = self._sub.connection.execute(
            "SELECT principal_id, display_name, trusted_identifiers_json, "
            "authority_scope_json, created_at FROM principals ORDER BY created_at"
        )
        return [self._row_to_principal(row) for row in cursor.fetchall() if row]

    @staticmethod
    def _row_to_principal(row) -> Principal | None:
        if row is None:
            return None
        return Principal(
            principal_id=row[0],
            display_name=row[1],
            trusted_identifiers=tuple(json.loads(row[2] or "[]")),
            authority_scope=tuple(json.loads(row[3] or "[]")),
            created_at=row[4],
        )
