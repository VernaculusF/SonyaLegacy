"""Current, sourced assertions about Sonya's world.

Unlike durable memory, situational assertions are explicitly time-sensitive.
They preserve provenance, confidence, expiry, and supersession so stale
observations do not silently remain current forever.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypedDict

from sonya.state.substrate import Substrate


class TrustContext(TypedDict, total=False):
    authority_level: str
    trust_signals: list[str]



_CREDENTIAL_MARKERS = (
    "apikey",
    "api_key",
    "token",
    "secret",
    "credential",
    "password",
    "passwd",
)

_IVAN_UNAVAILABLE_MARKERS = (
    "спит",
    "сплю",
    "asleep",
    "sleeping",
    "занят",
    "busy",
    "не беспокоить",
    "dnd",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_credential_shaped_key(key: str) -> bool:
    normalized = (key or "").strip().lower()
    return any(marker in normalized for marker in _CREDENTIAL_MARKERS)


@dataclass(frozen=True, slots=True)
class SituationalAssertion:
    assertion_id: str
    subject: str
    predicate: str
    value: str
    source: str
    source_ref: str
    confidence: float
    observed_at: str
    expires_at: str
    scope: str
    visibility: str
    supersedes_id: str
    metadata: dict[str, Any]


class SituationalStore:
    """Current-view and history operations for situational assertions."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def assert_fact(
        self,
        *,
        subject: str,
        predicate: str,
        value: str,
        source: str = "observation",
        source_ref: str = "",
        confidence: float = 0.5,
        observed_at: str = "",
        expires_at: str = "",
        scope: str = "global",
        visibility: str = "normal",
        metadata: dict[str, Any] | None = None,
        trust_context: TrustContext | None = None,
        invalidates_ids: list[str] | None = None,
        force_repromote: bool = False,
    ) -> SituationalAssertion:
        subject = (subject or "").strip()
        predicate = (predicate or "").strip()
        scope = (scope or "global").strip()
        source = (source or "").strip().lower()
        if not subject:
            raise ValueError("situational subject is required")
        if not predicate:
            raise ValueError("situational predicate is required")
        if is_credential_shaped_key(predicate):
            raise ValueError("credentials must use protected secret storage")
            
        allowed_sources = {"observation", "inference", "hypothesis", "imagination", "ivan_said", "system", "confirmed_fact", "incoming.atrium_dialog"}
        if source not in allowed_sources and not source.startswith("incoming."):
            raise ValueError(f"invalid situational source: '{source}'. must be one of {allowed_sources} or start with incoming.")
        
        confidence = max(0.0, min(1.0, float(confidence)))
        observed_at = observed_at or _utc_now_iso()
        assertion_id = f"wa-{uuid.uuid4().hex[:16]}"
        previous = self._sub.connection.execute(
            "SELECT assertion_id FROM situational_assertions "
            "WHERE subject = ? AND predicate = ? AND scope = ? AND active = 1 "
            "ORDER BY observed_at DESC LIMIT 1",
            (subject, predicate, scope),
        ).fetchone()
        supersedes_id = previous[0] if previous else ""
        if supersedes_id:
            # Check for silent re-promotion of a refuted fact
            prev_row = self._sub.connection.execute(
                "SELECT value, metadata_json FROM situational_assertions WHERE assertion_id = ?",
                (supersedes_id,)
            ).fetchone()
            if prev_row and prev_row[0] == "[REFUTED]" and not force_repromote:
                prev_md = json.loads(prev_row[1] or "{}")
                if prev_md.get("refuted_value") == value:
                    raise ValueError(f"Cannot silently re-promote refuted fact '{subject}.{predicate}={value}'. Explicitly override with force_repromote=True or assert a different value.")

            self._sub.connection.execute(
                "UPDATE situational_assertions SET active = 0, superseded_by = ? "
                "WHERE assertion_id = ?",
                (assertion_id, supersedes_id),
            )
        
        if invalidates_ids:
            for inv_id in invalidates_ids:
                if inv_id == supersedes_id:
                    continue
                self._sub.connection.execute(
                    "UPDATE situational_assertions SET active = 0, superseded_by = ? "
                    "WHERE assertion_id = ?",
                    (assertion_id, inv_id),
                )
        final_metadata = metadata or {}
        if trust_context:
            final_metadata["trust"] = trust_context

        self._sub.connection.execute(
            "INSERT INTO situational_assertions("
            "assertion_id, subject, predicate, value, source, source_ref, confidence, "
            "observed_at, expires_at, scope, visibility, active, supersedes_id, "
            "superseded_by, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, '', ?)",
            (
                assertion_id,
                subject,
                predicate,
                value,
                source,
                source_ref,
                confidence,
                observed_at,
                expires_at,
                scope,
                visibility,
                supersedes_id,
                json.dumps(final_metadata, ensure_ascii=False),
            ),
        )
        self._sub.connection.commit()
        row = self._sub.connection.execute(
            "SELECT assertion_id, subject, predicate, value, source, source_ref, "
            "confidence, observed_at, expires_at, scope, visibility, supersedes_id, "
            "metadata_json FROM situational_assertions WHERE assertion_id = ?",
            (assertion_id,),
        ).fetchone()
        return _row_to_assertion(row)

    def get_current(
        self, *, subject: str, predicate: str, scope: str = "global"
    ) -> SituationalAssertion | None:
        row = self._sub.connection.execute(
            "SELECT assertion_id, subject, predicate, value, source, source_ref, "
            "confidence, observed_at, expires_at, scope, visibility, supersedes_id, "
            "metadata_json FROM situational_assertions "
            "WHERE subject = ? AND predicate = ? AND scope = ? AND active = 1 "
            "AND value != '[REFUTED]' "
            "AND (expires_at = '' OR expires_at > ?) "
            "ORDER BY observed_at DESC LIMIT 1",
            (subject, predicate, scope, _utc_now_iso()),
        ).fetchone()
        return _row_to_assertion(row) if row else None

    def list_current(
        self, *, subject: str | None = None, scope: str = "global"
    ) -> list[SituationalAssertion]:
        params: list[Any] = [scope, _utc_now_iso()]
        subject_sql = ""
        if subject is not None:
            subject_sql = "AND subject = ? "
            params.append(subject)
        rows = self._sub.connection.execute(
            "SELECT assertion_id, subject, predicate, value, source, source_ref, "
            "confidence, observed_at, expires_at, scope, visibility, supersedes_id, "
            "metadata_json FROM situational_assertions "
            "WHERE scope = ? AND active = 1 AND value != '[REFUTED]' AND (expires_at = '' OR expires_at > ?) "
            f"{subject_sql}ORDER BY subject, predicate",
            tuple(params),
        ).fetchall()
        return [_row_to_assertion(row) for row in rows]

    def retract(self, *, subject: str, predicate: str, scope: str = "global") -> bool:
        cur = self._sub.connection.execute(
            "UPDATE situational_assertions SET active = 0 "
            "WHERE subject = ? AND predicate = ? AND scope = ? AND active = 1",
            (subject, predicate, scope),
        )
        self._sub.connection.commit()
        return cur.rowcount > 0

    def invalidate_predicate(self, *, subject: str, predicate: str, reason: str, scope: str = "global") -> bool:
        cur = self._sub.connection.execute(
            "UPDATE situational_assertions SET active = 0, superseded_by = ? "
            "WHERE subject = ? AND predicate = ? AND scope = ? AND active = 1",
            (f"invalidated_{reason}", subject, predicate, scope),
        )
        self._sub.connection.commit()
        return cur.rowcount > 0

    def get_assertion_history(self, assertion_id: str) -> list[SituationalAssertion]:
        """Returns the chronological history of how an assertion was updated/refuted/invalidated.
        Traverses the graph of `supersedes_id` and `superseded_by` to find the entire connected component.
        """
        component_ids = set()
        
        def traverse(aid: str) -> None:
            if aid in component_ids:
                return
            component_ids.add(aid)
            
            # Find what this assertion supersedes (backward)
            row = self._sub.connection.execute(
                "SELECT supersedes_id, superseded_by FROM situational_assertions WHERE assertion_id = ?",
                (aid,)
            ).fetchone()
            if row:
                if row[0]: traverse(row[0])
                if row[1]: traverse(row[1])
                
            # Find what supersedes this assertion (forward)
            rows = self._sub.connection.execute(
                "SELECT assertion_id FROM situational_assertions WHERE supersedes_id = ? OR superseded_by = ?",
                (aid, aid)
            ).fetchall()
            for (next_id,) in rows:
                traverse(next_id)
                
        traverse(assertion_id)
        
        if not component_ids:
            return []
            
        placeholders = ",".join("?" for _ in component_ids)
        rows = self._sub.connection.execute(
            f"SELECT assertion_id, subject, predicate, value, source, source_ref, "
            f"confidence, observed_at, expires_at, scope, visibility, supersedes_id, "
            f"metadata_json FROM situational_assertions WHERE assertion_id IN ({placeholders}) "
            f"ORDER BY observed_at",
            tuple(component_ids)
        ).fetchall()
        
        return [
            SituationalAssertion(
                assertion_id=r[0],
                subject=r[1],
                predicate=r[2],
                value=r[3],
                source=r[4],
                source_ref=r[5],
                confidence=r[6],
                observed_at=r[7],
                expires_at=r[8],
                scope=r[9],
                visibility=r[10],
                supersedes_id=r[11],
                metadata=json.loads(r[12] or "{}"),
            )
            for r in rows
        ]

    def refute_fact(self, *, subject: str, predicate: str, reason: str, source: str = "inference", source_ref: str = "", scope: str = "global") -> SituationalAssertion:
        current = self.get_current(subject=subject, predicate=predicate, scope=scope)
        old_value = current.value if current else ""
        metadata = {"refuted_value": old_value, "reason": reason}
        return self.assert_fact(
            subject=subject,
            predicate=predicate,
            value="[REFUTED]",
            source=source,
            source_ref=source_ref,
            scope=scope,
            metadata=metadata,
            force_repromote=True
        )


