-- Sonya substrate schema v1.
-- Author of state changes: src/sonya/state/migrations.py runs this on first open.
-- All identity-critical tables include comments marking immutable zones.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Subject state: single-row table holding current SubjectState snapshot.
-- Updated through write-master only.
CREATE TABLE IF NOT EXISTS subject_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_principal_id TEXT,
    last_canonical_response_ref TEXT,
    active_channels_json TEXT NOT NULL DEFAULT '[]',
    pending_intentions_json TEXT NOT NULL DEFAULT '[]',
    emotional_vector_json TEXT NOT NULL DEFAULT '{}',
    drift_signals_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

-- Continuity stream: append-only event log.
-- seq is monotonically increasing.
CREATE TABLE IF NOT EXISTS continuity_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    principal_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_continuity_kind ON continuity_events(kind);
CREATE INDEX IF NOT EXISTS idx_continuity_principal ON continuity_events(principal_id);

-- Continuity snapshots: point-in-time SubjectState captures.
CREATE TABLE IF NOT EXISTS continuity_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    seq_at_snapshot INTEGER NOT NULL,
    subject_state_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Identity record: single row. Immutable fields enforced at runtime via IdentityWriter.
-- IMMUTABLE FIELDS: things_not_to_betray_json, identity_critical_traits_json.
CREATE TABLE IF NOT EXISTS identity_record (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    self_model_json TEXT NOT NULL DEFAULT '{}',
    things_not_to_betray_json TEXT NOT NULL DEFAULT '[]',
    identity_critical_traits_json TEXT NOT NULL DEFAULT '[]',
    drift_boundaries_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

-- Relation anchor bindings: identity-critical (per SUBSTRATE_STANCE §8).
-- Direct UPDATE/DELETE through runtime API is refused; use governed change protocol.
CREATE TABLE IF NOT EXISTS relation_anchor_bindings (
    principal_id TEXT PRIMARY KEY,
    trusted_identifiers_json TEXT NOT NULL DEFAULT '[]',
    trust_evidence_json TEXT NOT NULL DEFAULT '{}',
    authority_scope_json TEXT NOT NULL DEFAULT '[]',
    channel_constraints_json TEXT NOT NULL DEFAULT '{}',
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Principal registry: who is who. principal_id stable across renames.
CREATE TABLE IF NOT EXISTS principals (
    principal_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    trusted_identifiers_json TEXT NOT NULL DEFAULT '[]',
    authority_scope_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_principals_display ON principals(display_name);

-- ====================================================================
-- v2 additions: harness layer (policy, approval, audit).
-- See [docs/work/implementation-plans/2026-05-14-provider-principal-core-implementation-plan.md].
-- ====================================================================

CREATE TABLE IF NOT EXISTS harness_policy_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    principal_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    decision TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_harness_policy_principal ON harness_policy_rules(principal_id);
CREATE INDEX IF NOT EXISTS idx_harness_policy_scope ON harness_policy_rules(scope);

CREATE TABLE IF NOT EXISTS approval_requests (
    request_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    action TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by_principal_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);

CREATE TABLE IF NOT EXISTS audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    principal_id TEXT,
    action TEXT NOT NULL,
    decision TEXT NOT NULL,
    scope TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_principal ON audit_events(principal_id);
CREATE INDEX IF NOT EXISTS idx_audit_scope ON audit_events(scope);

-- ====================================================================
-- v3 additions: pending intentions + subject state enrichment.
-- See [docs/work/implementation-plans/2026-05-15-subject-core-internal-loop-implementation-plan.md].
-- ====================================================================

CREATE TABLE IF NOT EXISTS pending_intentions (
    intention_id TEXT PRIMARY KEY,
    principal_id TEXT,
    description TEXT NOT NULL,
    task_id TEXT,
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_intentions_status ON pending_intentions(status);
CREATE INDEX IF NOT EXISTS idx_intentions_principal ON pending_intentions(principal_id);

-- ====================================================================
-- v4 additions: self-modification framework.
-- See [docs/work/implementation-plans/2026-05-15-self-modification-framework-implementation-plan.md].
-- ====================================================================

CREATE TABLE IF NOT EXISTS self_mod_proposals (
    proposal_id TEXT PRIMARY KEY,
    target_module TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    diff_blob TEXT NOT NULL DEFAULT '',
    proposed_by_principal_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_selfmod_status ON self_mod_proposals(status);

CREATE TABLE IF NOT EXISTS self_mod_validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id TEXT NOT NULL,
    layer INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    checked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_selfmod_validation_proposal ON self_mod_validation_results(proposal_id);

-- ====================================================================
-- v5 additions: skills substrate.
-- See [docs/work/implementation-plans/2026-05-15-skills-substrate-implementation-plan.md].
-- ====================================================================

CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '0.1.0',
    status TEXT NOT NULL DEFAULT 'active',
    trust_level TEXT NOT NULL DEFAULT 'experimental',
    activation_rules_json TEXT NOT NULL DEFAULT '{}',
    dependencies_json TEXT NOT NULL DEFAULT '[]',
    allowed_tools_json TEXT NOT NULL DEFAULT '[]',
    forbidden_zones_json TEXT NOT NULL DEFAULT '[]',
    tests_json TEXT NOT NULL DEFAULT '[]',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    trace_tags_json TEXT NOT NULL DEFAULT '[]',
    history_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
CREATE INDEX IF NOT EXISTS idx_skills_trust ON skills(trust_level);

CREATE TABLE IF NOT EXISTS capability_gaps (
    gap_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    detected_from_event_seq INTEGER,
    proposal_id TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gaps_status ON capability_gaps(status);

-- ====================================================================
-- v6 additions: memory substrate (episodic + semantic).
-- ====================================================================

CREATE TABLE IF NOT EXISTS episodic_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    raw_content TEXT NOT NULL DEFAULT '',
    normalized_summary TEXT NOT NULL DEFAULT '',
    emotion_tags_json TEXT NOT NULL DEFAULT '[]',
    importance_score REAL NOT NULL DEFAULT 0.5,
    retention_strength REAL NOT NULL DEFAULT 1.0,
    last_accessed_at TEXT NOT NULL DEFAULT '',
    access_count INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    embedding BLOB,
    embedded_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_episodic_type ON episodic_events(event_type);
CREATE INDEX IF NOT EXISTS idx_episodic_timestamp ON episodic_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_episodic_archived ON episodic_events(archived);
CREATE INDEX IF NOT EXISTS idx_episodic_embedded_at ON episodic_events(embedded_at);

CREATE TABLE IF NOT EXISTS semantic_facts (
    fact_id TEXT PRIMARY KEY,
    fact_type TEXT NOT NULL,
    statement TEXT NOT NULL,
    source_event_ids_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5,
    last_reinforced_at TEXT NOT NULL DEFAULT '',
    contradiction_flags_json TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_semantic_type ON semantic_facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_semantic_confidence ON semantic_facts(confidence);

-- ====================================================================
-- v7 additions: task runtime (long-running multi-session work).
-- See [docs/SYSTEM_BUILDOUT_PLAN.md] Этап C.
-- ====================================================================

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    -- pending | in_progress | blocked | done | failed
    principal_id TEXT,
    parent_task_id TEXT,
    deadline TEXT,
    plan_steps_json TEXT NOT NULL DEFAULT '[]',
    completed_steps_json TEXT NOT NULL DEFAULT '[]',
    blocker TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- v9 additions
    created_by TEXT NOT NULL DEFAULT 'self',          -- 'ivan' | 'self'
    scheduled_for TEXT NOT NULL DEFAULT '',            -- ISO; empty = run now
    recurring_spec TEXT NOT NULL DEFAULT '',           -- JSON; empty = one-off
    notify_mode TEXT NOT NULL DEFAULT 'progress',      -- 'progress' | 'final' | 'silent'
    -- v12 additions: session budget + cross-session continuity
    max_sessions INTEGER NOT NULL DEFAULT 0,           -- hard cap; 0 = unlimited
    sessions_used INTEGER NOT NULL DEFAULT 0,          -- counter; auto-fail when reaches max_sessions
    last_session_notes TEXT NOT NULL DEFAULT '',       -- model writes summary at end of each session
    next_step_hint TEXT NOT NULL DEFAULT '',           -- one-line "where to start next time"
    stuck_loop_count INTEGER NOT NULL DEFAULT 0        -- incremented when handoff next_step repeats; reset on change
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_principal ON tasks(principal_id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_for ON tasks(scheduled_for);

-- ====================================================================
-- v8 additions: provider keys (own key pool, replacing OmniRoute).
-- See [docs/SYSTEM_BUILDOUT_PLAN.md] post-Этап cleanup.
-- ====================================================================

CREATE TABLE IF NOT EXISTS provider_keys (
    key_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,        -- fireworks | openrouter | groq | anthropic | google | ...
    name TEXT NOT NULL,            -- human label
    api_key TEXT NOT NULL,         -- the secret
    base_url TEXT NOT NULL,        -- https://api.fireworks.ai/inference/v1 etc.
    model TEXT NOT NULL DEFAULT '', -- override; empty = use provider_settings.default_model
    status TEXT NOT NULL DEFAULT 'active', -- active | disabled | banned | cooldown
    priority INTEGER NOT NULL DEFAULT 0,
    cooldown_until TEXT NOT NULL DEFAULT '',
    last_used_at TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    last_error_at TEXT NOT NULL DEFAULT '',
    request_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- v11 additions: provider account discovery + balance snapshot
    account_id TEXT NOT NULL DEFAULT '',
    balance_json TEXT NOT NULL DEFAULT '{}',
    balance_checked_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_provider_keys_provider ON provider_keys(provider);
CREATE INDEX IF NOT EXISTS idx_provider_keys_status ON provider_keys(status);

-- v11 columns added below via ALTER (account_id discovered + balance snapshot)

-- Single-row provider_settings
CREATE TABLE IF NOT EXISTS provider_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_provider TEXT NOT NULL DEFAULT 'fireworks',
    default_model TEXT NOT NULL DEFAULT 'accounts/fireworks/models/minimax-m2p7',
    default_base_url TEXT NOT NULL DEFAULT 'https://api.fireworks.ai/inference/v1',
    updated_at TEXT NOT NULL
);

-- LLM call audit log (v10)
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    key_id TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    purpose TEXT NOT NULL DEFAULT '',         -- 'tg_session' | 'idle_thinking' | 'active_session' | 'task_worker' | 'admin_chat' | 'unknown'
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT '',          -- 'ok' | 'error' | 'auth' | 'rate_limit' | 'server_error'
    http_status INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_timestamp ON llm_calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_llm_calls_key_id ON llm_calls(key_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_purpose ON llm_calls(purpose);
CREATE INDEX IF NOT EXISTS idx_llm_calls_status ON llm_calls(status);

-- ====================================================================
-- v9 additions: task scheduling + ownership
-- created_by: 'ivan' (Ivan-issued, worked on continuously by ivan-task-worker)
--             'self' (Sonya's own ideas, worked on in active sessions)
-- scheduled_for: ISO timestamp; null/empty = run immediately
-- recurring_spec: JSON describing repeat pattern (or '' for one-off)
-- notify_mode: 'progress' (chat.tell_ivan after each step) | 'final' (only at done) |
--              'silent' (no progress messages, just continuity)
-- These columns added via ALTER TABLE in migration v8 → v9.
-- ====================================================================

-- ====================================================================
-- v14 additions: sticker collection
-- Stores stickers Sonya has seen incoming from Ivan, so she can re-send
-- them as part of her own replies via the [STICKER: <emoji>] marker.
-- ====================================================================

CREATE TABLE IF NOT EXISTS seen_stickers (
    sticker_id TEXT PRIMARY KEY,        -- composite "<file_id>:<access_hash>" (telethon InputDocument key)
    file_id INTEGER NOT NULL,           -- Telegram document id (numeric)
    access_hash INTEGER NOT NULL,       -- Telegram access hash for the document
    file_reference BLOB,                -- short-lived reference (refreshed on stale)
    emoji TEXT NOT NULL DEFAULT '',     -- alt-emoji from sticker attribute (single emoji)
    pack_name TEXT NOT NULL DEFAULT '', -- short_name of the sticker set
    mime_type TEXT NOT NULL DEFAULT '', -- 'image/webp' | 'application/x-tgsticker' | 'video/webm'
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    seen_count INTEGER NOT NULL DEFAULT 1,
    use_count INTEGER NOT NULL DEFAULT 0   -- how many times Sonya re-sent this one
);

CREATE INDEX IF NOT EXISTS idx_seen_stickers_emoji ON seen_stickers(emoji);
CREATE INDEX IF NOT EXISTS idx_seen_stickers_pack ON seen_stickers(pack_name);
CREATE INDEX IF NOT EXISTS idx_seen_stickers_use_count ON seen_stickers(use_count);


-- ====================================================================
-- v15 additions: environment status (Sonya's observation of context).
-- Sonya records what she observes about Ivan's situation here via env.set
-- tool. Examples: ivan_status='спит', activity='работает над парсером',
-- mood='уставший'. No clock heuristics — she infers from conversation.
-- ====================================================================

CREATE TABLE IF NOT EXISTS environment_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',     -- 'observation' | 'inference' | 'ivan_said' | 'system'
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT ''  -- agent_session purpose / 'self_inspect' / etc
);

CREATE INDEX IF NOT EXISTS idx_environment_updated_at ON environment_state(updated_at);


-- ====================================================================
-- v16 additions: persistent drive state.
-- Drive counters survive restarts. Updated every 5 ticks (~50 seconds)
-- to avoid excessive writes while keeping state fresh enough.
-- ====================================================================

CREATE TABLE IF NOT EXISTS drive_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    boredom_analog REAL NOT NULL DEFAULT 0.0,
    curiosity_analog REAL NOT NULL DEFAULT 0.0,
    relational_focus REAL NOT NULL DEFAULT 0.0,
    pending_debt REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL DEFAULT ''
);


-- ====================================================================
-- v16 additions (cont): goals table.
-- Goals are long-term objectives that group tasks. A task can belong to
-- a goal via parent_goal_id. Active sessions read top goals to decide
-- what to work on. Goals don't expire (no deadline) but can be closed.
-- ====================================================================

CREATE TABLE IF NOT EXISTS goals (
    goal_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',      -- active | achieved | abandoned
    priority INTEGER NOT NULL DEFAULT 0,       -- higher = more important
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);


-- ====================================================================
-- v16 additions (cont): selfmod outcome tracking.
-- After a proposal is CONFIRMED_STABLE, we record baseline metrics and
-- then measure delta after 7 days to learn what helped vs what didn't.
-- ====================================================================

CREATE TABLE IF NOT EXISTS selfmod_outcomes (
    proposal_id TEXT PRIMARY KEY,
    target_module TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    baseline_errors_7d INTEGER NOT NULL DEFAULT 0,
    baseline_tokens_7d INTEGER NOT NULL DEFAULT 0,
    measure_at TEXT NOT NULL DEFAULT '',       -- when to take the 7-day measurement
    measured_errors_7d INTEGER,                -- null = not yet measured
    measured_tokens_7d INTEGER,
    outcome TEXT NOT NULL DEFAULT 'pending',   -- pending | improved | neutral | degraded
    measured_at TEXT NOT NULL DEFAULT ''
);


-- v16 addition (cont): perceptual hash for media-attached episodic events.
-- Computed via imagehash.phash on downloaded images. Allows "same image?"
-- comparisons without re-downloading or re-embedding.
-- ALTER TABLE addition handled by migration.
