# <Feature Name> Implementation Plan

**Status:** Draft
**Type:** Work Doc
**Scope:** <One-sentence description of what this plan actually builds>
**Depends on:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md), <plus the actual governing docs for this scope>
**Used by:** <which implementation sessions will consume this plan>
**Last reviewed:** YYYY-MM-DD

> **Template note:** Fill in every section. Do not delete section headers. Do not delete the Reference Check section under any circumstance — it is mandatory per [ARCHITECTURE_PLAN.md §11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md). A plan without a Reference Check is not allowed to govern implementation.

## 1. Goal

<Short, honest statement of what this plan is supposed to achieve. Not "build system X". More like "give Sonya a persistent `principal_id` layer so relation-anchor bindings can survive a process restart and cross-channel input".>

## 2. Architecture Summary

<Two to five sentences. Which subsystems are touched, how they relate, where the new/changed boundary sits. If this plan shifts a boundary between `packages/tg-bridge`, `src/sonya_runtime`, and `src/sonya_shared` (or a future `sonya-core`), say so here.>

## 3. Reference Check (Phase 0 Gate)

This section is mandatory. It is the Phase 0 gate defined in [ARCHITECTURE_PLAN.md §10–11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md) and enforced by [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md) and [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md).

Each answer must point to a concrete file, section, or behavior. "We agree with it" is not an answer.

### 3.1 OpenClaw — Operational Truth Preserved

**Which operational behavior from the live OpenClaw host does this plan preserve?**

Anchor paths: `C:\Users\Jester\.openclaw\*`, `C:\Users\Jester\.openclaw\workspace\*`, `telegram-bridge.mjs`, `memory_system/`, `openclaw.json`.

Governing reference: [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md) (especially Appendix: Code-Level Audit).

Required form of the answer:

- <file or artifact in the live host>
- <what behavior/guarantee it provides today>
- <how this plan keeps that behavior working (or explicitly replaces it, with no silent regression)>

If this plan does **not** touch OpenClaw at all, still say so and explain why — not "N/A".

### 3.2 Hermes — Orchestration Boundary Respected

**Which orchestration boundary from the Hermes role does this plan keep intact?**

Governing reference: [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md).

Because Hermes is currently code-level absent (see its audit appendix), treat the Hermes role as a set of responsibilities that must live inside `sonya_runtime/*` (channels, routing, scheduler, delivery, hooks). The question becomes:

- which part of the shell/brain split this plan respects;
- which responsibility this plan puts on the "shell" side vs. on the "brain"/subject-core side;
- which adapter boundary is preserved so the channel does not grow a second Sonya mind.

Required form of the answer:

- <the boundary in one sentence>
- <the module(s) that own each side of it after this plan>
- <the anti-pattern this prevents>

### 3.3 OmniAgent — Shortcut Explicitly Rejected

**Which tempting OmniAgent design choice does this plan explicitly refuse?**

Governing reference: [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md) (especially §§ 8.3–8.10 of the Code-Level Audit Appendix).

Required form of the answer:

- <name the specific OmniAgent pattern you were tempted by>
- <where it lives in the OmniAgent tree (file or module)>
- <why we refuse it here>
- <what we do instead>

Note: OmniAgent is GPL-3.0. No code copy. Only schema/interface inspiration with attribution.

### 3.4 Reference Pass Checklist

- [ ] 3.1 references a concrete OpenClaw artifact by path, not by topic
- [ ] 3.2 names the specific boundary and the modules on each side
- [ ] 3.3 names the specific OmniAgent pattern being refused and where it lives
- [ ] No copy-paste of governing theory from `docs/core/`, `docs/architecture/`, `docs/cognition/` — only links
- [ ] No action-type, task-kind, or harness-layer lists restated (link to the source of truth)

## 4. Tech Stack

<Languages, libraries, major dependencies. Must match repo conventions unless explicitly justified.>

## 5. File Structure

### Create

- <absolute paths of new files>

### Modify

- <absolute paths of existing files with one-line why>

### Responsibility Map

- <module>: <what it owns>

## 6. Task List

Each task follows the same mini-shape. Steps use `- [ ]` for trackable state.

### Task <n>: <Short task title>

**Files:**
- Create: <paths>
- Modify: <paths>

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Write minimal implementation**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

<Repeat per task.>

## 7. Verification

- <build command>
- <test command>
- <any smoke / health check>

## 8. Self-Review

### Spec coverage

- <section>: <task reference>

### Placeholder scan

- no `TODO`
- no `TBD`
- no "add error handling later"

### Type consistency

- <any cross-module naming you want to double-check>

### Doc-review gate

- [ ] Governing documents that describe the affected contract were updated, or a follow-up was explicitly recorded in the commit message
- [ ] [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md) updated if files moved or changed role
- [ ] [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md) updated if a ⬜/🟡/✅ flipped
- [ ] `Last reviewed` updated on every touched governing doc
- [ ] Subsystem-scale change, if any, recorded as a short entry in [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md)

## 9. Promotion Note

When the plan is ready to be executed, flip `Status` from `Draft` to `Active`. When all tasks are done, flip `Status` to `Archived` and add a short "why archived" pointer to the real code + any follow-up plan.
