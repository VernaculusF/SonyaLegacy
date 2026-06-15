# STATE.md — current verified reality

**Status:** Active
**Type:** Current project state
**Last updated:** 2026-06-15

## Current Reality

- Sonya is currently running from the old monorepo on the VPS.
- The repo split has **not** started yet. Documentation is the current active
  work.
- The current repository still has 582 commits and must be archived intact as
  `SonyaLegacy`.
- The future active runtime will move to fresh repos headed by a new
  `SonyaCore`.

## Canonical Live Runtime State

The following state is canonical and must survive the restructuring unchanged:

- production substrate: `/home/jester-sonya/.sonya/sonya_substrate.db`
- runtime secret storage under `~/.sonya/`
- provider/account state
- web-proxy auth artifacts
- package registry
- Telegram session state

If any restructuring step resets or discards this state, that step is invalid.

## Production Baseline To Preserve

- Host: `34.38.255.149`
- User: `jester-sonya`
- Current production repo: `/home/jester-sonya/Sonya`
- Services: `sonya.service`, `sonya-admin.service`

Before any repo migration on VPS:

- back up substrate;
- back up runtime secrets/session artifacts;
- record exact repo/service state;
- treat repo split and schema/runtime-state migration as separate proofs.

## Current Priority

1. Finish and commit documentation baseline for restructuring.
2. Archive the old monorepo as `SonyaLegacy`.
3. Create fresh active repos.
4. Bootstrap the new layout against the same live runtime state.

## Known Important Gaps

- `MONOREPO_SPLIT_DESIGN.md` was previously incomplete and is being finalized.
- Current deploy tooling is still single-repo.
- Current package discovery still depends on old monorepo assumptions.
- Runtime migration/bootstrap is not yet implemented.
