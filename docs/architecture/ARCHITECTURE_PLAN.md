# ARCHITECTURE PLAN

**Status:** Active (with caveats)
**Type:** System Plan
**Scope:** Runtime-wide architecture, subsystem boundaries, and structural rules
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
**Used by:** [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md), [VPS_MIGRATION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/VPS_MIGRATION_PLAN.md), cognition plans, skill plans, work implementation plans
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):** Layered architecture below is mostly correct as direction. But many subsystem boxes (`selfmod/`, `skills/`, `initiative/`, `anchor/`, `embodiment/`, `simulation/`) exist as code yet are NOT instantiated in `src/sonya/main.py`. Channel layer doesn't exist as abstraction at all (Telegram is hardcoded in main.py). For honest implementation status see `docs/agents/EXTERNAL_MODEL_ONBOARDING.md §6-§7`. References below to `TASK_AND_ACTION_RUNTIME_PLAN.md` are stale — that plan was archived; task runtime never landed.

## 1. Purpose

This document translates the project core from [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) into architectural form.

Its job is to:

- define the main subsystems of the Sonya environment;
- fix their boundaries and interactions;
- preserve the `full-scope MVP shell`;
- prevent the project from degrading into either a prompt wrapper or a dead enterprise backend.

## 2. Architectural Principle

The architecture must be built around Sonya as a continuous system.

That means:

- one living environment instead of isolated one-shot calls;
- stateful runtime;
- memory-backed behavior;
- explicit identity structures;
- traceable loops;
- guarded self-modification;
- provider independence;
- VPS-first deployability.

The architecture must not depend on one UI, one provider, or one local machine process.

## 3. Reference-Derived Rules

This architecture is constrained by the reference analysis documents:

