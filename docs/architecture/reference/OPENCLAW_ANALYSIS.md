# OPENCLAW ANALYSIS

**Status:** Active
**Type:** Reference Analysis
**Scope:** What OpenClaw contributes operationally and what must not be copied as final Sonya architecture
**Depends on:** [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
**Used by:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), bridge extraction work, runtime migration work
**Last reviewed:** 2026-05-01


## 1. Что такое OpenClaw в контексте проекта

OpenClaw для Сони - это не просто сторонний фреймворк.

Это текущая живая среда, в которой уже реально существуют:

- личностные якоря через `AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`;
- Telegram channel;
- SQLite memory database;
- hooks and autonomous routines;
- workspace-centric continuity.

То есть OpenClaw важен не как идеальный код, а как доказательство того, какие слои в живой персональной системе действительно нужны.

## 2. Что в OpenClaw сильное

### 2.1 Workspace Anchors

Личность и поведение подхватываются через явные workspace artifacts.

Это полезно потому, что:

- identity becomes inspectable;
- continuity is not purely hidden in model state;
- behavior can be reloaded after reset.

### 2.2 Memory as separate persistence

У OpenClaw уже есть сдвиг от разбросанных markdown-файлов к SQLite memory system в `memory_system/`.

Это полезно как operational lesson:

- память должна жить отдельно;
- память должна грузиться выборочно;
- long-term memory needs structure, not just transcript accumulation.

### 2.3 Heartbeat and autonomy traces

`HEARTBEAT.md` и связанные routines показывают, что initiative and maintenance tasks реально нужны.

### 2.4 Local lived complexity

OpenClaw уже показывает реальные потребности среды:

- identity anchors;
- memory maintenance;
- channel behavior;
- routines;
- hooks;
- persistence.

Это важнее красивой теории.

## 3. Что в OpenClaw слабое или ограниченное

### 3.1 Personality still heavily anchor-file dependent

Даже при наличии памяти, личность сильно завязана на prompt/workspace injection.

Это не должно остаться конечной формой Сони.

### 3.2 Ad hoc accumulation

Вокруг OpenClaw уже наросло много operational scripts, hooks and helper files.

Это нормально для живой среды, но плохо как финальная модульная архитектура.

### 3.3 Secrets and environment coupling

Конфигурация OpenClaw смешивает runtime concerns и environment-specific secrets.

Для Sonya core это unacceptable as final pattern.

### 3.4 Locality bias

OpenClaw как среда родился локально. Это оставляет след:

- loopback gateway assumptions;
- local tools;
- local secret use;
- personal machine coupling.

Для Сони это надо разорвать ранним VPS-first move.

## 4. Что берём в Sonya core

- explicit anchor docs as inspectable personality scaffolding;
- structured memory approach;
- minimal context loading idea;
- heartbeat/initiative concept;
- separation between live memory and static identity docs.

## 5. Что не берём как final architecture

- personality anchored mainly through startup prompt files;
- local machine as canonical runtime;
- flat secret-bearing config style;
- uncontrolled growth of helper scripts as architecture substitute.

## 6. Итоговый вывод

OpenClaw важен как operational ancestor.

Он уже доказал, что Соне нужны:

- anchors;
- memory;
- routines;
- channels;
- persistent artifacts.

Но Sonya core не должен быть "OpenClaw, только побольше".

Он должен взять operational truth from OpenClaw and rebuild it into a cleaner, VPS-first, growth-ready architecture.


## 7. Appendix: Code-Level Audit (2026-05-13)

This section records observations from actually reading the OpenClaw host code, not just the prior high-level description. Paths are real paths on the live host.

### 7.1 Host Layout

