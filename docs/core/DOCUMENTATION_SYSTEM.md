# DOCUMENTATION SYSTEM

**Status:** Active
**Type:** Core
**Scope:** Rules, taxonomy, lifecycle, and link discipline for all project documentation
**Depends on:** [../PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md)
**Used by:** all documentation maintenance and future project work
**Last reviewed:** 2026-05-01

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

### docs/work/

Contains active execution material only.

Valid subtrees:

- docs/work/designs/
- docs/work/implementation-plans/
- docs/work/notes/

## Required Metadata Header

Every long-lived document should begin with:

```md
**Status:** Active | Archived | Draft
**Type:** Core | System Plan | Reference Analysis | Work Doc
**Scope:** What this document governs
**Depends on:** [doc links]
**Used by:** [doc links]
**Last reviewed:** YYYY-MM-DD
```

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
