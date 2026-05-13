# DOCUMENTATION SYSTEM

**Status:** Active
**Type:** Core
**Scope:** Rules, taxonomy, lifecycle, and link discipline for all project documentation
**Depends on:** [../PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md)
**Used by:** all documentation maintenance and future project work
**Last reviewed:** 2026-05-13

## Purpose

This file defines how the Sonya documentation system works.

The documentation exists to prevent three failure modes:

- losing the project idea while implementing details;
- drowning in disconnected plans and stale notes;
- drifting into local optimizations that break the core direction.

## Top-Level Rule

Documentation must act as a system.

That means:

- every living document must have a role;
- every role must have a place in the tree;
- every important document must be linked from the master index;
- dead documents must be removed or merged;
- active implementation docs must not pollute long-lived project truth.

## Document Types

### Core

Defines project identity and rules of interpretation.

### System Plan

Defines a long-lived subsystem or cross-cutting project concern.

### Reference Analysis

Explains how an external or predecessor system should and should not influence Sonya.

### Work Doc

Active design, implementation, migration, or execution planning tied to current work.

These live under [../work/](C:/Users/Jester/Desktop/Sonya/docs/work), inside `docs/`, but remain explicitly non-governing.

## Folder Rules

### docs/

Contains long-lived documentation only.

Valid subtrees:

- docs/core/
- docs/agents/
- docs/architecture/
- docs/cognition/
- docs/skills/
- docs/research/
- docs/mvp/
- docs/governance/

### docs/work/

Contains active execution material only.

Valid subtrees:

- docs/work/designs/
- docs/work/implementation-plans/
- docs/work/notes/

## Required Metadata Header

Every long-lived document must begin with the following header. `Status` is mandatory and its value must be one of the four defined below. `Last reviewed` must be set to a real date whenever the document is touched in a governance-relevant way.

```md
**Status:** Active | Draft | Stale | Archived
**Type:** Core | System Plan | Reference Analysis | Work Doc
**Scope:** What this document governs
**Depends on:** [doc links]
**Used by:** [doc links]
**Last reviewed:** YYYY-MM-DD
```

### Status Values

- **Active** — current source of truth for its scope. Governs present and planned work. Must be consistent with the real state of the code.
- **Draft** — work in progress toward becoming Active. Intentionally incomplete. Must not be cited as governing truth. Must declare what it needs to become Active.
- **Stale** — was Active, but reality drifted away from it and nobody has yet realigned it. Must carry a brief "why stale" note at the top of section 1. Not allowed to govern new work.
- **Archived** — finished, superseded, or intentionally frozen. Kept for history. Must include a short "why archived" pointer to the replacement or result. Must not be edited further except to fix its archival note.

### Status Transitions

- Active → Stale: when the code no longer matches the document, or when a more current document takes over the same scope, and re-alignment is not yet done. Transition requires adding a "why stale" note.
- Active → Archived: when the scope is complete, abandoned, or superseded. Transition requires adding a "why archived" pointer.
- Draft → Active: when the document is complete enough to govern. Transition requires removing the Draft note and setting `Last reviewed`.
- Stale → Active: when the document is re-aligned with reality. Transition requires updating affected sections and setting `Last reviewed`.
- Any → Archived: always allowed. Archived is terminal.

Transitions must be recorded either in the commit message that performs the transition or in [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md) if the transition affects a governance checklist item.

### Last Reviewed

`Last reviewed` is not a free-text field. It must be updated in these situations:

- the document is edited in a way that changes its governing meaning;
- the status changes;
- the document passes a drift review and is confirmed accurate without changes (note the review date even when nothing else changes).

Minor typo fixes, link path updates, and formatting-only edits do not require touching `Last reviewed`.

## Linking Rules

- Use absolute project-local links for every important cross-reference.
- Prefer links in metadata headers, section introductions, and indexes.
- If a document depends on another one conceptually, say so explicitly.
- If a document repeats an idea only because another file already defines it, replace repetition with a link unless local restatement is necessary.

## Duplication Rules

Duplication is allowed only when it serves one of these purposes:

- local restatement needed for a subsystem to remain readable on its own;
- short summary in an index;
- deliberate summary layer above a more detailed reference.

Duplication is not allowed when it creates competing definitions.

## Document Lifecycle

A document is allowed to live only if it does one of these jobs:

- defines project identity;
- defines a subsystem;
- defines a reference decision;
- drives active implementation work.

If it does none of these, it is dead.

Dead docs must be deleted, merged, or moved into work/notes/ if temporarily useful.

### Doc-Review Gate for Code Changes

Every code change that touches runtime contracts, runtime surfaces, or the documented shape of a subsystem must include a **doc-review gate** before it is considered complete. Runtime-relevant changes include but are not limited to:

- adding, removing, or renaming an action type, task kind, event, continuity concept, subject-state field, or canonical response kind;
- changing a storage path, schema, or database used by the runtime;
- changing a channel contract or a channel adapter surface;
- changing a provider contract or adding a provider;
- changing harness, authority, or approval semantics;
- changing the boundary between `tg-bridge` and `sonya_runtime`, or later between `sonya_runtime` and `sonya-core`.

For each such change, the contributor must, in the same PR or commit series:

1. identify which governing documents (under `docs/core/`, `docs/architecture/`, `docs/cognition/`, `docs/skills/`, `docs/mvp/`, `docs/research/`, `docs/agents/`) describe the affected contract;
2. update those documents so they match the new reality, or explicitly record that a follow-up doc task is required;
3. update [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md) if a file moved or changed role;
4. update [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md) if the change flips a ⬜/🟡/✅ item;
5. update `Last reviewed` in every document whose governing meaning changed.

If one of these steps is intentionally deferred, the PR/commit message must say so explicitly and name the follow-up task. Silent divergence between code and governing docs is treated as a drift event.

### Drift Review Cadence

Independent of PR-level gates, the project runs a **drift review** on a regular cadence to re-check alignment between code and docs at the subsystem level.

- Cadence: at least once every two weeks during active development, and before any release or deployment milestone.
- Location of evidence: each drift review appends a short entry to [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md).
- Output of each review: a list of confirmed-accurate governing docs, a list of docs moved to `Stale`, and a list of docs moved to `Archived`.
- Scope of each review: the reviewer is explicitly expected to spot-check real code paths against the claims in the documents that cover them.

Missing drift review windows is itself a drift event and must be recorded.

## Review Rules

When documentation changes:

1. update moved links;
2. update metadata headers when dependencies or scope change;
3. check [../PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md);
4. check root `docs/work/` entries if execution docs moved;
5. remove stale paths immediately.

## Operational Rule

When starting new implementation:

1. read the relevant long-lived docs from docs/;
2. create or update a work doc in `docs/work/`;
3. do not create new execution plans outside the `docs/work/` work layer;
4. do not allow work docs to silently become project truth without intentional promotion.

## Checklist Rule

The project must maintain one global long-lived checklist:

- [../GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)

This file is not a sprint TODO.

It is the top-level reality check that tracks whether the project still has the required core, architecture, cognition, channel, safety, and research contours.
