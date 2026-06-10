# Provider, Subagent, and Memory Roadmap

**Status:** Active execution order
**Last updated:** 2026-06-10

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
- substrate-backed provider/model/account routing without fixed
  provider-to-model or environment binding
- evidence-driven subagent picker over eligible account offerings
- production OpenRouter encrypted account, live discovery, and routed
  inference
- Admin backend CRUD for provider registry, accounts, offerings, and runtime
  defaults

## Active Delivery Order

### 1. Admin Provider Console

- [x] replace the legacy key-centric Providers page with provider pool,
  account, model, quota, and observation views
- [x] expose existing provider/account/offering CRUD and protected secret
  rotation
- [x] keep legacy keys visible only as migration/debug data
- [x] add a typed Admin provider refresh/probe endpoint and control
- [ ] visually verify the authenticated production page with operator access

### 2. Provider Import and Operations

- bootstrap Nous, Google AI Studio, AgentRouter, CodexSale, Kimchi, and other
  approved accounts through protected ingestion
- support many accounts per provider without embedding credentials in Git,
  docs, prompts, argv, or continuity
- add periodic discovery/health/quota refresh with last-good-cache behavior
- add measured model scorecards and provider/account cooldown handling
- research Freemodel and browser bridges separately; do not pretend they are
  ordinary OpenAI-compatible providers until proven

### 3. Subagent Runtime

- make `subagent.spawn` record requirement, chosen offering/account, reason,
  scope, cost, and outcome
- enforce disposable empty-context workers and filesystem scope
- allow Sonya to choose no delegation, one worker, or multiple workers
- evaluate carrier/worker/reviewer patterns without hard-coding recursion
- feed measured outcomes into scorecards and future routing

### 4. Memory and Knowledge Migration

- [x] inventory the production substrate using actual tables:
  `episodic_events`, `semantic_facts`, `raw_traces`, `procedural_memory`, and
  `continuity_events`
- [x] inventory `~/.sonya/knowledge/` and available legacy import sources
- [x] build a read-only migration manifest command
- [x] create a WAL-safe backup and idempotent migration manifest before any write
- [x] define deduplication rules from backup provenance analysis
- [ ] prove semantic dedup apply and retrieval on a disposable backup copy
- run existing Telegram history and legacy knowledge migrations where needed
- deduplicate, preserve provenance, and verify retrieval after migration
- prove that project work and summarized subagent outcomes enter the one shared
  memory without mixing UI chat histories

### 5. Atrium

Return to Atrium project/workspace UX after the provider, subagent, and memory
runtime is operationally trustworthy. Do not add Admin provider CRUD to Atrium.

## VPS Gate

Every substantial slice must be committed, pushed, deployed, and verified on
the VPS. Do not treat local execution as production proof.