- [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
- [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)
- [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md)
- [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)

Practical consequences:

- Sonya core does not clone OpenClaw. It extracts operational truth from OpenClaw and rebuilds it in a cleaner VPS-first runtime.
- Hermes is treated as an architectural function, not as a missing external dependency that blocks MVP.
- OmniAgent is treated as a vocabulary donor and warning source, not as a trusted runtime foundation.
- Any implementation plan that contradicts these rules is architecturally wrong and must be corrected before code execution starts.

## 4. Main Architectural Layers

### 4.1 Subject Core and Continuity Layer

Contains:

- subject core;
- continuity stream;
- canonical subject state;
- canonical response object;
- pending intention state;
- cross-channel continuity snapshots.

Responsibility:
keep Sonya one continuous subject above all channels, renderers, and model substrates.

This layer exists to stop Telegram, Discord, TTS, avatar, or future embodiment surfaces from becoming separate practical instances.

See:

- [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)

### 4.2 Core Runtime Layer

Contains:

- main environment process;
- event bus;
- task loop;
- scheduler;
- runtime state;
- lifecycle management.

Responsibility:
keep Sonya alive as a continuous system.

### 4.3 Cognition Layer

Contains:

- subject-state interpretation hooks;
- identity layer;
- episodic memory;
- semantic memory;
- context evolution;
- initiative signals;
- reflexion paths;
- self-observation hooks.

Responsibility:
preserve continuity, self-structure, and internal growth.

### 4.4 Skills and Behavior Layer

Contains:

- skill registry;
- skill activation;
- skill injection;
- real-time skill evolution;
- behavior artifacts;
- skill testing hooks.

Responsibility:
give Sonya expandable capabilities without collapsing everything into prompts.

### 4.5 Tool and Action Layer

Contains:

- tool registry;
- action protocol;
- task protocol;
- task store;
- task worker;
- execution sandbox;
- tool result capture;
- action trace logging.

Responsibility:
perform real action in filesystem, network, and process environments.

This layer now explicitly includes the reusable task and action runtime defined in:

- [TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)

### 4.6 Harness Layer

Contains the three harness slices (technical, epistemic, anchor) plus the approval controls, immutable zones, and drift controls that wrap them. The canonical definition of each slice and its contents lives in [cognition/ANCHORS_AND_FAILURE_MODES.md §7](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md).

Responsibility:
prevent the system from damaging itself, weakening its own criteria, or eroding identity-critical anchors.

### 4.7 Model and Provider Layer

Contains:

- provider abstraction;
- OpenRouter adapter;
- generic OpenAI-compatible adapter;
- brain backend interface;
- future self-hosted backend slots.

Responsibility:
keep the system independent from the current provider and preserve the path toward its own brain stack.

### 4.8 Channel Layer

Contains:

- Telegram/Userbot;
- admin CLI;
- diagnostics/admin web channel;
- inbound/outbound routing.

Responsibility:
provide real bidirectional contact between Sonya and the outside world.

Channel layer is downstream from subject core. Channels are render and ingress surfaces, not separate minds.

### 4.9 Embodiment and Simulation Layer

Contains:

- embodiment adapter;
- virtual body counters;
- spike/event contracts;
- simulation/world interface;
- future body integrations.

Responsibility:
create a path to grounding without corrupting the core runtime.

### 4.10 Subject Substrate Layer (formerly Persistence and Storage)

Contains:

- subject substrate artifacts (см. [SUBSTRATE_STANCE.md §3](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md));
- runtime databases that hold those artifacts;
- event storage attached to `ContinuityStream`;
- semantic storage;
- trace logs;
- config artifacts (versioned, secrets separated);
- skill artifacts;
- archives and rollback points;
- migration registry для substrate schema versioning.

Responsibility:
make Sonya persistent and restart-safe. Это **не просто "storage"** — это **substrate Сони** в смысле [SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md). Любой reader-процесс читает этот слой и продолжает Соню. Слой имеет immutable zones (см. [SUBSTRATE_STANCE.md §8](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md)) и validation pipeline для self-modifying изменений (см. [SUBSTRATE_STANCE.md §9](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md)).

## 5. High-Level Data Flow

1. An event arrives from a channel, environment, scheduler, or internal signal.
2. Runtime normalizes the event and publishes it into the event bus.
3. Subject core resolves current continuity state, active relation context, and pending intentions.
4. Cognition assembles context from identity, memory, summaries, anchors, and current subject state.
5. The agent loop selects a path:
   - fast;
   - slow;
   - tool-driven;
   - initiative-driven.
6. Planner produces a canonical response or action result before channel-specific rendering.
7. Skills and tool runtime execute the required actions.
8. Harness checks changes, calls, risks, and anchor integrity.
9. Traceability records the decision path.
10. Memory stack updates from events and derived conclusions.
11. Channel layer or action layer emits the rendered result outward.

## 6. Minimal Form of the First Release

The first release must include every load-bearing layer, even if their maturity differs:

- subject core and continuity stream: partial but explicit;
- runtime: production;
- provider layer: production;
- memory: episodic production, semantic partial;
- identity: partial but explicit;
- skills: production shell;
- skill evolution: manual-gated;
- harness: production baseline;
- self-modification: manual-gated baseline;
- simulation/embodiment: explicit stubs;
- brain evolution: research-shell.

## 7. What the First Release Is Allowed to Borrow

The first release may borrow:

- anchor-doc and lived-environment lessons from OpenClaw;
- shell/brain separation and adapter-first orchestration from Hermes;
- terminology and selected module ideas from OmniAgent.

The first release may not borrow:

- OpenClaw local-machine coupling as a deployment assumption;
- Hermes as a blocker dependency before runtime exists;
- OmniAgent gateway, auth model, README claims, or raw codebase as trusted base.

## 8. What Must Not Be Allowed Architecturally

- channel logic, memory, tools, and identity must not be fused into one blob without boundaries;
- provider-specific code must not leak into cognition;
- skill system must not collapse into prompt snippets without lifecycle;
- harness must not be reduced to only a filesystem sandbox;
- self-modification must not bypass traceability or approvals;
- VPS deployability must not be postponed as an afterthought.

## 9. Recommended Modular Decomposition

Logical first-order modules:

- `runtime`
- `channels`
- `providers`
- `identity`
- `memory`
- `context`
- `skills`
- `tools`
- `tasks`
- `harness`
- `reflexion`
- `initiative`
- `embodiment`
- `simulation`
- `trace`
- `storage`
- `selfmod`

This is not yet the final file tree. It is the architectural decomposition.

## 10. Phase 0: Reference Analysis

Before implementation enters core runtime work, the project must complete an explicit analysis phase.

This is not optional paperwork. It is the filter that stops the project from importing the wrong assumptions.

Phase 0 includes:

- audit of the live OpenClaw host and its operational truth;
- analysis of Hermes as orchestration role rather than dependency;
- audit of OmniAgent as concept source and anti-pattern source;
- extraction of what is borrowed, what is rejected, and what must be rebuilt cleanly.

Phase 0 is represented by:

- [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
- [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)
- [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md)
- [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)

The project is not allowed to move from emergency implementation into real `sonya-core` construction while pretending this phase never happened.

## 11. Required Checks for All Subplans

Every implementation-facing subplan must answer three reference checks:

1. Which operational truth from OpenClaw does it preserve?
2. Which orchestration boundary from Hermes does it respect?
3. Which tempting OmniAgent shortcut does it explicitly reject?

These three checks live in a single mandatory **Reference Check** section inside every design or implementation plan under `docs/work/`. Templates that pre-populate the section are provided at:

- [work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md)
- [work/TEMPLATES/DESIGN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/DESIGN_TEMPLATE.md)

A subplan that omits this section, leaves it empty, or answers with "N/A" without explanation is not allowed to govern implementation. Each answer must point at a concrete file, section, or behavior — not a topic.

Relevant linked plans:

- [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)
- [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
- [VPS_MIGRATION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/VPS_MIGRATION_PLAN.md)
- [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)
- [SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md)
- [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
- [STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)

## 12. Conclusion

Sonya architecture must be built as an environment for a continuous subject with growth, not as a wrapper around a model.

If a later decision destroys:

- continuity;
- explicit identity;
- traceability;
- guarded growth;
- provider independence;
- VPS-first runtime;

then that decision is architecturally invalid.