Host root: `C:\Users\Jester\.openclaw\`.

Top-level directories present in the live host:

- `agents/` — per-agent working roots (holds `main/` for the primary agent).
- `browser/`, `canvas/`, `completions/` — channel-/UX-specific artifacts surrounding the main runtime.
- `credentials/` — OpenClaw credential store, host-local.
- `cron/` — scheduled jobs. Stores `jobs.json` (scheduled definitions) and `jobs-state.json` (runtime state). Confirms OpenClaw already has a real scheduler surface, not just hooks.
- `delivery-queue/` — outbound work queue with a `failed/` bucket.
- `devices/` — device/identity surface for multi-device runtime.
- `exports/`, `media/` (`inbound/`, `generated/`) — artifact persistence.
- `flows/` — `registry.sqlite` plus WAL/SHM files, i.e. OpenClaw keeps a live SQLite-backed flow registry with active transactions.
- `identity/`, `settings/`, `plugins/`, `plugin-runtime-deps/`, `subagents/` — first-class subsystems, each with their own persisted state (`plugins/installs.json`, `subagents/runs.json`).
- `sonya_runtime/` — the new Sonya-owned task slice we introduced (`tasks.db`); deliberately lives beside OpenClaw’s subsystems, not inside `workspace/`.
- `tasks/`, `telegram/`, `telegram-bridge-sessions/` — operational state of the live channel.
- `workspace/` — the anchor/memory/skills/tools workspace we already extract from.
- `_tmp_omniagent/` — cloned OmniAgent repo used as reference.

Observation: OpenClaw is materially richer than “workspace + a bot”. It already has `flows`, `cron`, `delivery-queue`, `plugins`, `subagents`, `devices`, `canvas`, `completions`, `browser` as first-class subsystems. These are operational truths we must consciously decide to keep, reshape, or drop — not invisible noise.

### 7.2 `openclaw.json` in Practice

The real config shows several load-bearing design choices to preserve, and several patterns to reject.

Present and load-bearing:

- Single provider config object under `models.providers.omniroute` with `baseUrl`, `apiKey`, `api: "openai-completions"`, and a `models` array that describes each model’s `input` (text/image/video), `contextWindow`, `maxTokens`, cost, and `compat` (`supportsReasoningEffort`, `maxTokensField`). This is a provider capability matrix in practice, not a flat string. Sonya must keep a structured capability matrix rather than reducing providers to one model name.
- `agents.defaults` separates `model` (text/vision) and `imageModel`. Sonya already reflects this in `tg-bridge.model_client.resolve_image_model_name`; the reference validates that split.
- `agents.defaults.compaction` fields (`reserveTokens`, `keepRecentTokens`) — OpenClaw already models explicit context compaction budgets. Sonya’s future context evolution layer must carry at least these two knobs.
- `channels.telegram` with `dmPolicy`, `allowFrom`, `groupPolicy`, `streaming.mode`, `network.autoSelectFamily`, `network.dnsResultOrder`, `timeoutSeconds`, `pollingStallThresholdMs` — a channel adapter contract much richer than a token plus a chat id. Sonya’s channel registry must support per-channel policy, not just credentials.
- `gateway` with `port`, `mode`, `bind: "loopback"`, and `auth.mode: "token"` — OpenClaw already runs a loopback-only auth-gated HTTP surface. Treat `loopback + static token` as a real operational pattern, not something to assume out of thin air in Sonya.
- `hooks.internal.entries.working-memory-logger.enabled` — hooks are config-addressable, not just file-existence-triggered.
- `mcp.servers.exa.url` — OpenClaw already speaks MCP as a first-class integration surface. Sonya’s tool/provider layer should allow the same.

Patterns to reject as final architecture:

- API keys, bot tokens, and `gateway.auth.token` stored in plaintext in the operational config alongside behavior knobs. Sonya must separate secrets from config (env-based or secrets store).
- `env.PRISMFY_API_KEYS` stores a comma-separated list of live API keys directly inside the config. Explicit anti-pattern.
- `.bak`, `.bak.N`, `.clobbered.<iso>`, and `.last-good` siblings of `openclaw.json`. OpenClaw’s config evolution strategy is “write backup next to file”. That is acceptable as lived reality, but Sonya must not elevate this into final config lifecycle — use versioned structured config with a real migration pipeline instead.
- `commands.exec.security: "full"` with `ask: "off"` — tool execution trust baked into config. Sonya must not let trust level live in one free-text string.

### 7.3 `telegram-bridge.mjs` as Operational Ground Truth

The bridge is a 501-line Node.js file at the host root, composed of: config/state read, JSON/event-stream response parsing, Telegram HTTP, a bootstrap loader that reads `AGENTS.md / SOUL.md / HEARTBEAT.md / IDENTITY.md` and runs `memory_system/context_loader.py full 7`, three completion paths (text / vision / image generation), post-response hook invocation via environment variables, and a long-polling `main()` loop.

Important operational specifics that reference analysis must preserve:

- **Input classification, attachment extraction, OpenRouter event-stream parsing** live in `workspace/tools/telegram-bridge-media.mjs`. Sonya already ported that; reference validates the split.
- **HTML rendering and chunking** live in `workspace/tools/telegram-bridge-format.mjs`. Same situation.
- **Bootstrap contract**: the system prompt concatenates `AGENTS.md`, `SOUL.md`, an optional `IDENTITY.md`, `HEARTBEAT.md`, and the stdout of `context_loader.py full 7`, with explicit runtime rules appended after. Sonya must preserve the ordering and the rule that memory context ends up in the system message, not in user content.
- **Post-response hook** is invoked via `spawnSync("python", "memory_system/post_response_hook.py")` with env `OPENCLAW_SESSION_ID`, `OPENCLAW_LAST_USER_MSG`, `OPENCLAW_LAST_ASSISTANT_MSG`. This is a cross-process contract. Any reshaping of memory must preserve or explicitly replace it before breaking it.
- **Session files**: `telegram-bridge-sessions/<chatId>.json`, truncated to the last 20 messages on save. This is the only dialog memory Sonya currently has per chat.
- **Raw updates** are appended as JSONL into `telegram/raw-updates.jsonl` before `handleUpdate`. OpenClaw keeps an audit of every incoming Telegram update; Sonya inherited that in `tg-bridge` and should keep it.
- **Update ordering bug in origin**: the original JS advances `state.offset` before `handleUpdate` finishes. If `handleUpdate` crashes, the update is silently dropped. Sonya already fixed this in the Python port by moving `handle_update` before offset advance. This is a concrete case where “preserving OpenClaw operational truth” explicitly meant correcting a bug, not copying behavior blindly.

### 7.4 `memory_system/` — Real Shape of OpenClaw Memory

`workspace/memory_system/` is not a single DB with a loader. It is a small framework:

- `schema.sql` defines tables `facts`, `events`, `emotions`, `goals`, `lessons`, `research` with real indexes. This is a structured long-term memory model, already beyond “chat transcript”.
- `schema_working_memory.sql` adds a separate `working_memory` table, session-scoped, with types `emotion | thought | focus | context | unfinished`, importance, estimated `tokens`, and metadata JSON. Working memory is a first-class artifact in OpenClaw, not a side effect of prompt history.
- `memory_api.py` exposes a `MemoryDB` class with CRUD and search for each table, plus `add_working_memory`, `get_working_memory_tokens`, `prune_working_memory` (importance-weighted), and an `export_context(days)` that returns a categorized snapshot.
- `context_loader.py` is what the bridge actually runs. It pulls `MemoryDB.export_context`, grabs working memory by session, optionally calls `rag_integration.get_rag().search_formatted()` with startup queries, and renders a multi-section Markdown block (`FACTS ABOUT JESTER`, `OUR RELATIONSHIP`, `RECENT EVENTS`, `ACTIVE GOALS`, `LESSONS LEARNED`, `EMOTIONAL CONTEXT`, optional `RECENT RESEARCH`). Deduplication is explicit.
- `post_response_hook.py` writes working memory via `working_memory_auto_logger.log_mental_state` and conditionally appends an event via `MemoryDB.add_event` when content passes a “is this worth remembering” heuristic based on length, importance score, and a hard-coded list of strong markers (`паметь`, `проект`, `архитект`, `agi`, `rwkv`, `сознание`, etc.). Importance 5 always persists.
- A `rag_*` family (`rag_indexer`, `rag_integration`, `rag_service`, `rag_search`, `rag_query_helper`, `rag_auto_re*`, `rag_context`) implements chunk-based retrieval on top of `memory.db` and is already used by `context_loader` if available.
- `working_memory_auto_logger.py` (referenced from post-response hook) and `consolidate.py` (6 KB) point at a consolidation pipeline, not a nightly stub.

Operational lessons Sonya must carry:

- Long-term memory is split into at least six orthogonal tables, not one blob. Any future Sonya-owned memory core must keep this domain separation from day one.
- Working memory is session-scoped with importance-based pruning by token budget. Sonya must not flatten this back into “a conversation history slice”.
- Post-response persistence is selective and policy-driven, not always-on. Sonya must make the selection policy first-class and visible, instead of inheriting a silent hard-coded marker list.
- RAG already exists on top of memory content. Sonya must either keep that bridge or replace it with a cleaner retrieval contract, not pretend memory is only SQL tables.
- Events carry `importance` (1–5) and JSON `tags`. Keep those at minimum in Sonya’s event schema.

Operational constraints to reject for Sonya-owned memory:

- The existing strong-marker list is a hard-coded Russian-biased regex. It is an emergency heuristic, not a policy layer. Sonya must expose it as a configurable policy, not inherit the list verbatim.
- `MemoryDB` opens and closes a new SQLite connection in many methods. Acceptable for a bridge hook, not for a long-lived runtime. Sonya’s memory layer must hold the connection across a process.
- Several schema tables assume one user (`Jester` vs `Sonya`). Sonya’s principal layer must replace this with principal IDs.

### 7.5 Workspace: Hooks, Skills, Tools

- `workspace/hooks/working-memory-logger/` is the only hook directory. Hooks are folder-based units, not per-event scripts scattered around.
- `workspace/skills/` already contains concrete skill folders: `agent-browser-clawdbot`, `image-handler`, `image-ocr-reader`, `marketing-strategy-pmm`, `prismfy-search` (bundles its own `jq.exe`), `read-word`, `self-improving-agent`, `skill-finder-cn`, `vision-analyze`, `web-search-exa`. Each holds `SKILL.md` with YAML frontmatter (`name`, `description`), optional scripts and helpers, a `_meta.json` with `ownerId`, `slug`, `version`, and `publishedAt`, and sometimes a `.clawhub` marker.
- `workspace/tools/` currently carries the bridge helpers (`telegram-bridge-format.mjs`, `telegram-bridge-media.mjs`) and `export-telegram-dialogs`. Tools are host-level utility code, separate from skills.

What this means for Sonya:

- A skill is a directory with a YAML-frontmatter markdown spec plus optional assets, with a registry provenance (`_meta.json.ownerId/slug/version`). Sonya’s skill registry should keep skills as self-contained directories with explicit spec + metadata, not as code modules with implicit capabilities.
- “Hub-installable skills” is already a real concept (`clawdhub`, `_meta.json`). Sonya does not have to build this now, but must not prevent it later.
- `self-improving-agent` is not a stub. It defines a real flow: write to `.learnings/{LEARNINGS,ERRORS,FEATURE_REQUESTS}.md` with schemas, promote to governing docs, support multi-agent activation, optionally auto-extract skills. Sonya’s skill evolution track can borrow this explicit promotion contract instead of reinventing it.

### 7.6 Root-Level Operational Artifacts

- `exec-approvals.json` — there is already a persistent approvals surface on disk. Sonya’s harness approval gate must not pretend this is novel; it should match the existing shape or define a clean replacement.
- `update-check.json` + `.tmp` — there is an auto-update path. Out of scope for Sonya, but must not be accidentally broken by config writes.
- `health-check.ps1` (~6.8 KB) — real operational health check, already referenced from the implementation plan. Sonya should end up with an equivalent health endpoint owned by the runtime, not by a PowerShell script.
- `telegram-bridge.log` grows into hundreds of KB. Already expected. Sonya’s logger must rotate or the runtime must.

### 7.7 Summary Of Additions

Concrete items added to the “take from OpenClaw” list:

- structured provider capability matrix with per-model `input`, `contextWindow`, `maxTokens`, `cost`, `compat`;
- separate text/vision model and image-generation model;
- explicit compaction budget fields (`reserveTokens`, `keepRecentTokens`);
- rich per-channel policy (DM/group, allowlist, streaming mode, network family, timeouts, stall threshold);
- loopback-bound auth-token-gated gateway as a valid lived pattern;
- MCP server list as a first-class integration surface;
- six-table structured long-term memory (`facts`, `events`, `emotions`, `goals`, `lessons`, `research`);
- session-scoped working memory with type + importance + token budget;
- selective, policy-driven post-response event persistence;
- RAG retrieval over memory content;
- skill-as-directory with YAML spec, `_meta.json`, optional `.clawhub` provenance;
- `.learnings/` as an append-only self-improvement artifact;
- config-addressable hooks (`hooks.internal.entries.*.enabled`);
- `flows/registry.sqlite` + `cron/jobs.json` as evidence of a live scheduler layer, not only hooks.

Concrete items added to the “do not copy” list:

- secrets inside operational JSON, including bot tokens and gateway tokens;
- `env.PRISMFY_API_KEYS` as a comma-separated secret list;
- `.bak / .clobbered / .last-good` sibling files as config lifecycle;
- `commands.exec.security: "full"` + `ask: "off"` as a substitute for a real approval policy;
- hard-coded Russian-biased importance markers in `post_response_hook.py`;
- opening and closing a SQLite connection per memory method from a long-lived runtime;
- `MemoryDB` schema hard-coding `Jester` / `Sonya` as principals.
