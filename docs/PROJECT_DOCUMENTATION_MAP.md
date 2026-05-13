# PROJECT DOCUMENTATION MAP

**Status:** Active
**Type:** Core
**Scope:** Root navigation and role map for every living documentation file in the Sonya project
**Depends on:** [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md), [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
**Used by:** all readers, all planning, all implementation, all documentation maintenance
**Last reviewed:** 2026-05-13

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
3. [agents/AGENT_TASK_RUNTIME_CONTRACT.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_TASK_RUNTIME_CONTRACT.md)
4. [agents/AGENT_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_FAILURE_MODES.md)
5. [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
6. [core/SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
7. [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md)
8. [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md)
9. [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)
10. [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md)
11. [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
12. [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md)
13. [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)
14. [mvp/MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)
15. [cognition/MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)
16. [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
17. [cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
18. [skills/SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md)
19. [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
20. [research/STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)
21. [research/BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md)
22. [research/SIMULATION_AND_EMBODIMENT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/SIMULATION_AND_EMBODIMENT_PLAN.md)
23. active work docs under `docs/work/`

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

### [agents/AGENT_TASK_RUNTIME_CONTRACT.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_TASK_RUNTIME_CONTRACT.md)

This file is the operational contract for any agent that emits runtime actions or creates tasks.

Use it to answer:

- which action types are allowed and what fields each one requires;
- what shape a valid `task_payload` must have;
- which task kinds the v1 executor actually supports;
- how to pick between `reply`, image actions, task actions, `ask_clarification`, and `report_limitation`;
- how not to invent fake `task_id` values or narrate non-existent task progress.

The governing architectural plan is [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md). This file is the agent-facing contract derived from it.

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

### [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)

This file defines the reusable action and task runtime.

Use it to answer:

- how runtime actions are represented outside any one channel;
- how deferred work becomes a persisted task instead of fake narrative;
- where the planner boundary ends and the executor boundary starts;
- how the first reusable worker layer fits under future `sonya-core`.

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

### [work/designs/2026-04-30-telegram-bridge-extraction-design.md](C:/Users/Jester/Desktop/Sonya/docs/work/designs/2026-04-30-telegram-bridge-extraction-design.md)

**Archived (2026-05-13).** Historical record of the extraction strategy for the Telegram bridge. Kept because it records:

- why the extraction was wrapper-first;
- what needed to stay behavior-preserving;
- what lived in `.openclaw` versus the Sonya repo.

The current shape of the bridge is governed by [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md) and [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md), not by this document.

### [work/implementation-plans/2026-04-29-first-runtime-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-04-29-first-runtime-implementation-plan.md)

**Stale (2026-05-13).** Earliest first-runtime slice plan. Kept as historical planning context only. Its proposed `src/sonya/` file layout does not match reality, because the real path taken was narrower (extract bridge, then build `src/sonya_runtime`). A replacement implementation plan is scheduled at `docs/work/implementation-plans/2026-05-13-base-runtime-implementation-plan.md`; this document must not be used to drive new code.

### [work/implementation-plans/2026-05-01-telegram-bridge-extraction-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-01-telegram-bridge-extraction-implementation-plan.md)

**Archived (2026-05-13).** Step-by-step implementation plan for the extracted Telegram bridge. Every task was executed. Kept because it records:

- what was built;
- what parity constraints existed;
- how the current `tg-bridge` package took shape.

For the live bridge shape, read the architecture plans listed above. This document is historical reference only.

## Files That Were Deliberately Removed

The following document classes were intentionally collapsed because they had become redundant after adding this root map and root checklist:

- local `INDEX.md` files that did nothing except restate directory contents;
- the older `core/GLOBAL_CHECKLIST.md`, which is now superseded by the root-level [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md).

If someone wants to re-add local indexes later, they need a stronger justification than "the folder has files in it."

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
