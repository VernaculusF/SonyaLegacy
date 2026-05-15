from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sonya.state.substrate import Substrate


@dataclass(frozen=True, slots=True)
class SubjectState:
    """Current snapshot of who Sonya is paying attention to and what is open."""

    active_principal_id: str | None = None
    last_canonical_response_ref: str | None = None
    active_channels: tuple[str, ...] = field(default_factory=tuple)
    pending_intentions: tuple[str, ...] = field(default_factory=tuple)
    emotional_vector: dict[str, Any] = field(default_factory=dict)
    drift_signals: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ContinuitySnapshotRef:
    snapshot_id: str
    seq_at_snapshot: int


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SubjectStateStore:
    """Reads/writes the single-row subject_state table."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def load(self) -> SubjectState:
        row = self._sub.connection.execute(
            "SELECT active_principal_id, last_canonical_response_ref, "
            "active_channels_json, pending_intentions_json, "
            "emotional_vector_json, drift_signals_json "
            "FROM subject_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return SubjectState()
        return SubjectState(
            active_principal_id=row[0],
            last_canonical_response_ref=row[1],
            active_channels=tuple(json.loads(row[2] or "[]")),
            pending_intentions=tuple(json.loads(row[3] or "[]")),
            emotional_vector=json.loads(row[4] or "{}"),
            drift_signals=tuple(json.loads(row[5] or "[]")),
        )

    def save(self, state: SubjectState) -> None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO subject_state(id, active_principal_id, last_canonical_response_ref, "
            "active_channels_json, pending_intentions_json, emotional_vector_json, "
            "drift_signals_json, updated_at) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "active_principal_id=excluded.active_principal_id, "
            "last_canonical_response_ref=excluded.last_canonical_response_ref, "
            "active_channels_json=excluded.active_channels_json, "
            "pending_intentions_json=excluded.pending_intentions_json, "
            "emotional_vector_json=excluded.emotional_vector_json, "
            "drift_signals_json=excluded.drift_signals_json, "
            "updated_at=excluded.updated_at",
            (
                state.active_principal_id,
                state.last_canonical_response_ref,
                json.dumps(list(state.active_channels), ensure_ascii=False),
                json.dumps(list(state.pending_intentions), ensure_ascii=False),
                json.dumps(state.emotional_vector, ensure_ascii=False),
                json.dumps(list(state.drift_signals), ensure_ascii=False),
                now,
            ),
        )
        self._sub.connection.commit()

    def create_snapshot(self, snapshot_id: str) -> ContinuitySnapshotRef:
        from sonya.state.continuity_stream import ContinuityStream

        seq = ContinuityStream(self._sub).latest_seq()
        state = self.load()
        payload = json.dumps(
            {
                "active_principal_id": state.active_principal_id,
                "last_canonical_response_ref": state.last_canonical_response_ref,
                "active_channels": list(state.active_channels),
                "pending_intentions": list(state.pending_intentions),
                "emotional_vector": state.emotional_vector,
                "drift_signals": list(state.drift_signals),
            },
            ensure_ascii=False,
        )
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO continuity_snapshots(snapshot_id, seq_at_snapshot, "
            "subject_state_json, created_at) VALUES (?, ?, ?, ?)",
            (snapshot_id, seq, payload, now),
        )
        self._sub.connection.commit()
        return ContinuitySnapshotRef(snapshot_id=snapshot_id, seq_at_snapshot=seq)

    def restore_from_snapshot(self, snapshot_id: str) -> None:
        row = self._sub.connection.execute(
            "SELECT subject_state_json FROM continuity_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"snapshot {snapshot_id!r} not found")
        data = json.loads(row[0])
        self.save(
            SubjectState(
                active_principal_id=data.get("active_principal_id"),
                last_canonical_response_ref=data.get("last_canonical_response_ref"),
                active_channels=tuple(data.get("active_channels", [])),
                pending_intentions=tuple(data.get("pending_intentions", [])),
                emotional_vector=data.get("emotional_vector", {}),
                drift_signals=tuple(data.get("drift_signals", [])),
            )
        )
