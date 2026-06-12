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



    -- v20 (Atrium Р’В¦Р Р…TР вЂ™Р’В¦-Р’В¦Р’В¬ 0): Sonya-controlled state surfaces.



    -- mind.focus / body.expression / body.outfit / mind.mood_tint tools



    -- write here directly (replace semantics, not append). Source-of-truth



    -- for Avatar / Room view rendering. Р’В¦Р В±Р’В¦-. docs/atrium/EVENT_SCHEMA.md TР В·1.2.



    current_focus TEXT NOT NULL DEFAULT '',



    current_outfit TEXT NOT NULL DEFAULT 'home',



    current_expression TEXT NOT NULL DEFAULT 'neutral',



    mood_tint TEXT NOT NULL DEFAULT 'neutral',



    updated_at TEXT NOT NULL



);







-- Continuity stream: append-only event log.



-- seq is monotonically increasing.



CREATE TABLE IF NOT EXISTS continuity_events (



    seq INTEGER PRIMARY KEY AUTOINCREMENT,



    kind TEXT NOT NULL,



    principal_id TEXT,



    payload_json TEXT NOT NULL DEFAULT '{}',



    -- v20 (Atrium Р’В¦Р Р…TР вЂ™Р’В¦-Р’В¦Р’В¬ 0): channel + private fields (mirror payload values



    -- to dedicated columns for SQL-level filtering Р’В¦-Р’В¦Р’В¦Р’В¦Р’В¬ Р’В¦Р’В¬Р’В¦-TР С’TР вЂ�Р’В¦Р’В¬Р’В¦-Р’В¦Р’В¦Р’В¦- JSON).



    -- channel: 'dialog' | 'worker_log' | 'mind' | 'body' | 'voice' | ''



    -- private=1: skipped from /atrium/feed but kept in substrate.



    -- Р’В¦Р В±Р’В¦-. docs/atrium/EVENT_SCHEMA.md TР В·1.1.



    channel TEXT NOT NULL DEFAULT '',



    private INTEGER NOT NULL DEFAULT 0,



    created_at TEXT NOT NULL



);







CREATE INDEX IF NOT EXISTS idx_continuity_kind ON continuity_events(kind);



CREATE INDEX IF NOT EXISTS idx_continuity_principal ON continuity_events(principal_id);



-- Note: idx_continuity_channel and idx_continuity_private are created by



-- migrations._ensure_atrium_indexes() to keep schema.sql safe for legacy



-- migration paths (executescript on a v1 DB doesn't have the new columns



-- yet РЎвЂљР С’Р В¤ index creation TР вЂ™Р’В¦-Р’В¦- would fail on `no such column`).







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







-- Relation anchor bindings: identity-critical (per SUBSTRATE_STANCE TР В·8).



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



    module_path TEXT NOT NULL DEFAULT '',



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
,
    media_phash TEXT NOT NULL DEFAULT ''



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



-- See [docs/SYSTEM_BUILDOUT_PLAN.md] Р’В¦Р Р…TР вЂ™Р’В¦-Р’В¦Р’В¬ C.



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



    -- v18 addition: stuck_loop_count



    stuck_loop_count INTEGER NOT NULL DEFAULT 0,        -- incremented when handoff next_step repeats; reset on change



    -- v21 addition: explicit urgency. urgent / normal / background.



    urgency TEXT NOT NULL DEFAULT 'normal'



);







CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);



CREATE INDEX IF NOT EXISTS idx_tasks_principal ON tasks(principal_id);



CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);



CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);



CREATE INDEX IF NOT EXISTS idx_tasks_created_by ON tasks(created_by);



CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_for ON tasks(scheduled_for);







-- ====================================================================



-- v8 additions: provider keys (own key pool, replacing OmniRoute).



-- See [docs/SYSTEM_BUILDOUT_PLAN.md] post-Р’В¦Р Р…TР вЂ™Р’В¦-Р’В¦Р’В¬ cleanup.



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



    balance_checked_at TEXT NOT NULL DEFAULT '',



    -- v17 addition: slot routing (text-fast, text-deep, code, vision, voice, video, image_gen).



    -- Comma-separated. KeyStore.acquire_strict matches against this list.



    slot TEXT NOT NULL DEFAULT 'text'



);







