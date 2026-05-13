# <Feature Name> Design

**Status:** Draft
**Type:** Work Doc
**Scope:** <One-sentence description of what this design fixes, before any implementation plan is written>
**Depends on:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md), <governing docs for this scope>
**Used by:** <planned implementation plan(s) that will consume this design>
**Last reviewed:** YYYY-MM-DD

> **Template note:** Do not delete section headers. The Reference Check section is mandatory per [ARCHITECTURE_PLAN.md §11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md). A design without a Reference Check is not allowed to feed implementation.

## 1. Problem

<What real problem this design solves. Two to five sentences. No aspirational framing.>

## 2. Non-Negotiable Constraints

- <invariants that must hold>
- <things that must not regress>
- <things that must not be silently changed>

## 3. Proposed Shape

<Module names, data flow, key interfaces. Text is fine; small diagrams if they really help. Link to governing docs for theory instead of restating.>

## 4. Reference Check (Phase 0 Gate)

Mandatory. Same contract as in the implementation-plan template and [ARCHITECTURE_PLAN.md §10–11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md).

### 4.1 OpenClaw — Operational Truth Preserved

Governing reference: [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md).

- <live host artifact>
- <behavior it currently provides>
- <how this design preserves or explicitly replaces it>

### 4.2 Hermes — Orchestration Boundary Respected

Governing reference: [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md).

- <the boundary in one sentence>
- <modules on each side>
- <anti-pattern this prevents>

### 4.3 OmniAgent — Shortcut Explicitly Rejected

Governing reference: [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md).

- <the specific OmniAgent pattern>
- <its path in the OmniAgent tree>
- <why we refuse it>
- <what we do instead>

### 4.4 Reference Pass Checklist

- [ ] 4.1 references a concrete OpenClaw artifact by path
- [ ] 4.2 names the specific boundary and the modules on each side
- [ ] 4.3 names the specific OmniAgent pattern being refused and where it lives
- [ ] No copy-paste of governing theory (only links)
- [ ] No duplicated lists from source-of-truth docs

## 5. Alternatives Considered

- <option>: <why it was rejected>

## 6. Risks

- <risk>: <mitigation>

## 7. Follow-Up

- <link to the implementation plan that will execute this design>
- <any remaining open questions that must be resolved before implementation starts>

## 8. Promotion Note

When this design is accepted, flip `Status` from `Draft` to `Active`. When the implementing plan is archived, flip `Status` to `Archived` and point to the code.
