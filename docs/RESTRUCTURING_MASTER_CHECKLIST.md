# Restructuring Master Checklist

**Status:** Active
**Type:** Master execution checklist
**Last updated:** 2026-06-15

## 1. Documentation Baseline

- [ ] Finish and commit restructuring documentation before implementation
- [ ] Keep `docs/RESTRUCTURING_STATUS.md` updated after every meaningful change
- [ ] Keep `docs/HANDOFF.md` aligned with current continuation point
- [ ] Keep `docs/STATE.md` aligned with verified current reality

## 2. Legacy Archive

- [ ] Preserve current repo as `SonyaLegacy` with full `.git`
- [ ] Create separate archive remote for `SonyaLegacy`
- [ ] Mark `SonyaLegacy` as read-only baseline, not active development home

## 3. Fresh Active Repos

- [ ] Create fresh `SonyaCore`
- [ ] Create fresh `SonyaTools`
- [ ] Create fresh `SonyaSkills`
- [ ] Create fresh `SonyaAdmin`
- [ ] Create fresh `Atrium`
- [ ] Create fresh `SonyaTgUserBot`

## 4. Runtime State Preservation

- [ ] Back up `~/.sonya/sonya_substrate.db`
- [ ] Back up package registry
- [ ] Back up provider/account secret storage
- [ ] Back up web-proxy auth/session artifacts
- [ ] Back up Telegram session state
- [ ] Prove new runtime uses the same preserved state

## 5. Package Registry

- [ ] Implement registry loading from `~/.sonya/package_registry.json`
- [ ] Replace hardcoded `packages/*/` discovery
- [ ] Support package slots for tools, skills, channels, workers, services
- [ ] Make registry mutations observable and auditable

## 6. Repo Split Execution

- [ ] Move core-only runtime code to `SonyaCore`
- [ ] Move low-coupling tools to `SonyaTools`
- [ ] Move low-coupling skills to `SonyaSkills`
- [ ] Move admin code to `SonyaAdmin`
- [ ] Move Atrium UI to `Atrium`
- [ ] Move Telegram package to `SonyaTgUserBot`

## 7. Deployment Rework

- [ ] Add `deploy/multi_update.py`
- [ ] Make `deploy/update.sh` a thin wrapper
- [ ] Support ordered multi-repo updates
- [ ] Support rollback branch creation per repo
- [ ] Keep `sonya.service` / `sonya-admin.service` semantics stable

## 8. Runtime Bootstrap On VPS

- [ ] Check out fresh repos beside legacy archive
- [ ] Install Python repos in target runtime environment
- [ ] Rebind services to new checkouts
- [ ] Reconnect package registry to new repo paths
- [ ] Verify substrate, provider state, and Telegram session continuity

## 9. Product Follow-Ons After Split

- [ ] Atrium channel identity fix
- [ ] Admin/Atrium backend separation inside new repo layout
- [ ] Web-proxy provider implementation
- [ ] Selfmod repair
- [ ] Background activity system
- [ ] Project/subagent end-to-end proofs

## 10. Completion Condition

- [ ] Fresh-repo runtime is live on VPS
- [ ] Same substrate/memory/secrets are preserved
- [ ] Old monorepo is archived safely
- [ ] Documentation matches the new reality
