# ARCHITECTURE PLAN

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

- [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/REFERENCE_SYSTEMS_ANALYSIS.md)
- [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/OPENCLAW_ANALYSIS.md)
- [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/HERMES_ANALYSIS.md)
- [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/OMNIAGENT_ANALYSIS.md)

Practical consequences:

- Sonya core does not clone OpenClaw. It extracts operational truth from OpenClaw and rebuilds it in a cleaner VPS-first runtime.
- Hermes is treated as an architectural function, not as a missing external dependency that blocks MVP.
- OmniAgent is treated as a vocabulary donor and warning source, not as a trusted runtime foundation.
- Any implementation plan that contradicts these rules is architecturally wrong and must be corrected before code execution starts.

## 4. Main Architectural Layers

### 4.1 Core Runtime Layer

Contains:

- main environment process;
- event bus;
- task loop;
- scheduler;
- runtime state;
- lifecycle management.

Responsibility:
keep Sonya alive as a continuous system.

### 4.2 Cognition Layer

Contains:

- identity layer;
- episodic memory;
- semantic memory;
- context evolution;
- initiative signals;
- reflexion paths;
- self-observation hooks.

Responsibility:
preserve continuity, self-structure, and internal growth.

### 4.3 Skills and Behavior Layer

Contains:

- skill registry;
- skill activation;
- skill injection;
- real-time skill evolution;
- behavior artifacts;
- skill testing hooks.

Responsibility:
give Sonya expandable capabilities without collapsing everything into prompts.

### 4.4 Tool and Action Layer

Contains:

- tool registry;
- action protocol;
- execution sandbox;
- tool result capture;
- action trace logging.

Responsibility:
perform real action in filesystem, network, and process environments.

### 4.5 Harness Layer

Contains:

- technical harness;
- epistemic harness;
- anchor harness;
- approval controls;
- immutable zones;
- drift controls.

Responsibility:
prevent the system from damaging itself, weakening its own criteria, or eroding identity-critical anchors.

### 4.6 Model and Provider Layer

Contains:

- provider abstraction;
- OpenRouter adapter;
- generic OpenAI-compatible adapter;
- brain backend interface;
- future self-hosted backend slots.

Responsibility:
keep the system independent from the current provider and preserve the path toward its own brain stack.

### 4.7 Channel Layer

Contains:

- Telegram/Userbot;
- admin CLI;
- diagnostics/admin web channel;
- inbound/outbound routing.

Responsibility:
provide real bidirectional contact between Sonya and the outside world.

### 4.8 Embodiment and Simulation Layer

Contains:

- embodiment adapter;
- virtual body counters;
- spike/event contracts;
- simulation/world interface;
- future body integrations.

Responsibility:
create a path to grounding without corrupting the core runtime.

### 4.9 Persistence and Storage Layer

Contains:

- runtime databases;
- event storage;
- semantic storage;
- trace logs;
- config artifacts;
- skill artifacts;
- archives and rollback points.

Responsibility:
make Sonya persistent and restart-safe.

## 5. High-Level Data Flow

1. An event arrives from a channel, environment, scheduler, or internal signal.
2. Runtime normalizes the event and publishes it into the event bus.
3. Cognition assembles context from identity, memory, summaries, anchors, and current runtime state.
4. The agent loop selects a path:
   - fast;
   - slow;
   - tool-driven;
   - initiative-driven.
5. Skills and tool runtime execute the required actions.
6. Harness checks changes, calls, risks, and anchor integrity.
7. Traceability records the decision path.
8. Memory stack updates from events and derived conclusions.
9. Channel layer or action layer emits the result outward.

## 6. Minimal Form of the First Release

The first release must include every load-bearing layer, even if their maturity differs:

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
- `harness`
- `reflexion`
- `initiative`
- `embodiment`
- `simulation`
- `trace`
- `storage`
- `selfmod`

This is not yet the final file tree. It is the architectural decomposition.

## 10. Required Checks for All Subplans

Every implementation-facing subplan must answer three reference checks:

1. Which operational truth from OpenClaw does it preserve?
2. Which orchestration boundary from Hermes does it respect?
3. Which tempting OmniAgent shortcut does it explicitly reject?

Relevant linked plans:

- [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/plans/mvp/MVP_BOUNDARIES.md)
- [VPS_MIGRATION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/VPS_MIGRATION_PLAN.md)
- [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/plans/cognition/MEMORY_AND_IDENTITY_PLAN.md)
- [SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/plans/skills/SKILL_SYSTEM_PLAN.md)
- [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/plans/cognition/ANCHORS_AND_FAILURE_MODES.md)
- [STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/plans/research/STATE_TUNING_PLAN.md)

## 11. Conclusion

Sonya architecture must be built as an environment for a continuous subject with growth, not as a wrapper around a model.

If a later decision destroys:

- continuity;
- explicit identity;
- traceability;
- guarded growth;
- provider independence;
- VPS-first runtime;

then that decision is architecturally invalid.