CREATE INDEX IF NOT EXISTS idx_provider_keys_provider ON provider_keys(provider);



CREATE INDEX IF NOT EXISTS idx_provider_keys_status ON provider_keys(status);







-- v11 columns added below via ALTER (account_id discovered + balance snapshot)







-- Single-row provider_settings



CREATE TABLE IF NOT EXISTS provider_settings (



    id INTEGER PRIMARY KEY CHECK (id = 1),



    active_provider TEXT NOT NULL DEFAULT 'openrouter',
    default_model TEXT NOT NULL DEFAULT '',
    default_base_url TEXT NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
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



-- These columns added via ALTER TABLE in migration v8 РЎвЂљР вЂ“Р Сћ v9.



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



-- tool. Examples: ivan_status='TР вЂ�Р’В¦Р’В¬Р’В¦Р’В¬TР вЂ™', activity='TР С’Р’В¦-Р’В¦-Р’В¦-TР вЂ™Р’В¦-Р’В¦Р’В¦TР вЂ™ Р’В¦-Р’В¦-Р’В¦+ Р’В¦Р’В¬Р’В¦-TР С’TР вЂ�Р’В¦Р’В¦TР С’Р’В¦-Р’В¦-',



-- mood='TР вЂњTР вЂ�TР вЂ™Р’В¦-Р’В¦-TР пїЅР’В¦Р’В¬Р’В¦Р’В¦'. No clock heuristics РЎвЂљР С’Р В¤ she infers from conversation.



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



    parent_goal_id TEXT DEFAULT NULL,



    completed_at TEXT DEFAULT NULL,



    created_at TEXT NOT NULL,



    updated_at TEXT NOT NULL,



    FOREIGN KEY (parent_goal_id) REFERENCES goals(goal_id)



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











-- v16 addition (cont): perceptual hash for media-attached episodic events.



-- Computed via imagehash.phash on downloaded images. Allows "same image?"



-- comparisons without re-downloading or re-embedding.



-- ALTER TABLE addition handled by migration.







-- v25 addition: tool experience memory.



-- Records every tool invocation outcome so Sonya learns from experience,



-- not from prompt text. Queried by picker for success rates / cooldowns,



-- and mirrored into episodic_events for semantic recall.



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





-- ====================================================================


-- v26 additions: project runtime.


-- Projects are long-lived activity contexts, NOT tasks.


-- ====================================================================





CREATE TABLE IF NOT EXISTS projects (


    project_id TEXT PRIMARY KEY,


    title TEXT NOT NULL,


    description TEXT NOT NULL DEFAULT '',


    workspace_path TEXT NOT NULL DEFAULT '',


    status TEXT NOT NULL DEFAULT 'in_progress',


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





-- v27 additions: workspace-level full-system-access / policy.


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





-- ====================================================================


-- v29 additions: model evaluation system.


-- Scorecards, evaluation runs, and champion tracking for subagent


-- model selection. See docs/operations/MODEL_EVALUATION_SYSTEM.md.


-- ====================================================================





CREATE TABLE IF NOT EXISTS model_scorecards (


    scorecard_id TEXT PRIMARY KEY,


    model_id TEXT NOT NULL,


    provider_id TEXT NOT NULL DEFAULT '',


    domain TEXT NOT NULL DEFAULT 'general',


    -- general | programming | math | science | facts | censorship | tool_use | orchestration


    role TEXT NOT NULL DEFAULT 'auto',


    -- auto | planner | executor | reviewer | cleanup | research | coordinator


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


    -- manual | scheduled | drift | new_model


    suite_name TEXT NOT NULL DEFAULT '',


    models_json TEXT NOT NULL DEFAULT '[]',


    status TEXT NOT NULL DEFAULT 'pending',


    -- pending | running | completed | failed


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


    -- 0 = auto-selected, 1 = manually pinned by Ivan


    challengers_json TEXT NOT NULL DEFAULT '[]',


    last_evaluated_at TEXT NOT NULL DEFAULT '',


    created_at TEXT NOT NULL,


    updated_at TEXT NOT NULL


);


CREATE INDEX IF NOT EXISTS idx_cm_domain_role ON champion_models(domain, role);



CREATE INDEX IF NOT EXISTS idx_cm_model ON champion_models(model_id);



-- ====================================================================

-- v30 additions: provider model pools.

--provider_models replaces the old single-model-per-key approach.

-- Each provider has a pool of available models with metadata.

-- llm_provider.py selects from this pool based on role/cost/latency.

-- ====================================================================



CREATE TABLE IF NOT EXISTS provider_models (
    model_id TEXT NOT NULL,
    -- raw upstream ID, e.g. "openrouter/owl-alpha" or "gpt-5.4"
    provider TEXT NOT NULL,

    -- provider ID, e.g. "openrouter", "codexsale", "google"

    model_name TEXT NOT NULL,

    -- short name, e.g. "owl-alpha", "gpt-5.4"

    base_url TEXT NOT NULL DEFAULT '',

    -- empty = use provider default

    api_key_ref TEXT NOT NULL DEFAULT '',

    -- key_id in provider_keys, empty = use any key for this provider

    context_length INTEGER NOT NULL DEFAULT 131072,

    modalities_json TEXT NOT NULL DEFAULT '["text"]',

    -- ["text"], ["text","image"], ["text","image","audio"], etc.

    cost_per_1m_input_tokens REAL NOT NULL DEFAULT 0.0,

    cost_per_1m_output_tokens REAL NOT NULL DEFAULT 0.0,

    -- 0.0 = free model

    is_free INTEGER NOT NULL DEFAULT 0,

    -- 1 = free, 0 = paid

    latency_tier TEXT NOT NULL DEFAULT 'medium',

    -- "very_fast", "fast", "medium", "slow", "very_slow"

    strength_json TEXT NOT NULL DEFAULT '{}',

    -- {"coding": 0.9, "reasoning": 0.8, "math": 0.7, etc.}

    role_preference TEXT NOT NULL DEFAULT 'auto',

    -- preferred role: "planner", "executor", "reviewer", "cleanup", "research", "coordinator", "auto"

    enabled INTEGER NOT NULL DEFAULT 1,
    text_loop_ok INTEGER NOT NULL DEFAULT 1,
    -- 1 = can be used in text-loop subagent, 0 = special worker only (image/audio/etc)
    last_checked_at TEXT NOT NULL DEFAULT '',
    discovery_source TEXT NOT NULL DEFAULT 'manual',
    -- "manual", "auto-discovered", "config"

    metadata_json TEXT NOT NULL DEFAULT '{}',

    -- extra: rate limits, special flags, notes

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

-- v32: provider registry, accounts, account-specific offerings and observations.
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

-- v33: encrypted provider secrets, referenced by provider_accounts.secret_ref.
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

-- v34: current, sourced, expiring-capable world-state assertions.
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

-- ====================================================================
-- v48 additions: Memory consolidation quality (#48)
-- ====================================================================

CREATE TABLE IF NOT EXISTS consolidation_candidates (
    candidate_id TEXT PRIMARY KEY,
    statement TEXT NOT NULL,
    source_event_ids_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5,
    scope TEXT NOT NULL DEFAULT 'global',
    project_id TEXT NOT NULL DEFAULT '',
    eval_status TEXT NOT NULL DEFAULT 'pending',
    eval_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cc_status ON consolidation_candidates(eval_status);


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

-- Technical process coordination. Never injected as Sonya's world model.
CREATE TABLE IF NOT EXISTS runtime_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);


-- v24 additions: unified work items
CREATE TABLE IF NOT EXISTS work_items (
    item_id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL DEFAULT 'task',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    owner_principal_id TEXT,
    origin TEXT NOT NULL DEFAULT 'self',
    parent_item_id TEXT,
    deadline TEXT,
    dependencies_json TEXT NOT NULL DEFAULT '[]',
    progress_json TEXT NOT NULL DEFAULT '[]',
    context_anchors_json TEXT NOT NULL DEFAULT '[]',
    validation_evidence_json TEXT NOT NULL DEFAULT '[]',
    urgency TEXT NOT NULL DEFAULT 'normal',
    max_sessions INTEGER NOT NULL DEFAULT 0,
    sessions_used INTEGER NOT NULL DEFAULT 0,
    last_session_notes TEXT NOT NULL DEFAULT '',
    next_step_hint TEXT NOT NULL DEFAULT '',
    stuck_loop_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_type ON work_items(item_type);
CREATE INDEX IF NOT EXISTS idx_work_items_owner ON work_items(owner_principal_id);
