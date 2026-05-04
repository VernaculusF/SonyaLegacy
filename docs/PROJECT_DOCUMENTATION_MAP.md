# PROJECT DOCUMENTATION MAP

**Status:** Active
**Type:** Core
**Scope:** Root navigation and role map for every living documentation file in the Sonya project
**Depends on:** [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md), [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
**Used by:** all readers, all planning, all implementation, all documentation maintenance
**Last reviewed:** 2026-05-02

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
- `docs/architecture/` - runtime structure, deployment shape, channel architecture, reference analyses;
- `docs/cognition/` - memory, identity, anchors, continuity, failure modes;
- `docs/skills/` - skill system and evolution surface;
- `docs/research/` - long-horizon research tracks that must shape architecture without hijacking MVP;
- `docs/mvp/` - boundaries for the first coherent system shell;
- `docs/work/` - active designs and implementation plans that support current execution.

## Reading Order

Read in this order if you need the full project context:

1. [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
2. [core/SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
3. [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)
4. [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
5. [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md)
6. [mvp/MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)
7. [cognition/MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)
8. [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
9. [cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
10. [skills/SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md)
11. [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
12. [research/STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)
13. [research/BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md)
14. [research/SIMULATION_AND_EMBODIMENT_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/SIMULATION_AND_EMBODIMENT_PLAN.md)
15. active work docs under `docs/work/`

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

### [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)

This is the full project-wide execution checklist.

Use it to answer:

- what already exists in reality;
- what is only documented;
- what still has not been built;
- whether the implementation is drifting away from the original plan.

This is not a sprint TODO. It is the top-level reality ledger.

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

Work docs are allowed to be volatile. They are not project truth, but they still need explicit purpose.

### [work/designs/2026-04-30-telegram-bridge-extraction-design.md](C:/Users/Jester/Desktop/Sonya/docs/work/designs/2026-04-30-telegram-bridge-extraction-design.md)

This file explains the original extraction strategy for the Telegram bridge.

Keep it because it records:

- why the extraction was wrapper-first;
- what needed to stay behavior-preserving;
- what lived in `.openclaw` versus the Sonya repo.

If the bridge architecture changes radically, this file should either be revised or archived.

### [work/implementation-plans/2026-04-29-first-runtime-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-04-29-first-runtime-implementation-plan.md)

This is the earlier first-runtime slice plan.

Keep it because it records:

- what the first runtime slice was supposed to cover;
- how the initial decomposition was imagined before the Telegram emergency took over.

It is partly stale and should be treated as historical planning context, not the current execution truth.

### [work/implementation-plans/2026-05-01-telegram-bridge-extraction-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-01-telegram-bridge-extraction-implementation-plan.md)

This is the implementation plan for the extracted Telegram bridge.

Keep it because it records:

- what was built;
- what parity constraints existed;
- how the current `tg-bridge` package took shape.

This remains relevant until the bridge is either stabilized enough to be considered solved, or replaced by a more general channel runtime.

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
