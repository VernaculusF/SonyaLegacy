from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"

CURRENT_VERSION = 25


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


def ensure_critical_schema(conn: sqlite3.Connection) -> None:
    """Repair columns that current runtime assumes even on stamped DBs.

    Production once reached the current schema_version while missing columns
    that were added by ALTER migrations. A stamped DB skips forward migrations,
    so these idempotent guards run on every writable open.
    """
    _add_column_if_missing(conn, "provider_keys", "slot", "TEXT NOT NULL DEFAULT 'text'")
    _add_column_if_missing(conn, "provider_settings", "vision_provider", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_settings", "vision_model", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_settings", "vision_base_url", "TEXT NOT NULL DEFAULT ''")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subagent_tasks (
            subagent_id TEXT PRIMARY KEY,
            task TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            max_steps INTEGER NOT NULL DEFAULT 6,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT NOT NULL DEFAULT '',
            steps_taken INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT ''
        );
    """)
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
        # Visual memory: phash column for image dedup
        _add_column_if_missing(conn, "episodic_events", "media_phash", "TEXT NOT NULL DEFAULT ''")
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (16, now),
        )
        conn.commit()
        version = 16

    if version == 16:
        # v16 → v17: multi-model routing — slot column on provider_keys.
        # slot = comma-separated list of purposes: text,vision,voice,video,image_gen
        # Existing keys default to 'text'. Routing columns on provider_settings
        # are kept for backward compat but unused by code.
        _add_column_if_missing(conn, "provider_keys", "slot", "TEXT NOT NULL DEFAULT 'text'")
        # Legacy columns (kept, not used — harmless dead weight)
        _add_column_if_missing(conn, "provider_settings", "vision_provider", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "vision_model", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "vision_base_url", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "voice_provider", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "voice_model", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "voice_base_url", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "video_provider", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "video_model", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "video_base_url", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "image_gen_provider", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "image_gen_model", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "provider_settings", "image_gen_base_url", "TEXT NOT NULL DEFAULT ''")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (17, now),
        )
        conn.commit()
        version = 17

    if version == 17:
        # v17 → v18: goals table for long-term goal hierarchy (Stage 5).
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                goal_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                priority INTEGER NOT NULL DEFAULT 0,
                parent_goal_id TEXT DEFAULT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT DEFAULT NULL,
                FOREIGN KEY (parent_goal_id) REFERENCES goals(goal_id)
            );
        """)
        _add_column_if_missing(conn, "goals", "parent_goal_id", "TEXT DEFAULT NULL")
        _add_column_if_missing(conn, "goals", "completed_at", "TEXT DEFAULT NULL")
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (18, now),
        )
        conn.commit()
        version = 18

    if version == 18:
        # v18 → v19: stuck_loop_count column on tasks. Sonya added this
        # field in `models.py` and wired increment_stuck_loop_count via
        # selfmod commit a09cd49 (2026-05-28 ~07:13 UTC), but the column
        # itself was added to the production substrate via raw ALTER TABLE
        # in the same selfmod session. schema.sql was missed by that pass.
        # This migration brings fresh installs and any other substrate up
        # to par. Idempotent — _add_column_if_missing skips if present.
        _add_column_if_missing(
            conn, "tasks", "stuck_loop_count",
            "INTEGER NOT NULL DEFAULT 0",
        )
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (19, now),
        )
        conn.commit()
        version = 19

    if version == 19:
        # v19 → v20: Atrium Этап 0. Channel-aware multichannel output.
        #
        # `continuity_events.channel` — копия `payload.channel` для SQL-фильтрации
        # без парсинга JSON в WS feed (важно для latency).
        # `continuity_events.private` — копия `payload.private` для быстрого
        # exclude из feed (right_to_inner_privacy implementation).
        # `subject_state.current_focus / current_outfit / current_expression /
        # mood_tint` — поля которыми Соня управляет напрямую через mind.focus,
        # body.expression и т.д. (replace, не append). Source-of-truth для
        # Avatar / Room view рендеринга.
        # См. docs/atrium/EVENT_SCHEMA.md §1.
        _add_column_if_missing(conn, "continuity_events", "channel", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "continuity_events", "private", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "subject_state", "current_focus", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "subject_state", "current_outfit", "TEXT NOT NULL DEFAULT 'home'")
        _add_column_if_missing(conn, "subject_state", "current_expression", "TEXT NOT NULL DEFAULT 'neutral'")
        _add_column_if_missing(conn, "subject_state", "mood_tint", "TEXT NOT NULL DEFAULT 'neutral'")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_continuity_channel ON continuity_events(channel)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_continuity_private ON continuity_events(private)")
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (20, now),
        )
        conn.commit()
        version = 20

    if version == 20:
        # v20 → v21: explicit task urgency column. Replaces is_urgent()
        # heuristic-only with a stored field that survives schema bumps and
        # can be set by Sonya / Ivan directly. Default 'normal' so existing
        # rows behave the same as before until classified.
        _add_column_if_missing(conn, "tasks", "urgency", "TEXT NOT NULL DEFAULT 'normal'")
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_urgency ON tasks(urgency)")
        except sqlite3.OperationalError:
            pass  # tasks table not present in this substrate
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (21, now),
        )
        conn.commit()
        version = 21

    if version == 21:
        # v21 → v22: skills.module_path column for runtime skill registration.
        # Lets Sonya register a new skill (write code → register row →
        # executor imports & runs) without us hardcoding the module dotted
        # path in `skills/executor.py::_BUILTIN_SKILLS`. Legacy rows keep
        # working because the executor falls back to the hardcoded dict
        # when module_path is empty.
        _add_column_if_missing(conn, "skills", "module_path", "TEXT NOT NULL DEFAULT ''")
        # Backfill module_path for the 3 legacy builtin skills so freshly
        # migrated substrates don't need a re-register call.
        for sid, mpath in (
            ("skill-memory-search", "sonya.skills.builtins.memory_search"),
            ("skill-identity-check", "sonya.skills.builtins.identity_check"),
            ("skill-dialog-tone", "sonya.skills.builtins.dialog_tone"),
        ):
            try:
                conn.execute(
                    "UPDATE skills SET module_path = ? "
                    "WHERE skill_id = ? AND (module_path IS NULL OR module_path = '')",
                    (mpath, sid),
                )
            except sqlite3.OperationalError:
                pass
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (22, now),
        )
        conn.commit()
        version = 22

    if version == 22:
        # v22 → v23: selfmod_outcomes — feedback loop closure on self-improvement.
        #
        # Schema was in schema.sql since v16-era but never wired through a
        # migration; existing v22 substrates are missing the table. v23 creates
        # it idempotently, plus backfills baseline rows for any recent
        # `self_mod.confirmed_stable` proposals so Sonya immediately gets
        # feedback on changes that landed before this column existed.
        #
        # Watchdog already calls record_baseline → check_pending_outcomes is
        # already wired in internal_loop. v23 adds the storage so those calls
        # don't silently swallow IntegrityError.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS selfmod_outcomes (
                proposal_id TEXT PRIMARY KEY,
                target_module TEXT NOT NULL,
                confirmed_at TEXT NOT NULL,
                baseline_errors_7d INTEGER NOT NULL DEFAULT 0,
                baseline_tokens_7d INTEGER NOT NULL DEFAULT 0,
                measure_at TEXT NOT NULL DEFAULT '',
                measured_errors_7d INTEGER,
                measured_tokens_7d INTEGER,
                outcome TEXT NOT NULL DEFAULT 'pending',
                measured_at TEXT NOT NULL DEFAULT ''
            );
        """)
        # Backfill: any APPLIED proposal in the last 14 days that doesn't
        # already have an outcome row gets one. Baseline numbers are
        # measured at backfill-time over the 7 days BEFORE confirmed_at.
        try:
            from datetime import timedelta as _td
            cutoff_iso = (datetime.now(timezone.utc) - _td(days=14)).isoformat()
            applied = conn.execute(
                "SELECT proposal_id, target_module, updated_at FROM self_mod_proposals "
                "WHERE status = 'applied' AND updated_at > ? ORDER BY updated_at ASC",
                (cutoff_iso,),
            ).fetchall()
            for pid, target, applied_at in applied:
                exists = conn.execute(
                    "SELECT 1 FROM selfmod_outcomes WHERE proposal_id = ?", (pid,),
                ).fetchone()
                if exists:
                    continue
                # Baseline window = 7 days BEFORE applied_at.
                try:
                    apply_dt = datetime.fromisoformat(applied_at)
                except Exception:
                    apply_dt = datetime.now(timezone.utc)
                if apply_dt.tzinfo is None:
                    apply_dt = apply_dt.replace(tzinfo=timezone.utc)
                baseline_since = (apply_dt - _td(days=7)).isoformat()
                measure_at = (apply_dt + _td(days=7)).isoformat()
                err_row = conn.execute(
                    "SELECT COUNT(*) FROM continuity_events "
                    "WHERE created_at >= ? AND created_at < ? AND kind IN "
                    "('internal.tool_error','internal.task_worker_error')",
                    (baseline_since, applied_at),
                ).fetchone()
                baseline_errs = int(err_row[0]) if err_row else 0
                tok_row = conn.execute(
                    "SELECT COALESCE(SUM(total_tokens), 0) FROM llm_calls "
                    "WHERE timestamp >= ? AND timestamp < ?",
                    (baseline_since, applied_at),
                ).fetchone()
                baseline_toks = int(tok_row[0]) if tok_row else 0
                conn.execute(
                    "INSERT OR IGNORE INTO selfmod_outcomes"
                    "(proposal_id, target_module, confirmed_at, "
                    "baseline_errors_7d, baseline_tokens_7d, measure_at, outcome) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
                    (pid, target, applied_at, baseline_errs, baseline_toks, measure_at),
                )
        except sqlite3.OperationalError:
            # llm_calls or self_mod_proposals missing in extremely minimal
            # test substrates — skip backfill, table is still created.
            pass
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (23, now),
        )
        conn.commit()
        version = 23

    if version == 23:
        # v23 → v24: subagent_tasks table for subagent delegation system.
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS subagent_tasks (
                subagent_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                max_steps INTEGER NOT NULL DEFAULT 6,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT NOT NULL DEFAULT '',
                steps_taken INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT ''
            );
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (24, now),
        )
        conn.commit()
        version = 24

    if version == 24:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tool_experiences (
                exp_id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                tool_arg_summary TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT 'success',
                outcome_detail TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                latency_ms INTEGER NOT NULL DEFAULT 0,
                tags_json TEXT NOT NULL DEFAULT '[]',
                session_type TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_texp_tool ON tool_experiences(tool_name);
            CREATE INDEX IF NOT EXISTS idx_texp_outcome ON tool_experiences(outcome);
            CREATE INDEX IF NOT EXISTS idx_texp_provider_model ON tool_experiences(provider, model);
            CREATE INDEX IF NOT EXISTS idx_texp_created ON tool_experiences(created_at);
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (25, now),
        )
        conn.commit()
        version = 25

    if version < CURRENT_VERSION:
        raise RuntimeError(f"no migration path from version {version}")

    return version


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_type: str
) -> None:
    """Add a column to a table if it doesn't already exist. No-op if table missing
    (e.g. minimal test substrates that don't carry every table)."""
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        return
    if not rows:
        return
    existing = {row[1] for row in rows}
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
