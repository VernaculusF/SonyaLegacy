# Documentation Audit

**Status:** Active
**Type:** Documentation maintenance record
**Last updated:** 2026-06-15

## Current Audit Result

The documentation set is being normalized for the restructuring phase. The main
problems at the start of this session were:

- `MONOREPO_SPLIT_DESIGN.md` was incomplete;
- `STATE.md` and `DOCUMENTATION_AUDIT.md` were missing from the worktree even
  though other docs referenced them as canonical;
- there was no dedicated live tracker for the restructuring effort;
- there was no single master checklist for the whole repo split + runtime
  preservation program.

## What This Session Adds

- restores `STATE.md` as a canonical current-reality document;
- restores this file as the documentation-maintenance record;
- adds `RESTRUCTURING_STATUS.md` as the live handoff/status tracker;
- adds `RESTRUCTURING_MASTER_CHECKLIST.md` as the master execution checklist;
- finalizes the split design around:
  - `SonyaLegacy` archive
  - fresh `SonyaCore`
  - `SonyaTools` / `SonyaSkills`
  - JSON package registry
  - multi-repo deploy
  - runtime-state migration

## Documentation Rules For This Workstream

- Update `RESTRUCTURING_STATUS.md` after every meaningful change.
- Update `STATE.md` when verified reality changes.
- Update `HANDOFF.md` at each meaningful stopping point.
- Do not let repo-split work outrun the docs baseline.

## Remaining Documentation Debt

- Ensure all top-level planning docs describe the same six-repo target.
- Remove stale references that assume the old four-deployable picture.
- Keep the restructuring tracker and checklist synchronized with actual work.
