from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"

CURRENT_VERSION = 16


def apply_initial_schema(conn: sqlite3.Connection) -> None:
    """Apply schema DDL (idempotent via IF NOT EXISTS) and stamp current version."""
    conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (?, ?)",
        (CURRENT_VERSION, now),
    )
    # v8: seed provider_settings single row if missing
    conn.execute(
        "INSERT OR IGNORE INTO provider_settings(id, active_provider, default_model, default_base_url, updated_at) "
        "VALUES (1, 'fireworks', 'accounts/fireworks/models/minimax-m2p7', 'https://api.fireworks.ai/inference/v1', ?)",
        (now,),
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

    if version == 3:
        # v3 → v4: add self_mod_proposals + self_mod_validation_results tables.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (4, now),
        )
        conn.commit()
        version = 4

    if version == 4:
        # v4 → v5: add skills + capability_gaps tables.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (5, now),
        )
        conn.commit()
        version = 5

    if version == 5:
        # v5 → v6: add episodic_events + semantic_facts tables.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (6, now),
        )
        conn.commit()
        version = 6

    if version == 6:
        # v6 → v7: add tasks table (long-running multi-session work).
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (7, now),
        )
        conn.commit()
        version = 7

    if version == 7:
        # v7 → v8: own key pool (provider_keys + provider_settings).
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        # Seed provider_settings single row
        conn.execute(
            "INSERT OR IGNORE INTO provider_settings(id, active_provider, default_model, default_base_url, updated_at) "
            "VALUES (1, 'fireworks', 'accounts/fireworks/models/minimax-m2p7', 'https://api.fireworks.ai/inference/v1', ?)",
            (now,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (8, now),
        )
        conn.commit()
        version = 8

    if version == 8:
        # v8 → v9: task scheduling + ownership columns.
        _add_column_if_missing(conn, "tasks", "created_by", "TEXT NOT NULL DEFAULT 'self'")
        _add_column_if_missing(conn, "tasks", "scheduled_for", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "tasks", "recurring_spec", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "tasks", "notify_mode", "TEXT NOT NULL DEFAULT 'progress'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_for ON tasks(scheduled_for)")
        # Existing tasks default to created_by='self' (their previous behaviour)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (9, now),
        )
        conn.commit()
        version = 9

    if version == 9:
        # v9 → v10: LLM call audit log.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (10, now),
        )
        conn.commit()
        version = 10

    if version == 10:
        # v10 → v11: provider_keys balance/quota snapshot columns.
        _add_column_if_missing(conn, "provider_keys", "account_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_keys", "balance_json", "TEXT NOT NULL DEFAULT '{}'")
        _add_column_if_missing(conn, "provider_keys", "balance_checked_at", "TEXT NOT NULL DEFAULT ''")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (11, now),
        )
        conn.commit()
        version = 11

    if version == 11:
        # v11 → v12: task session budget + handoff notes for cross-session continuity.
        _add_column_if_missing(conn, "tasks", "max_sessions", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "tasks", "sessions_used", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "tasks", "last_session_notes", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "tasks", "next_step_hint", "TEXT NOT NULL DEFAULT ''")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (12, now),
        )
        conn.commit()
        version = 12

    if version == 12:
        # v12 → v13: episodic embeddings for semantic recall.
        _add_column_if_missing(conn, "episodic_events", "embedding", "BLOB")
        _add_column_if_missing(conn, "episodic_events", "embedded_at", "TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_episodic_embedded_at ON episodic_events(embedded_at)")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (13, now),
        )
        conn.commit()
        version = 13

    if version == 13:
        # v13 → v14: sticker collection — captures stickers Sonya has seen
        # incoming from Ivan so she can re-send them via [STICKER: <emoji>].
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (14, now),
        )
        conn.commit()
        version = 14

    if version == 14:
        # v14 → v15: environment_state — Sonya records what she observes
        # about Ivan's situation (asleep, busy, etc) instead of the system
        # using clock-based heuristics.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (15, now),
        )
        conn.commit()
        version = 15

    if version == 15:
        # v15 → v16: persistent drive_state + goals table + tasks.parent_goal_id.
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO drive_state(id, boredom_analog, curiosity_analog, "
            "relational_focus, pending_debt, updated_at) VALUES (1, 0, 0, 0, 0, ?)",
            (now,),
        )
        _add_column_if_missing(conn, "tasks", "parent_goal_id", "TEXT NOT NULL DEFAULT ''")
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (16, now),
        )
        conn.commit()
        version = 16

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
