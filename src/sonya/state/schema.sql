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
