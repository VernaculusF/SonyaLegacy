from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from sonya.state import Substrate, SubstrateVersionError


def _create_v2_db(path: Path) -> None:
    """Create a minimal v2 substrate manually."""
    conn = sqlite3.connect(path)
    # Minimal v2 schema: schema_version + subject_state + continuity_events + identity_record
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (2, '2026-01-01T00:00:00+00:00');

        CREATE TABLE subject_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            active_principal_id TEXT,
            last_canonical_response_ref TEXT,
            active_channels_json TEXT NOT NULL DEFAULT '[]',
            pending_intentions_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        );
        INSERT INTO subject_state(id, active_principal_id, active_channels_json, pending_intentions_json, updated_at)
        VALUES (1, 'ivan', '["telegram"]', '["write-report"]', '2026-01-01T00:00:00+00:00');

        CREATE TABLE continuity_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            principal_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        INSERT INTO continuity_events(kind, principal_id, payload_json, created_at)
        VALUES ('test_event', 'ivan', '{}', '2026-01-01T00:00:00+00:00');

        CREATE TABLE identity_record (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            self_model_json TEXT NOT NULL DEFAULT '{}',
            things_not_to_betray_json TEXT NOT NULL DEFAULT '[]',
            identity_critical_traits_json TEXT NOT NULL DEFAULT '[]',
            drift_boundaries_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE principals (
            principal_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            trusted_identifiers_json TEXT NOT NULL DEFAULT '[]',
            authority_scope_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
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

        CREATE TABLE continuity_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            seq_at_snapshot INTEGER NOT NULL,
            subject_state_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE harness_policy_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            decision TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE approval_requests (
            request_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            action TEXT NOT NULL,
            scope TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            decided_at TEXT,
            decided_by_principal_id TEXT
        );

        CREATE TABLE audit_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            principal_id TEXT,
            action TEXT NOT NULL,
            decision TEXT NOT NULL,
            scope TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
    """)
    conn.close()


def test_fresh_substrate_creates_v3(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "s.db")
    assert sub.schema_version == 3
    # pending_intentions table exists
    row = sub.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_intentions'"
    ).fetchone()
    assert row is not None
    # subject_state has new columns
    cursor = sub.connection.execute("PRAGMA table_info(subject_state)")
    columns = {r[1] for r in cursor.fetchall()}
    assert "emotional_vector_json" in columns
    assert "drift_signals_json" in columns
    sub.close()


def test_v2_db_migrates_to_v3_preserving_data(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    _create_v2_db(db)

    sub = Substrate.open(db)
    assert sub.schema_version == 3

    # Old data preserved
    row = sub.connection.execute(
        "SELECT active_principal_id FROM subject_state WHERE id = 1"
    ).fetchone()
    assert row[0] == "ivan"

    row = sub.connection.execute(
        "SELECT kind FROM continuity_events WHERE seq = 1"
    ).fetchone()
    assert row[0] == "test_event"

    # New table exists
    row = sub.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pending_intentions'"
    ).fetchone()
    assert row is not None

    # New columns have defaults
    row = sub.connection.execute(
        "SELECT emotional_vector_json, drift_signals_json FROM subject_state WHERE id = 1"
    ).fetchone()
    assert row[0] == "{}"
    assert row[1] == "[]"

    sub.close()


def test_v1_to_v3_migration_chain(tmp_path: Path) -> None:
    """v1 DB should migrate through v2 to v3."""
    db = tmp_path / "s.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (1, '2026-01-01T00:00:00+00:00');

        CREATE TABLE subject_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            active_principal_id TEXT,
            last_canonical_response_ref TEXT,
            active_channels_json TEXT NOT NULL DEFAULT '[]',
            pending_intentions_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        );
        INSERT INTO subject_state(id, active_channels_json, pending_intentions_json, updated_at)
        VALUES (1, '[]', '[]', '2026-01-01T00:00:00+00:00');

        CREATE TABLE continuity_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            principal_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
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

        CREATE TABLE principals (
            principal_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            trusted_identifiers_json TEXT NOT NULL DEFAULT '[]',
            authority_scope_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
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

        CREATE TABLE continuity_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            seq_at_snapshot INTEGER NOT NULL,
            subject_state_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.close()

    sub = Substrate.open(db)
    assert sub.schema_version == 3
    # All v2 + v3 tables exist
    tables = {
        row[0]
        for row in sub.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "harness_policy_rules" in tables
    assert "approval_requests" in tables
    assert "audit_events" in tables
    assert "pending_intentions" in tables
    sub.close()


def test_read_only_open_v2_succeeds(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    _create_v2_db(db)
    sub = Substrate.open(db, read_only=True)
    assert sub.schema_version == 2
    sub.close()
