# Documentation Audit

**Status:** Active
**Type:** Documentation maintenance record
**Last updated:** 2026-06-10

## Audit Result

The documentation contained several generations of plans presented at the same
authority level. The repository now uses [INDEX.md](INDEX.md) to distinguish
current truth, governing intent, operational references, and historical plans.
No historical document was deleted.

## Verified Implementation Reality

Verified against the deployed codebase on 2026-06-10:

- production and repository migration target are schema v33
- `projects`, `project_runs`, `execution_traces`, and `workspace_policy` exist
- project CRUD, run/trace APIs, and workspace policy APIs exist
- provider registry, accounts, account offerings, encrypted secrets,
  observations, lifecycle adapters, discovery refresh, and evidence-driven
  routing implement the provider-to-model-pool foundation
- Atrium has an upload endpoint and frontend upload path
- full-system-access has backend policy/runtime wiring and tests
- Atrium is a hosted web surface; old Tauri/Rust IPC requirements are stale

These foundations do not prove complete end-to-end product behavior. Project
statuses, observable orchestration, project-scoped file handling, model-pool
discovery/refresh, and live VPS behavior still require completion or proof.

## Classification

### Canonical Current

- `ATRIUM_PROJECT_PLAN.md`
- `STATE.md`
- `HANDOFF.md`
- `MASTER.md`
- `FINAL_STATE_TODO.md`

### Governing

- `core/*`
- `cognition/COGNITION.md`
- `personality/*`

### Active Reference

- `atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `operations/*`
- `skills/SKILL_SYSTEM_PLAN.md`

### Historical / Legacy

- `atrium/PLAN.md`
- `atrium/EVENT_SCHEMA.md`
- `план/*`
- completed slice plans under `superpowers/*`

## Known Documentation Debt

- Several historical files reference removed documents such as `CHANNELS.md`,
  `UX_SKETCH.md`, `ETAP2_RESEARCH.md`, and `EXPRESSION_AS_STATE.md`.
- Some governing/personality documents contain target-state language mixed with
  implementation claims. They should be corrected only when a claim materially
  misleads current development.
- Older active documents still contain completed session logs and stale
  unchecked items. Current execution order is maintained in
  `operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md`; historical slice plans are
  retained only as evidence.
- The complete Markdown link audit still needs a small repository script or CI
  check that distinguishes real links from inline-code examples.
