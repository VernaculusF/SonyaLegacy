# Documentation Index

**Status:** Active
**Type:** Documentation map
**Last updated:** 2026-06-10

This file is the entry point for project documentation. When documents disagree,
prefer the sources listed earlier within the same category.

## Current Source Of Truth

1. [ATRIUM_PROJECT_PLAN.md](ATRIUM_PROJECT_PLAN.md) - active Atrium delivery plan
2. [STATE.md](STATE.md) - verified current state and known gaps
3. [HANDOFF.md](HANDOFF.md) - current continuation point and verification notes
4. [MASTER.md](MASTER.md) - high-level doctrine and long-term direction
5. [FINAL_STATE_TODO.md](FINAL_STATE_TODO.md) - broader target-state backlog

## Governing Invariants

- [core/ENVIRONMENT_AS_SONYA.md](core/ENVIRONMENT_AS_SONYA.md)
- [core/SUBSTRATE_STANCE.md](core/SUBSTRATE_STANCE.md)
- [core/UNCENSORED_ENVIRONMENT_STANCE.md](core/UNCENSORED_ENVIRONMENT_STANCE.md)
- [core/SELF_REWRITE_STANCE.md](core/SELF_REWRITE_STANCE.md)
- [personality/SOUL.md](personality/SOUL.md)
- [cognition/COGNITION.md](cognition/COGNITION.md)

These documents define identity and architectural intent. Their factual runtime
claims may age; use `STATE.md` for current implementation reality.

## Active Product And Operations References

- [atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md](atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md)
  - target product/architecture spec; partially implemented
- [operations/VPS.md](operations/VPS.md)
  - deployment and recovery reference
- [operations/SUBAGENT_MODELS.md](operations/SUBAGENT_MODELS.md)
  - subagent model-selection policy
- [operations/PROVIDER_SYSTEM_DESIGN.md](operations/PROVIDER_SYSTEM_DESIGN.md)
  - target provider/account/model-offering runtime
- [operations/PROVIDER_MODEL_CATALOG.md](operations/PROVIDER_MODEL_CATALOG.md)
  - provider inventory and bootstrap candidates; no secrets
- [operations/PROVIDER_RUNTIME_STATUS.md](operations/PROVIDER_RUNTIME_STATUS.md)
  - current provider-runtime implementation status and verification
- [operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md](operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md)
  - active delivery order for provider import, subagents, and memory migration
- [operations/MEMORY_KNOWLEDGE_MIGRATION_STATUS.md](operations/MEMORY_KNOWLEDGE_MIGRATION_STATUS.md)
  - production memory/knowledge inventory and safe migration order
- [operations/FREEMODEL_BRIDGE.md](operations/FREEMODEL_BRIDGE.md)
  - proposed freemodel bridge; not implemented
- [skills/SKILL_SYSTEM_PLAN.md](skills/SKILL_SYSTEM_PLAN.md)

## Historical And Research References

- [atrium/PLAN.md](atrium/PLAN.md) - historical Atrium implementation roadmap
- [atrium/EVENT_SCHEMA.md](atrium/EVENT_SCHEMA.md) - historical schema-v20 design
- [atrium/AVATAR_PROMPTS.md](atrium/AVATAR_PROMPTS.md) - visual reference
- `docs/план/*` - legacy early plans
- `docs/superpowers/*` - implementation slice designs and execution plans

Historical documents are retained for context. They are not current-state
authority and may reference files that no longer exist.

## Documentation Maintenance Rules

- Update `STATE.md` when implementation reality changes.
- Update `HANDOFF.md` at every meaningful stopping point.
- Update `ATRIUM_PROJECT_PLAN.md` as slices are completed or reprioritized.
- Do not turn `STATE.md`, `HANDOFF.md`, or `MASTER.md` into full changelogs.
- Keep old plans, but mark them Historical/Legacy instead of presenting them as
  active truth.
- Record broad documentation findings in
  [DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md).
