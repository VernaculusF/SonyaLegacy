from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sonya.state import Substrate


def test_fresh_substrate_creates_v2(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "s.db")
    try:
        # Fresh DB now creates at WRITABLE_VERSION (v3), but v2 tables must exist.
        assert sub.schema_version >= 2
        cursor = sub.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert {"harness_policy_rules", "approval_requests", "audit_events"}.issubset(tables)
    finally:
        sub.close()


def _create_v1_substrate(path: Path) -> None:
    """Manually create a v1 substrate to simulate an old DB on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE schema_version (
                version INTEGER NOT NULL PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE subject_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                active_principal_id TEXT,
                last_canonical_response_ref TEXT,
                active_channels_json TEXT NOT NULL DEFAULT '[]',
                pending_intentions_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE continuity_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                principal_id TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE continuity_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                seq_at_snapshot INTEGER NOT NULL,
                subject_state_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE identity_record (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                self_model_json TEXT NOT NULL DEFAULT '{}',
                things_not_to_betray_json TEXT NOT NULL DEFAULT '[]',
                identity_critical_traits_json TEXT NOT NULL DEFAULT '[]',
                drift_boundaries_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE relation_anchor_bindings (
                principal_id TEXT PRIMARY KEY,
                trusted_identifiers_json TEXT NOT NULL DEFAULT '[]',
                trust_evidence_json TEXT NOT NULL DEFAULT '{}',
                authority_scope_json TEXT NOT NULL DEFAULT '[]',
                channel_constraints_json TEXT NOT NULL DEFAULT '{}',
                is_primary INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE principals (
                principal_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                trusted_identifiers_json TEXT NOT NULL DEFAULT '[]',
                authority_scope_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            INSERT INTO schema_version(version, applied_at) VALUES (1, '2026-05-13T00:00:00');
            INSERT INTO principals(principal_id, display_name, trusted_identifiers_json, authority_scope_json, created_at)
                VALUES ('legacy', 'Legacy', '["tg:1"]', '[]', '2026-05-13T00:00:00');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_v1_db_migrates_to_v2_preserving_data(tmp_path: Path) -> None:
    db = tmp_path / "old.db"
    _create_v1_substrate(db)

    sub = Substrate.open(db)
    try:
        # v1 now migrates all the way to v3 (through v2).
        assert sub.schema_version >= 2
        cursor = sub.connection.execute("SELECT principal_id FROM principals")
        rows = [r[0] for r in cursor.fetchall()]
        assert "legacy" in rows
        cursor = sub.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert {"harness_policy_rules", "approval_requests", "audit_events"}.issubset(tables)
    finally:
        sub.close()


def test_v1_read_only_open_succeeds(tmp_path: Path) -> None:
    db = tmp_path / "old.db"
    _create_v1_substrate(db)
    sub = Substrate.open(db, read_only=True)
    try:
        assert sub.schema_version == 1
    finally:
        sub.close()


def test_unknown_future_version_refuses(tmp_path: Path) -> None:
    db = tmp_path / "future.db"
    Substrate.open(db).close()
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE schema_version SET version = 999")
        conn.commit()
    from sonya.state import SubstrateVersionError
    with pytest.raises(SubstrateVersionError):
        Substrate.open(db)
