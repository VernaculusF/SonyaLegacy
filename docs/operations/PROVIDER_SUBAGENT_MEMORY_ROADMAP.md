# Provider, Subagent, and Memory Roadmap

**Status:** Active execution order
**Last updated:** 2026-06-11

## Fixed Invariants

- Sonya is the environment and one continuous subject, not a selected LLM.
- Provider, account, credential, model offering, observations, and routing state
  belong in substrate.
- One provider has many accounts; one account can expose many models.
- Subagents are disposable internal tools. They are not UI actors and do not
  receive Sonya's shared memory directly.
- Atrium remains the user workspace. Detailed provider operations remain in
  Admin.

## Completed Foundation

- substrate schema v33 provider registry, accounts, account offerings, quota
  windows, observations, and encrypted provider secrets
- protected account-secret ingestion and masked read surfaces
- provider lifecycle adapters and discovery refresh service
- generic runtime refresh coordinator with provider-level TTL, account-scoped
  last-good discovery freshness, and quiet skip for pools without active
  accounts
- account-scoped lifecycle refresh: health/model discovery observations,
  offerings, and quota windows are tied to the account that was actually
  probed
- safe ignored-file provider account importer for bulk encrypted account
  bootstrap
- Kimchi production pool: 15 encrypted accounts and 8 discovered/available
  account-scoped model offerings
- substrate-backed provider/model/account routing without fixed
  provider-to-model or environment binding
- evidence-driven subagent picker over eligible account offerings
- production OpenRouter encrypted account, live discovery, and routed
  inference
- Admin backend CRUD for provider registry, accounts, offerings, and runtime
  defaults

## Active Delivery Order

### 1. Project Executor

- [x] observable project runs, traces, retries, multiple independent workers,
  and honest cancellation
- [x] model-driven decomposition without a hard-coded orchestration rule engine
- [x] dependency-aware scheduling and terminal dependency propagation
- [x] final synthesis that preserves raw worker outcomes

### 2. Measured Routing and Cooldowns

- [x] bootstrap approved Google, Nous, CodexSale, OpenRouter, Kimchi, and NVIDIA
  accounts through protected ingestion
- [x] support many accounts per provider without embedding credentials in Git,
  docs, prompts, argv, or continuity
- [x] add periodic discovery/health/quota refresh with last-good-cache behavior
- [x] feed measured project/subagent outcomes into model scorecards
- [x] repair bounded model-specific account cooldown reactivation

### 3. Pause, Approval, and Resume

- [x] honest cancellation persists across processes
- [x] pause orchestration without pretending an in-flight request is suspended
- [x] persist approval requests and decisions
- [x] expose project controls in Atrium, not Admin

### 4. Shared Memory and Knowledge Migration

- [x] inventory the production substrate using actual tables:
  `episodic_events`, `semantic_facts`, `raw_traces`, `procedural_memory`, and
  `continuity_events`
- [x] inventory `~/.sonya/knowledge/` and available legacy import sources
- [x] build a read-only migration manifest command
- [x] create a WAL-safe backup and idempotent migration manifest before any write
- [x] define deduplication rules from backup provenance analysis
- [x] prove semantic dedup apply and retrieval on a disposable backup copy
- [x] obtain explicit approval before any production semantic dedup apply
- [x] apply production semantic dedup with provenance merge and verify retrieval
- run existing Telegram history and legacy knowledge migrations where needed
- [x] prove that project work and summarized subagent outcomes enter the one shared
  memory without mixing UI chat histories

### 5. Atrium End-to-End Proof

Prove the full project-chat workflow on the live VPS and fix only gaps exposed
by that proof. Do not add Admin provider CRUD to Atrium.

### 6. Full-System-Access Policy

- [x] route project policy checks through workspace policy state
- [x] expose policy verdict source and `full_system_access` in API responses
- [x] expose the same verdict through `projects.check_policy`
- [x] prove on the live VPS that enabling full-system-access changes backend
  verdicts from project consent to workspace allowed
- [x] prove full-system-access does not automatically grant subagents wider
  filesystem scope
- next: make the Atrium UX show this policy state clearly without turning
  Atrium into Admin

## VPS Gate

Every substantial slice must be committed, pushed, deployed, and verified on
the VPS. Do not treat local execution as production proof.
