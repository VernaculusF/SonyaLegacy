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
    "is_credential_shaped_key",
    "record_ivan_activity",
]