@dataclass(frozen=True, slots=True)
class SituationalMetricsResult:
    total_active: int
    stale_active: int
    low_confidence: int
    invalidated_count: int
    frequent_sources: list[tuple[str, int]]
    invalidated_sources: list[tuple[str, int]]


class SituationalMetrics:
    """Computes quality metrics for the SituationalModel."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def calculate(self, scope: str = "global") -> SituationalMetricsResult:
        now_iso = _utc_now_iso()
        
        # Total active assertions (whether expired or not)
        total = self._sub.connection.execute(
            "SELECT COUNT(*) FROM situational_assertions WHERE active = 1 AND value != '[REFUTED]' AND scope = ?",
            (scope,)
        ).fetchone()[0]

        # Stale active: active = 1 but expires_at < now (and expires_at != '')
        stale = self._sub.connection.execute(
            "SELECT COUNT(*) FROM situational_assertions "
            "WHERE active = 1 AND value != '[REFUTED]' AND scope = ? AND expires_at != '' AND expires_at < ?",
            (scope, now_iso)
        ).fetchone()[0]

        # Low confidence: active = 1 and confidence < 0.5
        low_conf = self._sub.connection.execute(
            "SELECT COUNT(*) FROM situational_assertions "
            "WHERE active = 1 AND value != '[REFUTED]' AND scope = ? AND confidence < 0.5",
            (scope,)
        ).fetchone()[0]

        # Invalidated/Superseded assertions: active = 0 and superseded_by != ''
        invalidated = self._sub.connection.execute(
            "SELECT COUNT(*) FROM situational_assertions "
            "WHERE active = 0 AND scope = ? AND superseded_by != ''",
            (scope,)
        ).fetchone()[0]

        # Sources that provided currently active assertions (most frequent first)
        freq_sources = self._sub.connection.execute(
            "SELECT source, COUNT(*) as cnt FROM situational_assertions "
            "WHERE active = 1 AND value != '[REFUTED]' AND scope = ? "
            "GROUP BY source ORDER BY cnt DESC LIMIT 5",
            (scope,)
        ).fetchall()

        # Sources that frequently provided assertions which got invalidated
        inv_sources = self._sub.connection.execute(
            "SELECT source, COUNT(*) as cnt FROM situational_assertions "
            "WHERE active = 0 AND scope = ? AND superseded_by != '' "
            "GROUP BY source ORDER BY cnt DESC LIMIT 5",
            (scope,)
        ).fetchall()

        return SituationalMetricsResult(
            total_active=total,
            stale_active=stale,
            low_confidence=low_conf,
            invalidated_count=invalidated,
            frequent_sources=[(row[0], row[1]) for row in freq_sources],
            invalidated_sources=[(row[0], row[1]) for row in inv_sources],
        )


def record_ivan_activity(
    substrate: Substrate,
    *,
    source: str,
    source_ref: str = "",
    stream: object | None = None,
) -> SituationalAssertion | None:
    """Use fresh Ivan activity to invalidate stale asleep/busy status."""

    store = SituationalStore(substrate)
    current = store.get_current(subject="ivan", predicate="ivan_status")
    if current is None:
        return None
    if not any(marker in current.value.lower() for marker in _IVAN_UNAVAILABLE_MARKERS):
        return None
    updated = store.assert_fact(
        subject="ivan",
        predicate="ivan_status",
        value="active",
        source=source,
        source_ref=source_ref,
        confidence=0.95,
        metadata={
            "reason": "incoming_ivan_message_invalidated_unavailable_status",
            "previous_assertion_id": current.assertion_id,
            "previous_value": current.value,
        },
    )
    if stream is not None:
        try:
            from sonya.state.continuity_stream import ContinuityEvent

            stream.append(ContinuityEvent(
                kind="world_state.ivan_activity_invalidated_status",
                principal_id="ivan",
                payload={
                    "previous_assertion_id": current.assertion_id,
                    "previous_value": current.value,
                    "new_assertion_id": updated.assertion_id,
                    "new_value": updated.value,
                    "source": source,
                    "source_ref": source_ref,
                },
            ))
        except Exception:
            pass
    return updated


def _row_to_assertion(row: Any) -> SituationalAssertion:
    return SituationalAssertion(
        assertion_id=row[0],
        subject=row[1],
        predicate=row[2],
        value=row[3],
        source=row[4],
        source_ref=row[5],
        confidence=float(row[6]),
        observed_at=row[7],
        expires_at=row[8],
        scope=row[9],
        visibility=row[10],
        supersedes_id=row[11],
        metadata=json.loads(row[12] or "{}"),
    )


__all__ = [
    "SituationalAssertion",
    "SituationalStore",
    "SituationalMetrics",
    "SituationalMetricsResult",
    "is_credential_shaped_key",
    "record_ivan_activity",
    "CredentialExposure",
    "CredentialExposureStore",
]
@dataclass(frozen=True, slots=True)
class CredentialExposure:
    exposure_id: str
    source_kind: str
    source_ref: str
    credential_label: str
    discovered_at: str
    status: str
    metadata: dict[str, Any]

class CredentialExposureStore:
    def __init__(self, sub: Substrate) -> None:
        self._sub = sub

    def record_exposure(
        self,
        *,
        source_kind: str,
        credential_label: str,
        source_ref: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CredentialExposure:
        exposure_id = f"ce-{uuid.uuid4().hex[:16]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO credential_exposures("
            "exposure_id, source_kind, source_ref, credential_label, "
            "discovered_at, status, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, 'unresolved', ?)",
            (
                exposure_id,
                source_kind,
                source_ref,
                credential_label,
                now,
                json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        self._sub.connection.commit()
        return CredentialExposure(
            exposure_id=exposure_id,
            source_kind=source_kind,
            source_ref=source_ref,
            credential_label=credential_label,
            discovered_at=now,
            status="unresolved",
            metadata=metadata or {},
        )

    def list_unresolved(self) -> list[CredentialExposure]:
        rows = self._sub.connection.execute(
            "SELECT exposure_id, source_kind, source_ref, credential_label, "
            "discovered_at, status, metadata_json "
            "FROM credential_exposures WHERE status = 'unresolved' "
            "ORDER BY discovered_at DESC"
        ).fetchall()
        
        res = []
        for row in rows:
            res.append(CredentialExposure(
                exposure_id=row[0],
                source_kind=row[1],
                source_ref=row[2],
                credential_label=row[3],
                discovered_at=row[4],
                status=row[5],
                metadata=json.loads(row[6]),
            ))
        return res

    def resolve(self, exposure_id: str, note: str = "") -> bool:
        cur = self._sub.connection.execute(
            "UPDATE credential_exposures SET status = 'resolved' "
            "WHERE exposure_id = ? AND status = 'unresolved'",
            (exposure_id,)
        )
        if cur.rowcount > 0 and note:
            # Optionally update metadata with resolution note
            row = self._sub.connection.execute(
                "SELECT metadata_json FROM credential_exposures WHERE exposure_id = ?",
                (exposure_id,)
            ).fetchone()
            if row:
                md = json.loads(row[0])
                md["resolution_note"] = note
                self._sub.connection.execute(
                    "UPDATE credential_exposures SET metadata_json = ? WHERE exposure_id = ?",
                    (json.dumps(md, ensure_ascii=False), exposure_id)
                )
        self._sub.connection.commit()
        return cur.rowcount > 0
