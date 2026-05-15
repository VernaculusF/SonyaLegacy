from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"

CURRENT_VERSION = 3


def apply_initial_schema(conn: sqlite3.Connection) -> None:
    """Apply schema DDL (idempotent via IF NOT EXISTS) and stamp current version."""
    conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)",
        (CURRENT_VERSION, now),
    )
    conn.commit()


def migrate_to_current(conn: sqlite3.Connection, current_version: int) -> int:
    """Apply forward migrations from `current_version` to CURRENT_VERSION.

    Returns the new version. Each step is idempotent (IF NOT EXISTS / ADD COLUMN
    with existence check).
    """
    if current_version >= CURRENT_VERSION:
        return current_version

    version = current_version

    if version == 1:
        # v1 → v2: add harness tables (IF NOT EXISTS makes it safe).
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (2, now),
        )
        conn.commit()
        version = 2

    if version == 2:
        # v2 → v3: add pending_intentions table + subject_state enrichment.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        # ALTER TABLE for columns that schema.sql can't add idempotently.
        _add_column_if_missing(conn, "subject_state", "emotional_vector_json", "TEXT NOT NULL DEFAULT '{}'")
        _add_column_if_missing(conn, "subject_state", "drift_signals_json", "TEXT NOT NULL DEFAULT '[]'")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (3, now),
        )
        conn.commit()
        version = 3

    if version < CURRENT_VERSION:
        raise RuntimeError(f"no migration path from version {version}")

    return version


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_type: str
) -> None:
    """Add a column to a table if it doesn't already exist."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()


def read_current_version(conn: sqlite3.Connection) -> int:
    """Return current schema_version. Returns 0 if table missing or empty."""
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return 0
        return int(row[0])
    except sqlite3.OperationalError:
        return 0
