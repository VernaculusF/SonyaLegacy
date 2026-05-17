# REFERENCE SYSTEMS ANALYSIS

**Status:** Stale (frozen as 2026-05-13 reference snapshot)
**Type:** Reference Analysis
**Scope:** High-level policy for using OpenClaw, Hermes, and OmniAgent as references instead of foundations
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
**Used by:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), historical reference
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):** Frozen reference snapshot. Sonya is now decoupled from OpenClaw operationally — many "must carry" inheritance claims (provider capability matrix, compaction budget fields, per-channel policy, etc.) were not in fact carried into `src/sonya/`. The Hermes/OmniAgent posture analysis remains valid as direction. Don't read this as "what got inherited"; read it as "what was considered and what to remember when building forward."


## 1. Назначение документа

Этот документ фиксирует, как проект Сони должен относиться к трём reference-системам:

- OpenClaw
- Hermes
- OmniAgent

Его задача:

- отделить заимствование идей от слепого копирования;
- зафиксировать, что каждая система даёт полезного;
- зафиксировать, что в каждой нельзя тащить в ядро Сони как есть;
- дать основу для корректировки implementation plans.

## 2. Статус трёх систем

### OpenClaw

Это не просто внешний референс, а текущая живая личная среда, в которой уже существуют:

- workspace-based identity injection;
- Telegram channel;
- memory database;
- heartbeat routines;
- hooks;
- локальные интеграции и локальные ключи.

### Hermes

Это не локальный готовый кодовый reference в текущем workspace, а архитектурная роль из [`ОСНОВА.md`](C:/Users/Jester/Desktop/план/ОСНОВА.md:452).

Для проекта Соня `Hermes` означает:

- оркестратор;
- оболочка над каналами;
- body/signal adapter layer;
- event bridge between cognition and world.

### OmniAgent

Это сторонний агентный framework, локально представленный клоном в `C:\Users\Jester\.openclaw\_tmp_omniagent`, с сильным маркетинговым заявлением:

- realtime skill evolution;
- context evolution;
- brain evolution;
- hyper-harness;
- deep reflexion.

Но как reference он должен рассматриваться критически.

## 3. Главное различие ролей

- `OpenClaw` даёт фактический живой operational опыт.
- `Hermes` даёт целевой образ оркестратора и world-facing shell.
- `OmniAgent` даёт набор амбициозных концептов и частично полезный vocabulary for future modules.

Их нельзя рассматривать как взаимозаменяемые.

## 4. Что мы берём у каждой системы

### Из OpenClaw

- идея workspace anchors (`AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`);
- идея долговременной памяти вне чата;
- идея session continuity through persistent artifacts;
- event/hook-based behavior;
- практический опыт того, что реально нужно живой персональной среде.

### Из Hermes

- роль отдельного оркестратора;
- разделение "мозга" и "внешней оболочки";
- adapters for channels, body, avatar, signals;
- event-driven integration between cognition and embodiment.

### Из OmniAgent

- vocabulary around skill/context/brain evolution;
- dual-loop reflexion direction;
- idea that harness must be more than one static scanner;
- idea of separating security/review layers from response generation.

## 5. Что нельзя брать как есть

### Из OpenClaw

- жёсткую зависимость личности от workspace injection как единственного механизма;
- flat local config with environment-specific secrets mixed into operational config;
- накопившиеся ad hoc hooks and scripts as final architecture;
- локальность как норму.

### Из Hermes

- слишком раннюю привязку к heavy embodiment path;
- смешивание orchestration role с философским смыслом системы;
- зависимость архитектуры MVP от наличия полного body-track.

### Из OmniAgent

- доверие README claims как реальному состоянию кода;
- gateway surface without hardened auth model;
- заявленные channels without verifying runtime truth;
- саму кодовую базу как фундамент Сони.

## 6. Итоговая позиция проекта

### OpenClaw

Используется как:

- operational ancestor;
- источник практических требований;
- источник данных и наблюдений.

Не используется как:

- финальное ядро Сони;
- готовая архитектура для роста в сторону AGI.

### Hermes

Используется как:

- архитектурная роль оркестратора;
- будущая внешняя оболочка среды.

Не используется как:

- обязательная ранняя кодовая зависимость;
- причина откладывать MVP без body path.

### OmniAgent

Используется как:

- словарь модулей;
- частичный conceptual reference;
- источник warning signs.

Не используется как:

- фундамент runtime;
- trusted direct base for Sonya core.

## 7. Практический вывод

Все последующие implementation plans должны проверяться против этого правила:

- брать operational lessons from OpenClaw;
- строить orchestration role in the spirit of Hermes;
- заимствовать только проверяемые идеи from OmniAgent;
- не тянуть ни одну из трёх систем как конечную архитектурную истину.


## 8. Appendix: Code-Level Reference Pass (2026-05-13)

This appendix records the conclusions of a concrete pass over the three reference systems’ actual code, not only their teaching material. Detailed per-system evidence lives in:

- [OPENCLAW_ANALYSIS.md — “Code-Level Audit (2026-05-13)”](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)
- [OMNIAGENT_ANALYSIS.md — “Code-Level Audit (2026-05-13)”](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)
- [HERMES_ANALYSIS.md — “Code-Level Audit (2026-05-13)”](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md)

### 8.1 What Changed vs The Previous Version

Previously this file treated the three systems as largely interchangeable reference objects based on their documentation and role descriptions. A direct code pass changes three things:

