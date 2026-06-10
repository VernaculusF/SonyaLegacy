# Provider Model Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a secret-safe provider/account/model-offering runtime and migrate subagent routing to it.

**Architecture:** Add a first-class provider registry, evolve keys into accounts, map accounts to discovered model offerings, record quota/health observations, and route using capabilities plus measured evidence. Keep Sonya as the only orchestrator and expose management through typed capabilities.

**Tech Stack:** Python, SQLite substrate migrations, aiohttp/httpx provider adapters, pytest, hosted VPS systemd deployment

---

### Task 1: Freeze Current Behavior With Tests

**Files:**
- Modify: `tests/sonya/test_keystore_slot_routing.py`
- Create: `tests/sonya/test_provider_registry.py`
- Create: `tests/sonya/test_provider_account_offerings.py`

- [x] Add failing tests proving a provider can exist without a key, an account can exist without a fixed model, and a model is unavailable without an eligible account offering.
- [x] Run `pytest tests/sonya/test_provider_registry.py tests/sonya/test_provider_account_offerings.py -q` and verify failures describe missing target behavior.
- [ ] Commit the tests. Deferred because the shared worktree contains unrelated changes.

### Task 2: Add Provider Registry and Account Schema

**Files:**
- Modify: `src/sonya/state/migrations.py`
- Modify: `src/sonya/providers/keystore.py`
- Modify: `tests/sonya/test_provider_registry.py`

- [x] Add `providers`, `provider_accounts`, `provider_account_offerings`, `provider_quota_windows`, and `provider_observations` tables.
- [x] Migrate existing `provider_keys` metadata into accounts while preserving encrypted/raw secret compatibility until the secret-store task.
- [x] Add typed CRUD/read models.
- [x] Run focused migration and registry tests locally and in an isolated VPS copy.
- [ ] Commit the schema slice. Deferred because the shared worktree contains unrelated changes.

### Task 3: Add Secret-Safe Credential Boundary

**Files:**
- Create: `src/sonya/providers/secrets.py`
- Modify: `src/sonya/providers/keystore.py`
- Create: `tests/sonya/test_provider_secrets.py`

- [x] Add failing tests that reads return masked metadata and logs/traces never contain raw credentials.
- [x] Implement encrypted secret references and a compatibility migration path.
- [x] Run the secret tests and repository secret-leak checks locally and in an isolated VPS copy.
- [ ] Commit the secret boundary. Deferred because the shared worktree contains unrelated changes.

### Task 4: Extract Adapter Capability Contract

**Files:**
- Create: `src/sonya/providers/adapters/base.py`
- Create: `src/sonya/providers/adapters/openai_compatible.py`
- Create: `src/sonya/providers/adapters/google_native.py`
- Create: `tests/sonya/test_provider_adapters.py`

- [x] Define structured discovery, health, quota, and inference capabilities.
- [x] Implement OpenAI-compatible and Google-native adapters without provider-specific logic in `providers_tool.py`.
- [x] Run adapter contract tests locally and in an isolated VPS copy.
- [ ] Commit the adapter layer. Deferred because the shared worktree contains unrelated changes.

### Task 5: Implement Discovery and Observation Refresh

**Files:**
- Create: `src/sonya/providers/refresh.py`
- Modify: `src/sonya/tools/providers_tool.py`
- Create: `tests/sonya/test_provider_refresh.py`

- [x] Add failing tests for last-good snapshot preservation, account-specific access, quota reset timestamps, and substrate-backed model listing.
- [x] Implement refresh services and substrate-backed model listing.
- [x] Run focused tests locally and in an isolated VPS copy (`87 passed`).
- [ ] Commit discovery/refresh. Deferred because the shared worktree contains unrelated changes.

### Task 6: Replace Hard-Coded Subagent Routing

**Files:**
- Modify: `src/sonya/tools/subagent_model_picker.py`
- Modify: `src/sonya/providers/llm_provider.py`
- Modify: `src/sonya/tools/subagent_tool.py`
- Create: `tests/sonya/test_evidence_driven_model_routing.py`

- [x] Add failing tests that Fireworks/fixed purpose hints are absent, unavailable offerings are filtered, and scorecards/preferences produce soft ranking.
- [x] Replace `_PROFILES`, `_PURPOSE_MODEL_HINT`, and fixed fallback chains with offering queries and evidence ranking.
- [x] Add v33 legacy `provider_models` repair for live DBs missing newer columns.
- [x] Run subagent/provider suites locally and in an isolated VPS copy (`108 passed`).
- [ ] Commit routing migration. Deferred because the shared worktree contains unrelated changes.

### Task 7: Complete Sonya and Admin Management Surfaces

**Files:**
- Modify: `src/sonya/tools/providers_tool.py`
- Modify: `src/sonya/admin/server.py`
- Modify: `packages/atrium/src/ws.js`
- Create: `tests/sonya/test_provider_management_contract.py`

- [x] Implement create/update/disable/delete provider and account operations, account offering controls, quota/health inspection, and preference-bearing metadata controls.
- [x] Keep detailed controls in Admin; Atrium receives conversational status/actions only.
- [x] Add authenticated opaque secret ingestion with encrypted rotation.
- [x] Reject raw credentials from ordinary account and legacy key-add JSON/tool paths.
- [x] Run backend tests, isolated VPS tests, and frontend build.
- [x] Run the protected secret-ingestion slice in an isolated VPS copy
  (`122 passed` plus live-substrate-copy rotation/plaintext-absence smoke).
- [ ] Commit management surfaces. Deferred because the shared worktree contains unrelated changes.

### Task 8: Bootstrap and VPS Proof

**Files:**
- Modify: `docs/operations/PROVIDER_MODEL_CATALOG.md`
- Modify: `docs/STATE.md`
- Modify: `docs/HANDOFF.md`

- [ ] Securely bootstrap Nous and one OpenRouter account without writing secrets to Git/logs/prompts.
- [ ] Run local discovery, health, and routed subagent smoke tests.
- [x] Securely bootstrap the existing OpenRouter main account by migrating its
  legacy credential internally; Nous remains pending protected ingestion.
- [x] Deploy migrations and adapters to the VPS with rollback backup.
- [x] Run VPS discovery, health, picker, adapter inference, and main
  `LLMProvider` smoke tests.
- [x] Record measured OpenRouter observations in documentation.
- [ ] Commit documentation. Deferred because the shared worktree contains unrelated changes.
