# Restructuring Status

**Status:** Active
**Type:** Live restructuring tracker
**Last updated:** 2026-06-15
**Scope:** Repo split, legacy archive, fresh `SonyaCore`, runtime-state preservation, deploy rework

This file is the live handoff for the current restructuring effort. Update it
after every meaningful change so another agent can continue without guessing.

## Current State

- The current repository is still the old monorepo at
  `C:\Users\Jester\Desktop\Sonya`.
- The old repo must be preserved as `SonyaLegacy` with full `.git` and 582
  commits.
- The future active runtime will be split into fresh repos:
  `SonyaCore`, `SonyaTools`, `SonyaSkills`, `SonyaAdmin`, `Atrium`,
  `SonyaTgUserBot`.
- The live VPS runtime state is canonical and must not be lost:
  substrate, secrets, provider state, web-proxy auth artifacts, package
  registry, Telegram session.
- Documentation was not implementation-ready at session start; this session is
  fixing that baseline first.

## Last Completed Change

- Finalized the split direction: `SonyaLegacy` archive + fresh `SonyaCore`.
- Added runtime-state preservation as a hard constraint of the split.
- Created this tracker and the master restructuring checklist.
- Rewrote `docs/operations/MONOREPO_SPLIT_DESIGN.md` to include:
  - `SonyaTools` / `SonyaSkills` split
  - JSON package registry at `~/.sonya/package_registry.json`
  - multi-repo deploy design
  - legacy archive strategy
  - runtime migration / bootstrap section
- Restored and normalized canonical docs around the restructuring:
  `STATE.md`, `DOCUMENTATION_AUDIT.md`, `HANDOFF.md`, `INDEX.md`,
  `MASTER.md`, `FINAL_STATE_TODO.md`, and `SONYA_RUNTIME_COHERENCE_AUDIT.md`.

## Next Steps

1. Review the full documentation diff and commit docs only.
2. Archive the current repo as `SonyaLegacy` in a separate folder / remote.
3. Create fresh repos for the new active layout.
4. Prepare runtime bootstrap so the same VPS substrate and secrets continue
   under the new repo layout.

## Active Risks

- Losing or reinitializing `~/.sonya/sonya_substrate.db` is an invalid outcome.
- Losing provider secrets or web-proxy auth artifacts is an invalid outcome.
- Cutting fresh repos before the docs baseline is committed will make the split
  harder to hand off safely.
- Service restart semantics must stay stable even if deploy logic changes.

## Files That Must Stay In Sync

- `docs/operations/MONOREPO_SPLIT_DESIGN.md`
- `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`
- `docs/MASTER.md`
- `docs/STATE.md`
- `docs/HANDOFF.md`
- `docs/RESTRUCTURING_MASTER_CHECKLIST.md`
- this file

## Update Rule

After each meaningful change, update:

- `Current State` if reality changed
- `Last Completed Change`
- `Next Steps`

Do not turn this file into a raw session log. Keep it concise and operational.
