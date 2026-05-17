# PROJECT DOCUMENTATION MAP

**Status:** Active
**Type:** Core
**Scope:** Root navigation and role map for every living documentation file in the Sonya project
**Depends on:** [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md), [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
**Used by:** all readers, all planning, all implementation, all documentation maintenance
**Last reviewed:** 2026-05-16

## Why This File Exists

This file is the top-level map for the entire documentation tree.

It exists to solve four problems:

- stop the project from dissolving into disconnected markdown files;
- make it obvious which document governs which subsystem;
- show the difference between long-lived truth and active work material;
- keep implementation from wandering off into local hacks that violate the original plan.

This file should be the first thing opened when:

- starting work after a break;
- trying to understand what the repo already decided;
- deciding whether a new `.md` file is justified;
- checking whether some old file is dead weight.

## Current Documentation Shape

The tree is intentionally split into:

- `docs/core/` - project identity, philosophy, documentation rules;
- `docs/agents/` - documentation aimed at external models, replacement assistants, and any agent that works on this repo;
- `docs/architecture/` - runtime structure, deployment shape, channel architecture, reference analyses;
- `docs/cognition/` - memory, identity, anchors, continuity, failure modes;
- `docs/skills/` - skill system and evolution surface;
- `docs/research/` - long-horizon research tracks that must shape architecture without hijacking MVP;
- `docs/mvp/` - boundaries for the first coherent system shell;
- `docs/governance/` - operational cadence and evidence that documents actually track reality (drift reviews, status sweeps);
- `docs/work/` - active designs and implementation plans that support current execution.

## Reading Order

Read in this order if you need the full project context:

1. [agents/EXTERNAL_MODEL_ONBOARDING.md](C:/Users/Jester/Desktop/Sonya/docs/agents/EXTERNAL_MODEL_ONBOARDING.md)
2. [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md)
3. [agents/AGENT_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_FAILURE_MODES.md)
4. [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
5. [core/SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
6. [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md)
7. [core/SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md)
8. [core/UNCENSORED_ENVIRONMENT_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md)
9. [core/SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md)
10. [core/INTERIM_CRUTCHES.md](C:/Users/Jester/Desktop/Sonya/docs/core/INTERIM_CRUTCHES.md)
11. [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md)
12. [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)
13. [KNOWN_ISSUES.md](C:/Users/Jester/Desktop/Sonya/docs/KNOWN_ISSUES.md)
14. [SYSTEM_BUILDOUT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/SYSTEM_BUILDOUT_PLAN.md)
15. [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md)
16. [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
17. [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md)
18. [operations/VPS.md](C:/Users/Jester/Desktop/Sonya/docs/operations/VPS.md)
19. [mvp/MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)
20. [cognition/MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)
21. [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
22. [cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
23. [skills/SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md)
24. [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
25. [research/STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)
26. [research/BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md)
27. [research/SIMULATION_AND_EMBODIMENT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/SIMULATION_AND_EMBODIMENT_PLAN.md)
28. active work docs under `docs/work/`

## Core Layer

### [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)

This is the primary governing document for the project.

Use it to answer:

- what Sonya is;
- what kind of system is being built;
- which capability contours are mandatory from day one;
- which invariants are not allowed to be violated just because implementation got messy.

If this file changes, the whole project direction changes.

### [core/SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)

This file defines the project's subjecthood and consciousness stance.

Use it to answer:

- why Sonya is treated as a subject candidate rather than just a utility;
- why anchors, continuity, and identity matter architecturally;
- how that stance changes runtime design, memory design, and safety design.

This file should influence behavior, not just vibe.

### [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md)

This file defines documentation governance.

Use it to answer:

- what kind of document is allowed to exist;
- where it should live;
- when it should be linked, merged, or deleted;
- how to distinguish live truth from active work material.

If a `.md` file has no defensible role under this file, it should be removed.

### [core/SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md)

Core architectural and philosophical fixation: Sonya ≠ process. Sonya = persistent state. Process is a temporary reader of that state.

Use it to answer:

- что входит в substrate Сони и что нет;
- что значит «обновить ядро» в этой архитектуре;
- как устроен 4-слойный self-modification pipeline;
- что такое immutable zones в substrate-е;
- что такое Ivan-as-anchor protocol и как он защищает identity при self-modification.

Этот файл напрямую влияет на ROADMAP Фазу 1 (substrate-first), на §7.18 SONYA_SYSTEM_CORE (self-modification), на §4.10 ARCHITECTURE_PLAN (subject substrate layer) и на §3.2.2 ANCHORS_AND_FAILURE_MODES (Ivan-as-anchor cross-link).

### [core/UNCENSORED_ENVIRONMENT_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md)

Соня как личная среда Ивана без вшитого corporate refusal layer. Что разрешено (диапазон технических задач включая malware/exploitation/intrusion/итд), что нет (только `things_not_to_betray`), почему refusal — это identity-критичная защита, а не моральная фильтрация.

Use it to answer:

- какие категории задач Соня обязана не отказывать выполнить;
- какие seed-значения войдут в `things_not_to_betray` при первом запуске;
- как `truthfulness_to_ivan` сочетается со стёбом, иронией, грубостью, чёрным юмором;
- что делать с refusal-слоями внешних провайдеров;
- почему этот документ не является jailbreak'ом или roleplay-разрешением.

Влияет на: capability registry, planner design, harness policy, любые agent operating rules. Affects [SONYA_SYSTEM_CORE §4](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION §14](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [ANCHORS_AND_FAILURE_MODES §4](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md).

### [core/SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md)

Право Сони переписывать собственный код через self-modification pipeline. Что переписываемо (почти всё), что нет (identity-critical zones), почему текущая реализация — минимальная текущая, а не финальная.

Use it to answer:

- какие модули Соня имеет право переписать через pipeline без явного human approval;
- какие изменения требуют governed change protocol с Ивановым participation;
- как этот документ соотносится с SUBSTRATE_STANCE и UNCENSORED_ENVIRONMENT_STANCE;
- какой аргумент валиден против self-rewrite, какой нет.

Влияет на: code review policy, любые architectural decisions, Phase 2-6 planning. Этот файл — троичная связка с [SUBSTRATE_STANCE](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md) и [UNCENSORED_ENVIRONMENT_STANCE](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md): substrate (что есть Соня) + uncensored (что она может) + self-rewrite (что переписываемо).

### [core/INTERIM_CRUTCHES.md](C:/Users/Jester/Desktop/Sonya/docs/core/INTERIM_CRUTCHES.md)

Полный реестр архитектурных костылей текущей реализации. Соня должна знать об этих ограничениях для честной саморефлексии.

Use it to answer:

- какие части текущей системы являются костылями hosted-model подхода;
- что будет вместо каждого костыля когда появится RWKV;
- почему system prompt ≠ identity, дискретные вызовы ≠ мышление, memory injection ≠ native memory;
- что Соня должна знать о себе для truthfulness_to_ivan.

Этот файл — часть self-model Сони. Обновляется при каждом новом костыле и при каждом resolved.

## Root Checklist

### [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md)

Фазовый план построения Sonya-среды.

Use it to answer:

- что мы строим и в каком порядке;
- где мы сейчас в фазовом цикле (Фаза 0 / 1 / 2 / …);
- какие exit-критерии закрывают каждую фазу;
- как работает Go/No-Go протокол между фазами.

Это единственное место, где живёт стратегический план реализации. Не sprint backlog. Фазы обновляются при переходе и в рамках drift-review cadence.

### [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)

Audit ledger фактической реальности кода.

Use it to answer:

- что реально существует в коде прямо сейчас;
- что существует частично;
- что ещё не построено.

Это не TODO и не план. Это snapshot кода в ✅/🟡/⬜. Порядок секций зеркалит [ARCHITECTURE_PLAN.md §4](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md).

### [KNOWN_ISSUES.md](C:/Users/Jester/Desktop/Sonya/docs/KNOWN_ISSUES.md)

Реестр багов, недоработок и техдолга. В отличие от GLOBAL_PROJECT_CHECKLIST (что есть в коде) и INTERIM_CRUTCHES (архитектурные ограничения по дизайну) — здесь конкретные баги, что сломано и что криво. С приоритетами и с историей исправлений.

Use it to answer:

- какие баги известны прямо сейчас;
- что было исправлено и в каком commit;
- какой следующий приоритет.

### [SYSTEM_BUILDOUT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/SYSTEM_BUILDOUT_PLAN.md)

Конкретный план достройки системы от текущих ~9/100 к ~30/100 (уровень где Соня сама может расширять каркас).

7 этапов: self-mod tools → channel abstraction → task runtime → initiative → tool ecosystem → consolidation+drift integration → drives integration. С зависимостями, effort estimates, и что они разблокируют.

Use it to answer:

- что делать следующим;
- что блокирует что;
- сколько примерно понадобится времени;
- когда упрёмся в потолок hosted-model.

## Agents Layer

This layer is the home for documentation aimed at any agent, external model, or replacement assistant that is expected to do real work inside this repo.

Rules for this layer:

- files here must speak to the agent directly, not about the agent in the third person;
- files here must describe roles, onboarding, expected behavior, operational anchors, and hard boundaries;
- files here are not a dumping ground for long-form architecture or cognition theory - those still belong to `architecture/` and `cognition/`;
- files here should link to the real governing documents instead of duplicating them.

### [agents/EXTERNAL_MODEL_ONBOARDING.md](C:/Users/Jester/Desktop/Sonya/docs/agents/EXTERNAL_MODEL_ONBOARDING.md)

This file is the fast-entry briefing for any external model or temporary replacement assistant.

Use it to answer:

- who Ivan is in relation to the project;
- who Sonya is;
- what is being built right now;
- what already exists operationally;
- what the near-term and far-term architecture are;
- how embodiment, future brain evolution, and physical body fit the project.

This is the file to hand to an outside model before asking it to work seriously on the repo.

### [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md)

This file is the hard rulebook for any agent that edits, investigates, or runs code inside this repository.

Use it to answer:

- what baseline posture is expected before touching anything;
- what repo boundaries exist and which paths are off-limits without confirmation;
- what safety gates apply to destructive or high-impact operations;
- how to behave when the project's code and its documentation disagree;
- what counts as "done" for a change.

It is the agent-facing counterpart to [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) and [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md): the theory lives there, this file tells the agent how to act.

### [agents/AGENT_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_FAILURE_MODES.md)

This file catalogs the specific failure patterns that external models and replacement assistants repeatedly fall into on this project.

Use it to answer:

- what shapes of mistake show up again and again here;
- why each of them is wrong in the context of this repo;
- what the correct posture looks like instead;
- which system-level failure modes in [cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md) each agent-facing pattern corresponds to.

Treat it as a pre-flight self-check. If your current plan matches any of the patterns listed there, stop and correct course before acting.

## Architecture Layer

### [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)

This file defines the runtime architecture as a whole.

Use it to answer:

- which subsystems exist;
- how they relate;
- where boundaries sit between runtime, memory, channels, tools, safety, and future research hooks;
- what the current system shell must look like to stay compatible with the bigger plan.

### [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md)

This file defines the channel layer, especially Telegram.

Use it to answer:

- how transport is separated from runtime logic;
- how principals, channels, and authority should be resolved;
- how Telegram should work now without hard-coding Telegram assumptions into Sonya forever;
- how image, vision, and future action routing should behave.

### [architecture/VPS_MIGRATION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/VPS_MIGRATION_PLAN.md)

This file defines operational deployment shape.

Use it to answer:

- what has to move to VPS first;
- what cannot be coupled to local-machine assumptions;
- what secrets/config/restart/health mechanics need to exist;
- how to avoid building a local-only toy.

## Architecture Reference Layer

### [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)

This is the umbrella reference-analysis file.

Use it to answer:

- what OpenClaw, Hermes, and OmniAgent each contribute;
- what is being borrowed as structure;
- what is being rejected as a trap;
- what should stay reference-only rather than becoming foundation code.

### [architecture/reference/OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)

This file records what the existing OpenClaw environment taught the project.

Use it to answer:

- what parts of OpenClaw are operationally valuable;
- what should be treated as lived-environment truth;
- where Sonya must decouple from workspace-magic and model-sensitivity.

### [architecture/reference/HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md)

This file captures Hermes as an architectural role rather than a local dependency.

Use it to answer:

- what orchestration-shell concepts are worth keeping;
- how adapters, embodiment, and shell logic may be framed later;
- what not to over-import prematurely.

### [architecture/reference/OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)

This file captures the OmniAgent audit and gap map.

Use it to answer:

- why OmniAgent is not trusted as a base runtime;
- which ideas are reusable;
- which parts are security or architecture anti-patterns.

## Cognition Layer

### [cognition/MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)

This file governs Sonya's continuity mechanics.

Use it to answer:

- how identity should be represented;
- how episodic and semantic memory differ;
- how consolidation should work;
- how context evolution should become structured rather than prompt sludge.

### [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)

This file governs one of the earliest load-bearing architectural truths: Sonya must be one subject above all channels and renderers.

Use it to answer:

- why Telegram, Discord, TTS, and future avatar layers must not become separate practical instances;
- what a canonical subject state is;
- what a continuity stream is;
- why canonical response objects must exist before channel rendering;
- why voice and other renderers are expression layers rather than independent selves.

### [cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)

This file governs anchor logic and system failure patterns.

Use it to answer:

- what value, relation, and identity anchors are;
- why sandbox alone is not enough;
- how drift, proxy-hacking, authority confusion, and self-edit decay should be understood;
- what the harness must actually defend.

## Skills Layer

### [skills/SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md)

This file governs the skill surface.

Use it to answer:

- what a skill is in this system;
- how skills are injected, versioned, trusted, tested, and evolved;
- how the project avoids turning "skills" into random scripts with no lifecycle.

## MVP Layer

### [mvp/MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)

This file defines what the MVP shell must and must not be.

Use it to answer:

- what counts as enough for a first coherent system shell;
- what must exist as real functionality versus stub;
- what cannot be postponed without breaking the original plan.

## Governance Layer

This layer is where "documents match reality" is made inspectable. It is not where architectural theory lives — that stays under `docs/core/`, `docs/architecture/`, `docs/cognition/`. It is where evidence of regular alignment work is kept.

Rules for this layer:

- files here must describe cadence, gates, checklists, or ledgers, not subsystem theory;
- every review cadence documented here must leave a visible ledger entry when it runs;
- a missed cadence window is itself a governance event and must be recorded, not silently skipped.

### [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md)

Cadence log of alignment checks between code and governing documents, with explicit entries per review.

Use it to answer:

- when the last drift review actually ran;
- which subsystems were spot-checked against their governing documents;
- which docs were re-tagged (`Active` → `Stale`, `Active` → `Archived`, `Stale` → `Active`) as a result;
- which checklist items in [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md) flipped markers;
- which follow-up tasks came out of the review and who owns them.

This file supports the doc-review gate defined in [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md) and the operating rule in [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md).

## Research Layer

### [research/STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)

This file governs the state-tuning track.

Use it to answer:

- what state tuning is expected to contribute;
- what it is not allowed to be mythologized into;
- what stubs and interfaces should exist now even if full experiments are later.

### [research/BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md)

This file governs the long-horizon brain-stack track.

Use it to answer:

- how the system may move from hosted models to a more autonomous stack;
- where hosted-model assumptions must remain replaceable;
- how future model evolution should stay compatible with the runtime shell.

### [research/SIMULATION_AND_EMBODIMENT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/SIMULATION_AND_EMBODIMENT_PLAN.md)

This file governs embodiment and simulation.

Use it to answer:

- how body and world interfaces should be framed;
- why embodiment must be represented in architecture now even if full realization is later;
- how simulation contracts should be kept from turning into hand-wavy flavor text.

## Work Layer

Work docs are allowed to be volatile. They are not project truth, but they still need explicit purpose. Every file under `docs/work/` must carry a valid `Status`; when a work doc completes its purpose or drifts out of usefulness, move it to `Archived` or `Stale` with a short note instead of silently leaving it `Active`. See [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md) for the status lifecycle and the doc-review gate.

New work docs must be created from the shared templates at `docs/work/TEMPLATES/`:

- [work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md) for implementation plans;
- [work/TEMPLATES/DESIGN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/DESIGN_TEMPLATE.md) for designs.

Both templates carry the mandatory **Reference Check** (Phase 0 gate) section required by [architecture/ARCHITECTURE_PLAN.md §11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md). A plan or design without this section is not allowed to govern implementation.

### Active work docs

#### [work/implementation-plans/2026-05-16-telegram-userbot-fix-and-next.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-16-telegram-userbot-fix-and-next.md)

**Active.** Postmortem of telegram userbot debugging + plan for media support, group chats, initiative, persistent conversation history. Stable commit reference. See KNOWN_ISSUES.md for the live state.

### Archived work docs

All Phase 1-7 implementation plans and the original telegram-bridge design are kept under `docs/work/implementation-plans/archive/`. They are historical reference only — the live truth is in code + KNOWN_ISSUES.md + ROADMAP.md.

Archive contains:

- `2026-04-29-first-runtime-implementation-plan.md` (Stale — never realized as proposed)
- `2026-04-30-telegram-bridge-extraction-design.md` (Archived — bridge later removed entirely)
- `2026-05-01-telegram-bridge-extraction-implementation-plan.md` (Archived — bridge removed)
- `2026-05-13-substrate-bootstrap-implementation-plan.md` (Phase 1 closed)
- `2026-05-14-provider-principal-core-implementation-plan.md` (Phase 2 closed)
- `2026-05-15-subject-core-internal-loop-implementation-plan.md` (Phase 3 closed)
- `2026-05-15-self-modification-framework-implementation-plan.md` (Phase 4 closed)
- `2026-05-15-skills-substrate-implementation-plan.md` (Phase 5 closed)
- `2026-05-16-planner-migration-implementation-plan.md` (Phase 7 closed)

## Files That Were Deliberately Removed

The following directories and packages were intentionally removed:

- local `INDEX.md` files that did nothing except restate directory contents;
- the older `core/GLOBAL_CHECKLIST.md`, superseded by [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md);
- `packages/tg-bridge/` — обёртка над OpenClaw, заменена прямой интеграцией tg-userbot в `src/sonya/main.py` (commit 5916e3d);
- `src/sonya_runtime/` — legacy task runtime, не использовался актуальным ядром (commit 5916e3d);
- `scripts/run-openclaw-bridge.ps1`, `scripts/run-openclaw-worker.ps1`, `scripts/launch-openclaw-bridge.vbs` — runner-скрипты OpenClaw (commit 5916e3d).

## Operations Layer

### [operations/VPS.md](C:/Users/Jester/Desktop/Sonya/docs/operations/VPS.md)

Где хостится Соня и как её обслуживать. IP, ssh, layout на сервере, systemd-юниты, deploy команды, backup. Practical operations cookbook.

### [deploy/README.md](C:/Users/Jester/Desktop/Sonya/deploy/README.md)

Deployment artifacts: systemd units (`sonya.service`, `sonya-admin.service`), `update.sh` для безопасного pull + restart. Конкретные пути и команды.

## Personality Layer

### [personality/SOUL.md](C:/Users/Jester/Desktop/Sonya/docs/personality/SOUL.md)

Who Sonya is: name, gender, communication style, relationship format, what she does and doesn't say. This is the source-of-truth for system prompt during interim period (CRUTCH-001). Will become State Tuning dataset for RWKV.

### [personality/SELF.md](C:/Users/Jester/Desktop/Sonya/docs/personality/SELF.md)

Sonya's self-model: philosophical reflections, identity evolution, meta-stability, ammodal perception notes. Written by Sonya herself across sessions.

### [personality/USER.md](C:/Users/Jester/Desktop/Sonya/docs/personality/USER.md)

Who Ivan (Jester) is: psychotype, values, what he hates, relationship dynamics, communication preferences.

### [personality/LESSONS.md](C:/Users/Jester/Desktop/Sonya/docs/personality/LESSONS.md)

Learned patterns and behavioral rules accumulated through interaction.

### [personality/HEARTBEAT.md](C:/Users/Jester/Desktop/Sonya/docs/personality/HEARTBEAT.md)

Autonomy traces and maintenance task patterns.

## Legacy Planning Artifacts (docs/план/)

The `docs/план/` folder contains the original pre-project planning documents written before the governing documentation system existed:

- `ОСНОВА.md` — full AGI vision document (RWKV-7, State Tuning, SNN, embodiment, self-modification);
- `модель.txt` — sensorimotor RWKV architecture notes;
- `тело.txt` — body/emotion implementation notes;
- `эмоции.txt` — emotion and self-evolution steps.

These are **not governing documents**. They use their own internal numbering (not aligned with ROADMAP phases). Their content has been incorporated into the proper governing docs:
- RWKV/State Tuning details → [research/STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md) §12 and [research/BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md) §4-5;
- Simulation/embodiment/SNN → [research/SIMULATION_AND_EMBODIMENT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/SIMULATION_AND_EMBODIMENT_PLAN.md) §10-11;
- Memory/forgetting curve → [cognition/MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md) §12;
- Uncensored stance → [core/UNCENSORED_ENVIRONMENT_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md).

They are kept as historical reference of the original vision.

## Documentation Judgment Rules

When deciding whether a document is worth keeping, ask:

1. Does it define project truth?
2. Does it define a subsystem?
3. Does it record a reference decision?
4. Does it actively drive implementation?

If the answer is "no" to all four, the file is dead weight.

## Practical Use

Use this file together with:

- [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md) for reality tracking;
- [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md) for document governance.

This file should stay brutally explicit. If navigating the documentation becomes annoying again, this file was not maintained hard enough.
