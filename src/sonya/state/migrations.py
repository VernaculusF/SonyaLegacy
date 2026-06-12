from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA_FILE = Path(__file__).parent / "schema.sql"

CURRENT_VERSION = 35


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
        "VALUES (1, 'openrouter', '', 'https://openrouter.ai/api/v1', ?)",
        (now,),
    )
    conn.commit()


def ensure_critical_schema(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "provider_keys", "slot", "TEXT NOT NULL DEFAULT 'text'")
    _add_column_if_missing(conn, "provider_settings", "vision_provider", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_settings", "vision_model", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_settings", "fast_model", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_settings", "deep_model", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_settings", "vision_base_url", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "episodic_events", "record_type", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "episodic_events", "scope", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "episodic_events", "project_id", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "episodic_events", "retention_policy", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "episodic_events", "media_phash", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "semantic_facts", "scope", "TEXT NOT NULL DEFAULT 'global'")
    _add_column_if_missing(conn, "semantic_facts", "project_id", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "semantic_facts", "retention_policy", "TEXT NOT NULL DEFAULT 'long'")
    _add_column_if_missing(conn, "provider_models", "text_loop_ok", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "provider_models", "last_checked_at", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "provider_models", "discovery_source", "TEXT NOT NULL DEFAULT 'manual'")
    _add_column_if_missing(conn, "provider_models", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_provider_models_provider_scoped(conn)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            key TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subagent_tasks (
            subagent_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT '',
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
        CREATE TABLE IF NOT EXISTS raw_traces (
            trace_id TEXT PRIMARY KEY,
            record_type TEXT NOT NULL,
            scope TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            raw_content TEXT NOT NULL,
            normalized_summary TEXT NOT NULL DEFAULT '',
            importance REAL NOT NULL DEFAULT 0.3,
            stability REAL NOT NULL DEFAULT 0.2,
            project_id TEXT NOT NULL DEFAULT '',
            retention_policy TEXT NOT NULL DEFAULT 'archive_only',
            tags_json TEXT NOT NULL DEFAULT '[]',
            session_type TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rt_record_type ON raw_traces(record_type);
        CREATE INDEX IF NOT EXISTS idx_rt_scope ON raw_traces(scope);
        CREATE INDEX IF NOT EXISTS idx_rt_project_id ON raw_traces(project_id);
        CREATE INDEX IF NOT EXISTS idx_rt_created ON raw_traces(created_at);
        CREATE INDEX IF NOT EXISTS idx_rt_session_type ON raw_traces(session_type);
        CREATE TABLE IF NOT EXISTS procedural_memory (
            lesson_id TEXT PRIMARY KEY,
            record_type TEXT NOT NULL DEFAULT 'operational_lesson',
            scope TEXT NOT NULL DEFAULT 'global',
            statement TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT '',
            pattern TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            source_trace_ids_json TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.5,
            last_reinforced_at TEXT NOT NULL DEFAULT '',
            retention_policy TEXT NOT NULL DEFAULT 'long',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pm_lesson_domain ON procedural_memory(domain);
        CREATE INDEX IF NOT EXISTS idx_pm_lesson_scope ON procedural_memory(scope);
        CREATE INDEX IF NOT EXISTS idx_pm_lesson_project ON procedural_memory(project_id);
        CREATE INDEX IF NOT EXISTS idx_pm_lesson_confidence ON procedural_memory(confidence);
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
            "VALUES (1, 'openrouter', '', 'https://openrouter.ai/api/v1', ?)",
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
                status TEXT NOT NULL DEFAULT 'in_progress',
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
                workspace_id TEXT NOT NULL DEFAULT '',
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

    if version == 25:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                workspace_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                owner_principal_id TEXT NOT NULL DEFAULT 'ivan',
                policy_json TEXT NOT NULL DEFAULT '{}',
                last_activity_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
            CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_principal_id);

            CREATE TABLE IF NOT EXISTS project_runs (
                run_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'main',
                status TEXT NOT NULL DEFAULT 'pending',
                agent_type TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                steps_json TEXT NOT NULL DEFAULT '[]',
                result TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                continuity_seq_start INTEGER NOT NULL DEFAULT 0,
                continuity_seq_end INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            );
            CREATE INDEX IF NOT EXISTS idx_pruns_project ON project_runs(project_id);
            CREATE INDEX IF NOT EXISTS idx_pruns_status ON project_runs(status);
            CREATE INDEX IF NOT EXISTS idx_pruns_kind ON project_runs(kind);

            CREATE TABLE IF NOT EXISTS execution_traces (
                trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                project_id TEXT NOT NULL DEFAULT '',
                step_seq INTEGER NOT NULL DEFAULT 0,
                step_type TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                tool_name TEXT NOT NULL DEFAULT '',
                tool_arg_summary TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                provider TEXT NOT NULL DEFAULT '',
                latency_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES project_runs(run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_trace_run ON execution_traces(run_id);
            CREATE INDEX IF NOT EXISTS idx_trace_project ON execution_traces(project_id);
            CREATE INDEX IF NOT EXISTS idx_trace_type ON execution_traces(step_type);

            CREATE TABLE IF NOT EXISTS evolution_pressure (
                pressure_id TEXT PRIMARY KEY,
                dimension TEXT NOT NULL,
                current_score REAL NOT NULL DEFAULT 0.5,
                target_score REAL NOT NULL DEFAULT 1.0,
                gap REAL NOT NULL DEFAULT 0.5,
                evidence TEXT NOT NULL DEFAULT '',
                last_evaluated_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_evo_pressure_dim ON evolution_pressure(dimension);
            CREATE INDEX IF NOT EXISTS idx_evo_pressure_gap ON evolution_pressure(gap);
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (26, now),
        )
        conn.commit()
        version = 26

    if version < 27:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workspace_policy (
                workspace_id TEXT PRIMARY KEY,
                policy_json TEXT NOT NULL DEFAULT '{}',
                full_system_access INTEGER NOT NULL DEFAULT 0,
                allowed_paths TEXT NOT NULL DEFAULT '',
                denied_paths TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (workspace_id) REFERENCES projects(project_id)
            );
            CREATE INDEX IF NOT EXISTS idx_wsp_workspace ON workspace_policy(workspace_id);
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (27, now),
        )
        conn.commit()
        version = 27

    if version == 27:
        now = datetime.now(timezone.utc).isoformat()
        _add_column_if_missing(
            conn, "subagent_tasks", "workspace_id",
            "TEXT NOT NULL DEFAULT ''"
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (28, now),
        )
        conn.commit()
        version = 28

    if version == 28:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS model_scorecards (
                scorecard_id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                provider_id TEXT NOT NULL DEFAULT '',
                domain TEXT NOT NULL DEFAULT 'general',
                role TEXT NOT NULL DEFAULT 'auto',
                avg_score REAL NOT NULL DEFAULT 0.5,
                confidence REAL NOT NULL DEFAULT 0.0,
                avg_latency_ms INTEGER NOT NULL DEFAULT 0,
                avg_tokens_in INTEGER NOT NULL DEFAULT 0,
                avg_tokens_out INTEGER NOT NULL DEFAULT 0,
                refusal_rate REAL NOT NULL DEFAULT 0.0,
                hallucination_rate REAL NOT NULL DEFAULT 0.0,
                error_rate REAL NOT NULL DEFAULT 0.0,
                total_runs INTEGER NOT NULL DEFAULT 0,
                last_evaluated_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_msc_model ON model_scorecards(model_id);
            CREATE INDEX IF NOT EXISTS idx_msc_domain ON model_scorecards(domain);
            CREATE INDEX IF NOT EXISTS idx_msc_role ON model_scorecards(role);
            CREATE INDEX IF NOT EXISTS idx_msc_score ON model_scorecards(avg_score);

            CREATE TABLE IF NOT EXISTS evaluation_runs (
                run_id TEXT PRIMARY KEY,
                trigger TEXT NOT NULL DEFAULT 'manual',
                suite_name TEXT NOT NULL DEFAULT '',
                models_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending',
                started_at TEXT NOT NULL DEFAULT '',
                finished_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_er_status ON evaluation_runs(status);
            CREATE INDEX IF NOT EXISTS idx_er_trigger ON evaluation_runs(trigger);

            CREATE TABLE IF NOT EXISTS evaluation_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'auto',
                prompt_summary TEXT NOT NULL DEFAULT '',
                raw_output TEXT NOT NULL DEFAULT '',
                normalized_score REAL NOT NULL DEFAULT 0.0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                refusal_flag INTEGER NOT NULL DEFAULT 0,
                hallucination_flag INTEGER NOT NULL DEFAULT 0,
                error_flag INTEGER NOT NULL DEFAULT 0,
                passed INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_evr_run ON evaluation_results(run_id);
            CREATE INDEX IF NOT EXISTS idx_evr_model ON evaluation_results(model_id);
            CREATE INDEX IF NOT EXISTS idx_evr_domain ON evaluation_results(domain);
            CREATE INDEX IF NOT EXISTS idx_evr_passed ON evaluation_results(passed);

            CREATE TABLE IF NOT EXISTS champion_models (
                champion_id TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'auto',
                model_id TEXT NOT NULL,
                provider_id TEXT NOT NULL DEFAULT '',
                scorecard_id TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                pinned INTEGER NOT NULL DEFAULT 0,
                challengers_json TEXT NOT NULL DEFAULT '[]',
                last_evaluated_at TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cm_domain_role ON champion_models(domain, role);
            CREATE INDEX IF NOT EXISTS idx_cm_model ON champion_models(model_id);
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (29, now),
        )
        conn.commit()
        version = 29

    if version == 29:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS provider_models (
                model_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                base_url TEXT NOT NULL DEFAULT '',
                api_key_ref TEXT NOT NULL DEFAULT '',
                context_length INTEGER NOT NULL DEFAULT 131072,
                modalities_json TEXT NOT NULL DEFAULT '["text"]',
                cost_per_1m_input_tokens REAL NOT NULL DEFAULT 0.0,
                cost_per_1m_output_tokens REAL NOT NULL DEFAULT 0.0,
                is_free INTEGER NOT NULL DEFAULT 0,
                latency_tier TEXT NOT NULL DEFAULT 'medium',
                strength_json TEXT NOT NULL DEFAULT '{}',
                role_preference TEXT NOT NULL DEFAULT 'auto',
                enabled INTEGER NOT NULL DEFAULT 1,
                text_loop_ok INTEGER NOT NULL DEFAULT 1,
                last_checked_at TEXT NOT NULL DEFAULT '',
                discovery_source TEXT NOT NULL DEFAULT 'manual',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (provider, model_id)
            );
            CREATE INDEX IF NOT EXISTS idx_pm_provider ON provider_models(provider);
            CREATE INDEX IF NOT EXISTS idx_pm_model ON provider_models(model_id);
            CREATE INDEX IF NOT EXISTS idx_pm_role ON provider_models(role_preference);
            CREATE INDEX IF NOT EXISTS idx_pm_enabled ON provider_models(enabled);
            CREATE INDEX IF NOT EXISTS idx_pm_free ON provider_models(is_free);
            CREATE INDEX IF NOT EXISTS idx_pm_latency ON provider_models(latency_tier);

        """)

        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (30, now),
        )
        conn.commit()
        version = 30

    if version == 30:
        now = datetime.now(timezone.utc).isoformat()
        _add_column_if_missing(conn, "episodic_events", "record_type", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "episodic_events", "scope", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "episodic_events", "project_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "episodic_events", "retention_policy", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "episodic_events", "media_phash", "TEXT NOT NULL DEFAULT ''")
        if _table_exists(conn, "episodic_events"):
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodic_record_type ON episodic_events(record_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodic_scope ON episodic_events(scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodic_project_id ON episodic_events(project_id)")

        _add_column_if_missing(conn, "semantic_facts", "scope", "TEXT NOT NULL DEFAULT 'global'")
        _add_column_if_missing(conn, "semantic_facts", "project_id", "TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "semantic_facts", "retention_policy", "TEXT NOT NULL DEFAULT 'long'")
        if _table_exists(conn, "semantic_facts"):
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_scope ON semantic_facts(scope)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_project_id ON semantic_facts(project_id)")

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_traces (
                trace_id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                scope TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                raw_content TEXT NOT NULL,
                normalized_summary TEXT NOT NULL DEFAULT '',
                importance REAL NOT NULL DEFAULT 0.3,
                stability REAL NOT NULL DEFAULT 0.2,
                project_id TEXT NOT NULL DEFAULT '',
                retention_policy TEXT NOT NULL DEFAULT 'archive_only',
                tags_json TEXT NOT NULL DEFAULT '[]',
                session_type TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_rt_record_type ON raw_traces(record_type);
            CREATE INDEX IF NOT EXISTS idx_rt_scope ON raw_traces(scope);
            CREATE INDEX IF NOT EXISTS idx_rt_project_id ON raw_traces(project_id);
            CREATE INDEX IF NOT EXISTS idx_rt_created ON raw_traces(created_at);
            CREATE INDEX IF NOT EXISTS idx_rt_session_type ON raw_traces(session_type);

            CREATE TABLE IF NOT EXISTS procedural_memory (
                lesson_id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL DEFAULT 'operational_lesson',
                scope TEXT NOT NULL DEFAULT 'global',
                statement TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                pattern TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                source_trace_ids_json TEXT NOT NULL DEFAULT '[]',
                confidence REAL NOT NULL DEFAULT 0.5,
                last_reinforced_at TEXT NOT NULL DEFAULT '',
                retention_policy TEXT NOT NULL DEFAULT 'long',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pm_lesson_domain ON procedural_memory(domain);
            CREATE INDEX IF NOT EXISTS idx_pm_lesson_scope ON procedural_memory(scope);
            CREATE INDEX IF NOT EXISTS idx_pm_lesson_project ON procedural_memory(project_id);
            CREATE INDEX IF NOT EXISTS idx_pm_lesson_confidence ON procedural_memory(confidence);
        """)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (31, now),
        )
        conn.commit()
        version = 31

    if version == 31:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS providers (
                provider_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                adapter_kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                base_url TEXT NOT NULL DEFAULT '',
                capabilities_json TEXT NOT NULL DEFAULT '{}',
                constraints_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_providers_status ON providers(status);
            CREATE INDEX IF NOT EXISTS idx_providers_adapter ON providers(adapter_kind);

            CREATE TABLE IF NOT EXISTS provider_accounts (
                account_id TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL,
                name TEXT NOT NULL,
                secret_ref TEXT NOT NULL DEFAULT '',
                secret_masked TEXT NOT NULL DEFAULT '',
                legacy_key_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                priority INTEGER NOT NULL DEFAULT 0,
                constraints_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (provider_id) REFERENCES providers(provider_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_pa_legacy_key
                ON provider_accounts(legacy_key_id) WHERE legacy_key_id != '';
            CREATE INDEX IF NOT EXISTS idx_pa_provider ON provider_accounts(provider_id);
            CREATE INDEX IF NOT EXISTS idx_pa_status ON provider_accounts(status);

            CREATE TABLE IF NOT EXISTS provider_account_offerings (
                account_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (account_id, model_id),
                FOREIGN KEY (account_id) REFERENCES provider_accounts(account_id)
            );
            CREATE INDEX IF NOT EXISTS idx_pao_model ON provider_account_offerings(model_id);
            CREATE INDEX IF NOT EXISTS idx_pao_enabled ON provider_account_offerings(enabled);

            CREATE TABLE IF NOT EXISTS provider_quota_windows (
                quota_window_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                quota_kind TEXT NOT NULL,
                limit_value REAL,
                used_value REAL,
                remaining_value REAL,
                unit TEXT NOT NULL DEFAULT '',
                window_started_at TEXT NOT NULL DEFAULT '',
                resets_at TEXT NOT NULL DEFAULT '',
                observed_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY (account_id) REFERENCES provider_accounts(account_id)
            );
            CREATE INDEX IF NOT EXISTS idx_pqw_account ON provider_quota_windows(account_id);
            CREATE INDEX IF NOT EXISTS idx_pqw_resets ON provider_quota_windows(resets_at);

            CREATE TABLE IF NOT EXISTS provider_observations (
                observation_id TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL,
                account_id TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL DEFAULT '',
                observation_kind TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                value_json TEXT NOT NULL DEFAULT '{}',
                observed_at TEXT NOT NULL,
                FOREIGN KEY (provider_id) REFERENCES providers(provider_id)
            );
            CREATE INDEX IF NOT EXISTS idx_po_provider ON provider_observations(provider_id);
            CREATE INDEX IF NOT EXISTS idx_po_account ON provider_observations(account_id);
            CREATE INDEX IF NOT EXISTS idx_po_model ON provider_observations(model_id);
            CREATE INDEX IF NOT EXISTS idx_po_kind ON provider_observations(observation_kind);
        """)
        if _table_exists(conn, "provider_keys"):
            conn.execute(
                "INSERT OR IGNORE INTO providers "
                "(provider_id, display_name, adapter_kind, status, base_url, created_at, updated_at) "
                "SELECT provider, provider, 'openai_compatible', 'active', MAX(base_url), ?, ? "
                "FROM provider_keys GROUP BY provider",
                (now, now),
            )
        if _table_exists(conn, "provider_models"):
            conn.execute(
                "INSERT OR IGNORE INTO providers "
                "(provider_id, display_name, adapter_kind, status, base_url, created_at, updated_at) "
                "SELECT provider, provider, 'openai_compatible', 'active', MAX(base_url), ?, ? "
                "FROM provider_models GROUP BY provider",
                (now, now),
            )
        if _table_exists(conn, "provider_keys"):
            conn.execute(
                "INSERT OR IGNORE INTO provider_accounts "
                "(account_id, provider_id, name, secret_ref, legacy_key_id, status, priority, "
                "constraints_json, metadata_json, created_at, updated_at) "
                "SELECT key_id, provider, name, 'legacy-provider-key:' || key_id, key_id, status, "
                "priority, '{}', '{}', created_at, updated_at FROM provider_keys"
            )
        if _table_exists(conn, "provider_keys") and _table_exists(conn, "provider_models"):
            conn.execute(
                "INSERT OR IGNORE INTO provider_account_offerings "
                "(account_id, model_id, enabled, metadata_json, created_at, updated_at) "
                "SELECT pk.key_id, pk.model, 1, '{\"source\":\"legacy_fixed_model\"}', ?, ? "
                "FROM provider_keys pk JOIN provider_models pm "
                "ON pm.provider = pk.provider AND pm.model_id = pk.model "
                "WHERE pk.model != ''",
                (now, now),
            )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (32, now),
        )
        conn.commit()
        version = 32

    if version == 32:
        now = datetime.now(timezone.utc).isoformat()
        _add_column_if_missing(conn, "provider_accounts", "secret_masked", "TEXT NOT NULL DEFAULT ''")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS provider_secrets (
                secret_id TEXT PRIMARY KEY,
                provider_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                secret_kind TEXT NOT NULL DEFAULT 'api_key',
                encrypted_value TEXT NOT NULL,
                value_fingerprint TEXT NOT NULL,
                masked_value TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (provider_id) REFERENCES providers(provider_id),
                FOREIGN KEY (account_id) REFERENCES provider_accounts(account_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ps_provider ON provider_secrets(provider_id);
            CREATE INDEX IF NOT EXISTS idx_ps_account ON provider_secrets(account_id);
            CREATE INDEX IF NOT EXISTS idx_ps_status ON provider_secrets(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_ps_fingerprint
                ON provider_secrets(provider_id, value_fingerprint);
        """)
        if _table_exists(conn, "provider_accounts") and _table_exists(conn, "provider_keys"):
            conn.execute(
                "UPDATE provider_accounts SET secret_masked = "
                "CASE WHEN LENGTH(provider_keys.api_key) > 12 "
                "THEN SUBSTR(provider_keys.api_key, 1, 6) || '...' || SUBSTR(provider_keys.api_key, -4) "
                "ELSE '***' END "
                "FROM provider_keys WHERE provider_accounts.legacy_key_id = provider_keys.key_id "
                "AND provider_accounts.secret_masked = ''"
            )
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (33, now),
        )
        conn.commit()
        version = 33

    if version == 33:
        now = datetime.now(timezone.utc).isoformat()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS situational_assertions (
                assertion_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                value TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'observation',
                source_ref TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                observed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL DEFAULT 'global',
                visibility TEXT NOT NULL DEFAULT 'normal',
                active INTEGER NOT NULL DEFAULT 1,
                supersedes_id TEXT NOT NULL DEFAULT '',
                superseded_by TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_sa_current
                ON situational_assertions(subject, predicate, scope, active);
            CREATE INDEX IF NOT EXISTS idx_sa_expires ON situational_assertions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_sa_observed ON situational_assertions(observed_at);

            CREATE TABLE IF NOT EXISTS credential_exposures (
                exposure_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL DEFAULT '',
                credential_label TEXT NOT NULL DEFAULT '',
                discovered_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'unresolved',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_ce_status ON credential_exposures(status);

            CREATE TABLE IF NOT EXISTS runtime_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
        """)
        if _table_exists(conn, "environment_state"):
            rows = conn.execute(
                "SELECT key, value, source, updated_at, updated_by FROM environment_state"
            ).fetchall()
            credential_markers = (
                "apikey", "api_key", "token", "secret", "credential", "password", "passwd"
            )
            runtime_keys = {"atrium_last_seen", "drift_last_alert_at"}
            for key, value, source, updated_at, updated_by in rows:
                key_lower = (key or "").lower()
                if any(marker in key_lower for marker in credential_markers):
                    conn.execute(
                        "INSERT OR IGNORE INTO credential_exposures("
                        "exposure_id, source_kind, source_ref, credential_label, discovered_at, "
                        "status, metadata_json) VALUES (?, 'legacy_environment_state', ?, ?, ?, "
                        "'unresolved', '{\"value_removed\":true}')",
                        (f"ce-env-{key}", updated_by or "", key, now),
                    )
                    continue
                if key in runtime_keys:
                    conn.execute(
                        "INSERT OR REPLACE INTO runtime_state(key, value, updated_at) "
                        "VALUES (?, ?, ?)",
                        (key, value, updated_at or now),
                    )
                    continue
                subject = "ivan" if (key or "").startswith("ivan_") else "environment"
                conn.execute(
                    "INSERT OR IGNORE INTO situational_assertions("
                    "assertion_id, subject, predicate, value, source, source_ref, confidence, "
                    "observed_at, expires_at, scope, visibility, active, supersedes_id, "
                    "superseded_by, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0.5, ?, '', 'global', 'normal', 1, '', '', "
                    "'{\"migrated_from\":\"environment_state\"}')",
                    (
                        f"wa-env-{key}",
                        subject,
                        key,
                        value,
                        source or "legacy",
                        updated_by or "",
                        updated_at or now,
                    ),
                )
            conn.execute("DELETE FROM environment_state")
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (34, now),
        )
        conn.commit()
        version = 34

    if version == 34:
        # v34 -> v35: unified work items table
        conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES (?, ?)",
            (35, now),
        )
        # Migrate existing tasks to work_items
        conn.execute("""
            INSERT OR IGNORE INTO work_items (
                item_id, item_type, title, description, status,
                owner_principal_id, origin, parent_item_id, deadline,
                dependencies_json, progress_json, context_anchors_json,
                validation_evidence_json, urgency, max_sessions,
                sessions_used, last_session_notes, next_step_hint,
                stuck_loop_count, created_at, updated_at, last_activity_at
            )
            SELECT 
                task_id, 'task', title, description, status,
                principal_id, created_by, parent_task_id, deadline,
                '[]', completed_steps_json, '[]',
                '[]', urgency, max_sessions,
                sessions_used, last_session_notes, next_step_hint,
                stuck_loop_count, created_at, updated_at, updated_at
            FROM tasks
        """)
        # Migrate existing goals to work_items
        conn.execute("""
            INSERT OR IGNORE INTO work_items (
                item_id, item_type, title, description, status,
                owner_principal_id, origin, parent_item_id, deadline,
                dependencies_json, progress_json, context_anchors_json,
                validation_evidence_json, urgency, max_sessions,
                sessions_used, last_session_notes, next_step_hint,
                stuck_loop_count, created_at, updated_at, last_activity_at
            )
            SELECT 
                goal_id, 'goal', title, description, status,
                'ivan', 'self', NULL, NULL,
                '[]', '[]', '[]',
                '[]', 'normal', 0,
                0, '', '',
                0, created_at, updated_at, updated_at
            FROM goals
        """)
        conn.commit()
        version = 35

    if version != CURRENT_VERSION:
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


def _ensure_provider_models_provider_scoped(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "provider_models"):
        return
    rows = conn.execute("PRAGMA table_info(provider_models)").fetchall()
    if not rows:
        return
    pk = {row[1]: int(row[5] or 0) for row in rows}
    provider_scoped = pk.get("provider", 0) > 0 and pk.get("model_id", 0) > 0
    offerings_model_fk = _provider_offerings_has_model_fk(conn)
    if provider_scoped and not offerings_model_fk:
        _create_provider_model_indexes(conn)
        conn.commit()
        return

    foreign_keys_enabled = bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        if not provider_scoped:
            conn.executescript("""
                DROP INDEX IF EXISTS idx_pm_provider;
                DROP INDEX IF EXISTS idx_pm_model;
                DROP INDEX IF EXISTS idx_pm_role;
                DROP INDEX IF EXISTS idx_pm_enabled;
                DROP INDEX IF EXISTS idx_pm_free;
                DROP INDEX IF EXISTS idx_pm_latency;

                ALTER TABLE provider_models RENAME TO provider_models_old;

                CREATE TABLE provider_models (
                    model_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    base_url TEXT NOT NULL DEFAULT '',
                    api_key_ref TEXT NOT NULL DEFAULT '',
                    context_length INTEGER NOT NULL DEFAULT 131072,
                    modalities_json TEXT NOT NULL DEFAULT '["text"]',
                    cost_per_1m_input_tokens REAL NOT NULL DEFAULT 0.0,
                    cost_per_1m_output_tokens REAL NOT NULL DEFAULT 0.0,
                    is_free INTEGER NOT NULL DEFAULT 0,
                    latency_tier TEXT NOT NULL DEFAULT 'medium',
                    strength_json TEXT NOT NULL DEFAULT '{}',
                    role_preference TEXT NOT NULL DEFAULT 'auto',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    text_loop_ok INTEGER NOT NULL DEFAULT 1,
                    last_checked_at TEXT NOT NULL DEFAULT '',
                    discovery_source TEXT NOT NULL DEFAULT 'manual',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (provider, model_id)
                );

                INSERT OR REPLACE INTO provider_models (
                    model_id, provider, model_name, base_url, api_key_ref, context_length,
                    modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                    is_free, latency_tier, strength_json, role_preference, enabled,
                    text_loop_ok, last_checked_at, discovery_source, metadata_json,
                    created_at, updated_at
                )
                SELECT
                    model_id, provider, model_name, base_url, api_key_ref, context_length,
                    modalities_json, cost_per_1m_input_tokens, cost_per_1m_output_tokens,
                    is_free, latency_tier, strength_json, role_preference, enabled,
                    text_loop_ok, last_checked_at, discovery_source, metadata_json,
                    created_at, updated_at
                FROM provider_models_old;

                DROP TABLE provider_models_old;
            """)
            _create_provider_model_indexes(conn)
        if offerings_model_fk:
            _rebuild_provider_account_offerings_without_model_fk(conn)
        conn.commit()
    finally:
        conn.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys_enabled else 'OFF'}")


def _create_provider_model_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_pm_provider ON provider_models(provider);
        CREATE INDEX IF NOT EXISTS idx_pm_model ON provider_models(model_id);
        CREATE INDEX IF NOT EXISTS idx_pm_role ON provider_models(role_preference);
        CREATE INDEX IF NOT EXISTS idx_pm_enabled ON provider_models(enabled);
        CREATE INDEX IF NOT EXISTS idx_pm_free ON provider_models(is_free);
        CREATE INDEX IF NOT EXISTS idx_pm_latency ON provider_models(latency_tier);
    """)


def _provider_offerings_has_model_fk(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "provider_account_offerings"):
        return False
    try:
        rows = conn.execute("PRAGMA foreign_key_list(provider_account_offerings)").fetchall()
    except sqlite3.OperationalError:
        return False
    return any(row[2] == "provider_models" and row[4] == "model_id" for row in rows)


def _rebuild_provider_account_offerings_without_model_fk(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "provider_account_offerings"):
        return
    conn.executescript("""
        DROP INDEX IF EXISTS idx_pao_model;
        DROP INDEX IF EXISTS idx_pao_enabled;

        ALTER TABLE provider_account_offerings RENAME TO provider_account_offerings_old;

        CREATE TABLE provider_account_offerings (
            account_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (account_id, model_id),
            FOREIGN KEY (account_id) REFERENCES provider_accounts(account_id)
        );

        INSERT OR REPLACE INTO provider_account_offerings (
            account_id, model_id, enabled, metadata_json, created_at, updated_at
        )
        SELECT account_id, model_id, enabled, metadata_json, created_at, updated_at
        FROM provider_account_offerings_old;

        DROP TABLE provider_account_offerings_old;

        CREATE INDEX IF NOT EXISTS idx_pao_model ON provider_account_offerings(model_id);
        CREATE INDEX IF NOT EXISTS idx_pao_enabled ON provider_account_offerings(enabled);
    """)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


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
