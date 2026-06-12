# Runtime Coherence Workflow

**Status:** Active
**Type:** Operations runbook
**Last updated:** 2026-06-12

This document is the operating runbook for implementing and proving items from
[`docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`](../SONYA_RUNTIME_COHERENCE_AUDIT.md)
on the current Sonya VPS.

Use this when the work changes runtime behavior, state semantics, cognition,
provider routing, work execution, embodiment, continuity, or observability.

## 1. Read Order Before Touching Anything

1. `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`
2. `docs/STATE.md`
3. `docs/HANDOFF.md`
4. `docs/operations/VPS.md`

The audit defines the problem and checklist. `STATE.md` defines current proven
reality. `HANDOFF.md` defines the active continuation point and known traps.
`VPS.md` defines host-level operations and recovery paths.

## 2. Current Production Baseline

- Host: `jester-sonya@34.38.255.149`
- Production repo: `/home/jester-sonya/Sonya`
- Production substrate: `/home/jester-sonya/.sonya/sonya_substrate.db`
- Runtime services: `sonya.service`, `sonya-admin.service`
- Deploy rule: do not run Sonya locally; verify on the VPS or on an isolated
  VPS copy

Known unrelated dirt that must not be reverted unless the user explicitly asks:

- local: `tmp-planner-dump.txt`
- local: `.tmp_remote_provider_refresh_dir`
- VPS: `/home/jester-sonya/Sonya/tg.session`

## 3. Work Cycle For One Audit Item

1. Pick the exact checklist item in
   `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`.
2. Define the proof before coding:
   - what test or focused suite should pass;
   - what production or production-equivalent evidence is required;
   - what docs must change when the proof exists.
3. Make the code change in the local repo.
4. Run local static verification only if it does not require a local runtime.
5. Run VPS isolated-copy verification.
6. If the isolated proof is clean, create a production backup.
7. Fast-forward the VPS checkout without trashing runtime dirt.
8. Restart only the needed services.
9. Run post-deploy checks on the live VPS.
10. Only then mark the audit checklist item done and update state docs.

Do not close a checklist item based only on reasoning or local edits.

## 4. Editing Rules

- Use `apply_patch` for manual file edits.
- Do not use `git reset --hard` or `git checkout --`.
- Do not use `deploy/update.sh` when the VPS checkout has unrelated runtime dirt
  such as `tg.session`.
- Do not store credentials in docs, current-state notes, audit logs, or
  environment-state tables.
- Do not bind Sonya's main runtime model through `.env`. Provider/model choice
  belongs to substrate/runtime logic, not host env config.

## 5. Local Git Flow

Work from the local repository first.

Inspect:

```powershell
git status --short
git branch --show-current
```

Review your delta:

```powershell
git diff -- docs
git diff -- src tests
```

Stage only intended files:

```powershell
git add docs/SONYA_RUNTIME_COHERENCE_AUDIT.md
git add docs/STATE.md docs/HANDOFF.md
git add src tests
```

Commit:

```powershell
git commit -m "Describe the actual runtime change"
```

Push:

```powershell
git push origin develop
```

If the branch is not `develop`, push the active branch explicitly and document
why.

## 6. VPS Isolated-Copy Verification

Do not test risky runtime changes directly in the live production checkout
first. Use an isolated VPS copy.

SSH into the host:

```bash
ssh jester-sonya@34.38.255.149
```

Create or refresh an isolated copy:

```bash
rm -rf /tmp/sonya-proof
git clone /home/jester-sonya/Sonya /tmp/sonya-proof
cd /tmp/sonya-proof
git fetch origin
git checkout develop
git reset --hard origin/develop
```

Create the venv if needed and install deps:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .[dev]
```

Run focused verification from that isolated copy:

```bash
. .venv/bin/activate
pytest tests/sonya/... -q
python -m compileall src
```

For migration work, copy the live substrate instead of touching it in place:

```bash
cp /home/jester-sonya/.sonya/sonya_substrate.db /tmp/sonya-proof.db
PYTHONPATH=src python -m sonya.substrate.migrate /tmp/sonya-proof.db
```

Record exact results in `STATE.md` and `HANDOFF.md` only after the proof passes.

## 7. Production Backup Before Runtime Deploy

Before any live migration or state-shape change:

```bash
mkdir -p /home/jester-sonya/backups
cp /home/jester-sonya/.sonya/sonya_substrate.db \
  /home/jester-sonya/backups/sonya-$(date +%Y%m%d-%H%M%S).db
```

If the change touches a live WAL-heavy database, prefer an SQLite-safe backup
method already used by the runtime scripts or capture the proof on a copied
database first and then take the production backup immediately before deploy.

## 8. Safe VPS Update Procedure

Use fast-forward update steps manually when runtime dirt exists.

```bash
ssh jester-sonya@34.38.255.149
cd /home/jester-sonya/Sonya
git status --short
```

If unrelated runtime dirt is present, preserve it and update tracked files only:

```bash
git fetch origin
git stash push -- tg.session
git merge --ff-only origin/develop
git stash pop
```

If `tg.session` is untracked or the stash approach is noisy, preserve it by
copying it aside first and restoring it after the fast-forward.

Do not use `reset --hard` here unless the user explicitly asks for destructive
recovery.

## 9. Service Restart And Live Checks

Restart only the system services:

```bash
sudo systemctl restart sonya.service sonya-admin.service
```

Check health:

```bash
sudo systemctl is-active sonya.service sonya-admin.service
sudo journalctl -u sonya.service -n 100 --no-pager
sudo journalctl -u sonya-admin.service -n 100 --no-pager
```

If the change touched schema, providers, cognition, or Atrium runtime behavior,
also run targeted live checks:

```bash
sqlite3 /home/jester-sonya/.sonya/sonya_substrate.db "PRAGMA user_version;"
curl -I http://127.0.0.1:8877/atrium/
```

Use narrower probes when the slice has a specific contract to prove.

## 10. Documentation Update Rules

Update these docs together when the evidence exists:

- `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`
- `docs/STATE.md`
- `docs/HANDOFF.md`

What goes where:

- Audit: problem status and checklist state
- State: current verified reality
- Handoff: exact continuation point, recent proof, known blockers

Do not turn these files into a raw command dump. Keep the evidence concise and
specific.

## 11. Handling Known Fragile Cases

There is a known fragile VPS timing test:

- `tests/sonya/test_internal_loop.py::test_internal_process_emits_on_idle_timeout`

Treat it as unrelated noise unless your slice directly changes internal-loop
timing semantics. Do not claim a regression from that test alone without
separate evidence.

## 12. Definition Of Done For An Audit Slice

An audit slice is done only when all of these are true:

- code and tests for the slice are committed locally;
- the branch is pushed;
- isolated VPS proof passed;
- production backup exists if live state was at risk;
- production VPS is updated;
- required services are healthy;
- targeted live checks passed;
- `SONYA_RUNTIME_COHERENCE_AUDIT.md`, `STATE.md`, and `HANDOFF.md` are updated.

If any one of those is missing, the slice is still in progress.