- **OpenClaw is materially richer than “workspace + Telegram”.** It already hosts `flows/`, `cron/`, `delivery-queue/`, `plugins/`, `subagents/`, `devices/`, `canvas/`, `completions/`, `browser/`, a first-class MCP entry, a structured six-table long-term memory plus a separate working-memory table, an RAG layer, a config-addressable hook registry, and a loopback-bound gateway with token auth. We owe it more credit as an operational ancestor.
- **OmniAgent is not vaporware.** It is a real, GPL-3.0 Python codebase with an event bus, a concrete Agent abstract, multiple provider adapters, a three-part security stack (policy + approval + audit), a dataclass-driven skill evolution pipeline, a dataclass-driven context evolution pipeline, a Sentinel planner, a Guardian reviewer, and an optional RL proxy for self-hosted models. Our prior characterization understated that. The rejection stands, but with more precise reasons: license contagion, plaintext secrets in `config.yaml`, overclaim framing (“unbypassable”), monolithic files, and an RL path that only applies when you host your own model.
- **Hermes is code-level absent.** There is no Hermes package or artifact in either the OpenClaw host or the OmniAgent clone. It stays architectural-role-only. What currently plays the Hermes role in reality is the aggregate of OpenClaw’s `telegram-bridge.mjs`, `gateway`, `flows`, `cron`, and `workspace/hooks/`.

### 8.2 Updated Posture

OpenClaw:

- **Use as operational ancestor**, with explicit inheritance of: structured provider capability matrix, text/vision vs image-generation split, compaction budget fields, per-channel policy, loopback + token gateway pattern, MCP servers, six-table memory + session-scoped working memory, selective policy-driven post-response persistence, RAG over memory, skill-as-directory with YAML spec + `_meta.json`, `.learnings/` append-only self-improvement artifact, config-addressable hooks, scheduler evidence via `flows/registry.sqlite` and `cron/jobs.json`.
- **Reject as final shape**: secrets in operational JSON, `.bak/.clobbered/.last-good` as config lifecycle, `commands.exec.security: "full"` + `ask: "off"` as trust policy, hard-coded language-biased importance heuristics, SQLite-per-call patterns from a long-lived runtime, `Jester`/`Sonya`-as-principal schema constants.

OmniAgent:

- **Use as concrete reference** for: `Agent` abstract + `AgentResult` split, `IncomingMessage` / `OutgoingMessage` dataclasses, first-class `EventBus` + `EventType`, dataclass-backed persisted artifacts (`ExecutionPattern`, `SkillPatch`, `CompiledSkill`, `ApprovalRequest`, `AuditEvent`, `Milestone`, `TaskPlan`, `Lesson`), three-part security split (policy / approval / audit), `create_llm_provider` factory with explicit enum backends, `ToolProfile` presets (MINIMAL / CODING / FULL) with named allowed tools and required-approval sets, Guardian’s curated high-risk bash regex list as a seed, Sentinel’s multi-step detection + milestone decomposition, RL-proxy shape as a future BrainModel-evolution adapter.
- **Reject as base**: GPL-3.0 license contagion via code copy, plaintext `api_key` in `~/.omniagent/config.yaml`, “unbypassable” framing, 50+ KB single-file modules, `python-telegram-bot`-based Telegram adapter (parity-regressive vs our tested raw HTTP port), “BrainModel self-evolution” as a generic claim (it is local-inference only in code).

Hermes:

- **Treat as architectural role only.** No code to audit until an actual Hermes surface becomes available in this workspace.
- The Sonya-side counterpart is our own future `sonya_runtime/channels/*`, `routing/*`, `scheduler/*`, `delivery/*`, `hooks/*` — not an external dependency.

### 8.3 Rules Reinforced By The Code Pass

- **No code copy from OmniAgent.** License contagion is a real risk. Only schemas and interface shapes may be reimplemented, always with attribution in the per-system appendix.
- **Secrets are not config.** Both OpenClaw and OmniAgent violate this in opposite directions (one in JSON, one in YAML). Sonya must separate secrets from behavior knobs from day one.
- **Channel adapters are plural, and not interchangeable.** The production OpenClaw Telegram bridge and the OmniAgent Telegram channel use different libraries (raw HTTP vs `python-telegram-bot`). Channel parity is a per-adapter contract, not a shared one.
- **BrainModel evolution is not a remote-provider feature.** Any RL/self-host claim must be gated on an actually-local model backend.
- **Harness is three things, not one.** Policy decision, approval flow, and audit log are distinct objects. Sonya already says this in [cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md); OmniAgent’s code confirms the split is workable.
- **Operational complexity is real.** OpenClaw demonstrates that a lived system grows `flows / cron / delivery-queue / plugins / subagents / devices` on its own. Sonya’s runtime decomposition must keep room for those.

### 8.4 What This Unblocks

With the code-level pass recorded, the next implementation plans can now satisfy [ARCHITECTURE_PLAN.md §11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md) honestly. For each new subplan we can answer:

1. **What operational truth from OpenClaw does it preserve?** Pointable to specific host files or tables.
2. **Which orchestration boundary from Hermes does it respect?** Expressed as a concrete responsibility of `sonya_runtime/*`, since no external Hermes exists.
3. **Which tempting OmniAgent shortcut does it explicitly reject?** Pointable to specific OmniAgent files or design choices that we refuse to copy.

Before this pass, those answers would have been generic. Now they can be concrete and auditable.
