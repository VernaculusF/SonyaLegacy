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
from typing import Any

from sonya.state.substrate import Substrate


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
        invalidates_ids: list[str] | None = None,
    ) -> SituationalAssertion:
        subject = (subject or "").strip()
        predicate = (predicate or "").strip()
        scope = (scope or "global").strip()
        if not subject:
            raise ValueError("situational subject is required")
        if not predicate:
            raise ValueError("situational predicate is required")
        if is_credential_shaped_key(predicate):
            raise ValueError("credentials must use protected secret storage")
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
                json.dumps(metadata or {}, ensure_ascii=False),
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
            "WHERE scope = ? AND active = 1 AND (expires_at = '' OR expires_at > ?) "
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
            "SELECT COUNT(*) FROM situational_assertions WHERE active = 1 AND scope = ?",
            (scope,)
        ).fetchone()[0]

        # Stale active: active = 1 but expires_at < now (and expires_at != '')
        stale = self._sub.connection.execute(
            "SELECT COUNT(*) FROM situational_assertions "
            "WHERE active = 1 AND scope = ? AND expires_at != '' AND expires_at < ?",
            (scope, now_iso)
        ).fetchone()[0]

        # Low confidence: active = 1 and confidence < 0.5
        low_conf = self._sub.connection.execute(
            "SELECT COUNT(*) FROM situational_assertions "
            "WHERE active = 1 AND scope = ? AND confidence < 0.5",
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
            "WHERE active = 1 AND scope = ? "
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
