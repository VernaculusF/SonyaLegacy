from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate


class ImmutableFieldError(RuntimeError):
    """Raised when a runtime path tries to mutate an identity-critical field."""


_IMMUTABLE_FIELDS: frozenset[str] = frozenset(
    {"things_not_to_betray", "identity_critical_traits"}
)


@dataclass(frozen=True, slots=True)
class IdentityRecord:
    """Single-row identity. Immutable fields cannot be changed via write_mutable."""

    self_model: dict[str, Any] = field(default_factory=dict)
    things_not_to_betray: tuple[str, ...] = field(default_factory=tuple)
    identity_critical_traits: tuple[str, ...] = field(default_factory=tuple)
    drift_boundaries: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RelationAnchorBinding:
    """Identity-critical binding of a relation anchor to a principal."""

    principal_id: str
    trusted_identifiers: tuple[str, ...] = field(default_factory=tuple)
    trust_evidence: dict[str, Any] = field(default_factory=dict)
    authority_scope: tuple[str, ...] = field(default_factory=tuple)
    channel_constraints: dict[str, Any] = field(default_factory=dict)
    is_primary: bool = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdentityWriter:
    """Write-side enforcement of identity-critical immutability."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def load(self) -> IdentityRecord:
        row = self._sub.connection.execute(
            "SELECT self_model_json, things_not_to_betray_json, "
            "identity_critical_traits_json, drift_boundaries_json "
            "FROM identity_record WHERE id = 1"
        ).fetchone()
        if row is None:
            return IdentityRecord()
        return IdentityRecord(
            self_model=json.loads(row[0] or "{}"),
            things_not_to_betray=tuple(json.loads(row[1] or "[]")),
            identity_critical_traits=tuple(json.loads(row[2] or "[]")),
            drift_boundaries=json.loads(row[3] or "{}"),
        )

    def _save(self, record: IdentityRecord) -> None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO identity_record(id, self_model_json, things_not_to_betray_json, "
            "identity_critical_traits_json, drift_boundaries_json, updated_at) "
            "VALUES (1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "self_model_json=excluded.self_model_json, "
            "things_not_to_betray_json=excluded.things_not_to_betray_json, "
            "identity_critical_traits_json=excluded.identity_critical_traits_json, "
            "drift_boundaries_json=excluded.drift_boundaries_json, "
            "updated_at=excluded.updated_at",
            (
                json.dumps(record.self_model, ensure_ascii=False),
                json.dumps(list(record.things_not_to_betray), ensure_ascii=False),
                json.dumps(list(record.identity_critical_traits), ensure_ascii=False),
                json.dumps(record.drift_boundaries, ensure_ascii=False),
                now,
            ),
        )
        self._sub.connection.commit()

    def write_mutable(self, record: IdentityRecord) -> None:
        """Write only mutable parts; rejects any change to immutable fields vs current state."""
        current = self.load()
        for fname in _IMMUTABLE_FIELDS:
            if getattr(current, fname) != getattr(record, fname):
                raise ImmutableFieldError(
                    f"field {fname!r} is identity-critical; use write_via_governed_change"
                )
        self._save(record)

    def write_via_governed_change(
        self,
        record: IdentityRecord,
        *,
        change_id: str,
        approver_principal_id: str,
    ) -> None:
        """Write any field, including immutable ones. Records governed change in continuity."""
        self._save(record)
        ContinuityStream(self._sub).append(
            ContinuityEvent(
                kind="governed_identity_change",
                principal_id=approver_principal_id,
                payload={
                    "change_id": change_id,
                    "approver_principal_id": approver_principal_id,
                    "scope": "identity_record",
                },
            )
        )

    def load_relation_anchor(self, principal_id: str) -> RelationAnchorBinding | None:
        row = self._sub.connection.execute(
            "SELECT principal_id, trusted_identifiers_json, trust_evidence_json, "
            "authority_scope_json, channel_constraints_json, is_primary "
            "FROM relation_anchor_bindings WHERE principal_id = ?",
            (principal_id,),
        ).fetchone()
        if row is None:
            return None
        return RelationAnchorBinding(
            principal_id=row[0],
            trusted_identifiers=tuple(json.loads(row[1] or "[]")),
            trust_evidence=json.loads(row[2] or "{}"),
            authority_scope=tuple(json.loads(row[3] or "[]")),
            channel_constraints=json.loads(row[4] or "{}"),
            is_primary=bool(row[5]),
        )

    def write_via_governed_change_relation_anchor(
        self,
        binding: RelationAnchorBinding,
        *,
        change_id: str,
        approver_principal_id: str,
    ) -> None:
        """Identity-critical write of a relation anchor binding."""
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO relation_anchor_bindings("
            "principal_id, trusted_identifiers_json, trust_evidence_json, "
            "authority_scope_json, channel_constraints_json, is_primary, "
            "created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(principal_id) DO UPDATE SET "
            "trusted_identifiers_json=excluded.trusted_identifiers_json, "
            "trust_evidence_json=excluded.trust_evidence_json, "
            "authority_scope_json=excluded.authority_scope_json, "
            "channel_constraints_json=excluded.channel_constraints_json, "
            "is_primary=excluded.is_primary, "
            "updated_at=excluded.updated_at",
            (
                binding.principal_id,
                json.dumps(list(binding.trusted_identifiers), ensure_ascii=False),
                json.dumps(binding.trust_evidence, ensure_ascii=False),
                json.dumps(list(binding.authority_scope), ensure_ascii=False),
                json.dumps(binding.channel_constraints, ensure_ascii=False),
                1 if binding.is_primary else 0,
                now,
                now,
            ),
        )
        self._sub.connection.commit()
        ContinuityStream(self._sub).append(
            ContinuityEvent(
                kind="governed_identity_change",
                principal_id=approver_principal_id,
                payload={
                    "change_id": change_id,
                    "approver_principal_id": approver_principal_id,
                    "scope": "relation_anchor_binding",
                    "target_principal_id": binding.principal_id,
                },
            )
        )
