# Monorepo Split Design

**Status:** Active design — implementation not started
**Last updated:** 2026-06-15
**Parent audit:** [`docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`](../SONYA_RUNTIME_COHERENCE_AUDIT.md) §2

## 1. Problem Statement

The current repository is overloaded in two different ways at once:

1. It carries **582 commits of mixed history** that must be preserved, but this
   history is now a liability for fresh work on `SonyaCore`.
2. It mixes **six different source domains** in one repo:

| Current path | Nature | Build | Language | Split target |
|---|---|---|---|---|
| `src/sonya/` minus `admin/`, `tools/`, `skills/` | Runtime core | `pyproject.toml` | Python | `SonyaCore` |
| `src/sonya/tools/` | Tool implementations | shared with core | Python | `SonyaTools` |
| `src/sonya/skills/` | Skill runtime + builtins | shared with core | Python | `SonyaSkills` |
| `src/sonya/admin/` | Admin server + current Atrium backend routes | shared with core | Python | `SonyaAdmin` |
| `packages/atrium/` | Desktop / hosted UI | `package.json` + `Cargo.toml` | TS/JS + Rust | `Atrium` |
| `packages/tg-userbot/` | Telegram userbot | package-local `pyproject.toml` | Python | `SonyaTgUserBot` |

Consequences:

- Atrium styling or frontend work shares git history with cognition, memory,
  provider routing, and selfmod.
- Admin and Atrium backend concerns are entangled in one Python module family.
- Tools and skills are source-coupled to core, which blocks safe package-level
  selfmod and independent versioning.
- The current repo is too noisy to become the clean long-term home of
  `SonyaCore`.
- A fresh repo split is required, but **continuity cannot be broken**: the live
  VPS substrate, secrets, provider state, and auth artifacts must carry forward
  into the new runtime.

## 2. Design Constraints

1. **Preserve Sonya's live memory and runtime state.** The current canonical
   runtime state is the VPS substrate and runtime secret storage, not the git
   history. Splitting repos must not reset or replace:
   - `~/.sonya/sonya_substrate.db`
   - provider/account state
   - encrypted secrets
   - web-proxy auth artifacts
   - package registry
   - Telegram session state

2. **Archive the old repo intact.** The current repository becomes a
   read-only `legacy` archive with its full `.git` and 582 commits preserved in
   a separate folder / separate remote.

3. **Start `SonyaCore` fresh.** `SonyaCore` should be a new git repository
   without inherited commit history. The new repo gets only the code and docs
   that belong to the new architecture.

4. **One stream of consciousness.** Repo split is a source-management decision,
   not a mind split. Sonya remains one runtime with one substrate, one memory,
   one continuity stream, and one project/work graph.

5. **`SonyaTools` and `SonyaSkills` are source boundaries, not runtime
   boundaries.** They must remain importable as Python modules inside the same
   process as `SonyaCore`, either as editable installs, pinned package
   dependencies, or submodules checked out beside the core repo.

6. **Sonya must be able to add packages after the split.** Selfmod should not
   need to understand multi-repo git internals. It should write to a registry,
   scaffold package metadata, and let deploy/bootstrap tooling handle checkout
   and installation.

7. **Deployment must keep the current VPS semantics.** Existing
   `sonya.service` and `sonya-admin.service` semantics remain. The update
   mechanism changes, but the operational shape must stay predictable.

## 3. Candidate Structures

### 3A. Flat sibling repos under one parent folder

```
~/Sonya/
├── SonyaLegacy/         # archived old monorepo, read-only
├── SonyaCore/           # fresh runtime repo
├── SonyaTools/          # fresh tools repo
├── SonyaSkills/         # fresh skills repo
├── SonyaAdmin/          # fresh admin repo
├── Atrium/              # fresh UI repo
└── SonyaTgUserBot/      # fresh telegram repo
```

**Pros:**
- Cleanest source boundaries
- Clean fresh history for every working repo
- Easy to archive old repo without ambiguity
- Matches the user's explicit desire to start `SonyaCore` from scratch

**Cons:**
- More repos to manage
- Requires explicit bootstrap/install process on developer machine and VPS

### 3B. Flat sibling repos + `SonyaPackages/` umbrella

```
~/Sonya/
├── SonyaLegacy/
├── SonyaCore/
├── SonyaTools/
├── SonyaSkills/
├── SonyaAdmin/
└── SonyaPackages/
    ├── Atrium/
    ├── SonyaTgUserBot/
    └── future packages...
```

**Pros:**
- Groups non-core repos operationally
- Gives future package growth one visible home

**Cons:**
- Reintroduces a mini-monorepo problem
- Makes future package isolation weaker than necessary

### 3C. `SonyaCore` as host repo with nested package clones

```
~/Sonya/
├── SonyaLegacy/
└── SonyaCore/
    ├── packages/
    │   ├── SonyaTools/
    │   ├── SonyaSkills/
    │   ├── Atrium/
    │   └── SonyaTgUserBot/
    └── ...
```

**Pros:**
- Familiar from the current tree shape
- Simplifies local relative-path development

**Cons:**
- Keeps `SonyaCore` as the gravitational center again
- Nested repos are an avoidable git mess
- Makes archive vs fresh-core boundary blurrier

### Recommendation

**3A is recommended.**

Use flat sibling repos with `SonyaLegacy/` as a frozen archive and all active
repos as fresh histories. This gives the cleanest mental model:

- old repo preserved;
- new core starts clean;
- runtime continuity comes from substrate + secrets + registry migration, not
  from dragging old git history forward.

## 4. Inter-Package Interface Contracts

### 4.1 `SonyaCore` ↔ `SonyaTools`

**Contract type:** Python package import in the same process.

`SonyaTools` exports tool modules that `SonyaCore` registers into its tool
runtime. `SonyaCore` remains the owner of:

- substrate/session ownership
- tool policy and access boundaries
- execution tracing
- selfmod governance

`SonyaTools` can depend on `SonyaCore` public contracts, but not on private
internal file layout assumptions. The import contract should be stabilized
around explicit registries and typed protocols, not “import random module from
deep core path”.

### 4.2 `SonyaCore` ↔ `SonyaSkills`

**Contract type:** Python package import in the same process.

`SonyaSkills` contains the generic skill runtime and low-coupling builtins.
`SonyaCore` owns:

- identity-sensitive skill boundaries
- substrate-backed skill traces
- selfmod proposal generation and application

The split is **source-only**. At runtime, skills still execute inside the same
Sonya process and use the same continuity/memory graph.

### 4.3 `SonyaCore` ↔ `SonyaTgUserBot`

**Contract type:** Channel interface + package registry entry.

`SonyaTgUserBot` must expose a factory import path that the registry can load,
for example:

`tg_userbot.channel:build`

The userbot should not own substrate state directly. It emits inbound channel
events and consumes outbound deliveries through the channel contract.

### 4.4 `SonyaCore` ↔ `SonyaAdmin`

**Contract type:** Short-term same-process Python dependency.

Short-term recommendation:

- `SonyaAdmin` imports `SonyaCore` as a Python dependency.
- `SonyaAdmin` remains the host for operator control APIs and, on the first
  migration stage, Atrium-facing backend APIs.

This is intentionally conservative. It avoids forcing a distributed runtime
boundary while the repo split is still fresh.

### 4.5 `SonyaAdmin` ↔ `Atrium`

**Contract type:** HTTP + WebSocket only.

`Atrium` must not access substrate files or Python internals directly. It talks
to backend APIs and the live WS feed. Current recommendation:

- Atrium endpoints stay in `SonyaAdmin` for the first split stage.
- They must be separated from admin-only endpoints by routing, auth scope, and
  module boundary, even if they still live in the same repo initially.

### 4.6 `SonyaCore` ↔ Future packages

**Contract type:** Package registry + explicit package manifest.

Every future package should register through
`~/.sonya/package_registry.json`, not by requiring hardcoded path sweeps.
Packages may declare one or more of these slots:

- `channels`
- `tools`
- `skills`
- `workers`
- `services`

`SonyaCore` loads only declared, enabled entries.

## 5. Package Registry

**Recommended location:** `~/.sonya/package_registry.json`

This file is recommended because it is:

- outside git;
- runtime-local;
- writable by Sonya without requiring git fluency;
- easy to back up with the rest of `~/.sonya/`.

Example:

```json
{
  "version": 1,
  "workspace_root": "/home/jester-sonya/Sonya",
  "packages": [
    {
      "name": "sonya-tools",
      "repo_path": "/home/jester-sonya/Sonya/SonyaTools",
      "kind": "python",
      "enabled": true,
      "install_mode": "editable",
      "tools": [
        "sonya.tools.browser_tool",
        "sonya.tools.code_tool",
        "sonya.tools.filesystem",
        "sonya.tools.web_tool"
      ],
      "skills": [],
      "channels": [],
      "workers": [],
      "services": []
    },
    {
      "name": "sonya-skills",
      "repo_path": "/home/jester-sonya/Sonya/SonyaSkills",
      "kind": "python",
      "enabled": true,
      "install_mode": "editable",
      "tools": [],
      "skills": [
        "sonya.skills.activation",
        "sonya.skills.registry",
        "sonya.skills.builtins.dialog_tone"
      ],
      "channels": [],
      "workers": [],
      "services": []
    },
    {
      "name": "sonya-tg-userbot",
      "repo_path": "/home/jester-sonya/Sonya/SonyaTgUserBot",
      "kind": "python",
      "enabled": true,
      "install_mode": "editable",
      "tools": [],
      "skills": [],
      "channels": [
        {
          "id": "telegram_userbot",
          "factory": "tg_userbot.channel:build"
        }
      ],
      "workers": [],
      "services": []
    },
    {
      "name": "marketer",
      "repo_path": "/home/jester-sonya/Sonya/Marketer",
      "kind": "python",
      "enabled": false,
      "install_mode": "editable",
      "tools": [
        "marketer.tools.outreach"
      ],
      "skills": [
        "marketer.skills.follow_up"
      ],
      "channels": [],
      "workers": [
        "marketer.worker:build"
      ],
      "services": []
    }
  ]
}
```

Registry rules:

- registry lives beside substrate/secrets, not in git;
- Sonya may add entries, disable entries, or adjust install mode;
- deploy/bootstrap tooling is responsible for reconciling the registry with
  actual checkouts and installs;
- registry changes are observable events, not silent mutations.

## 6. Migration Steps

### 6.1 Source migration table

These counts are the current **tracked source-file baselines** and should be
used for migration accounting:

| Target repo | Current source area | Count | Notes |
|---|---|---:|---|
| `SonyaLegacy` | entire current repo | 582 commits | archive intact, no fresh development |
| `SonyaCore` | `src/sonya/` excluding `admin/`, `tools/`, `skills/` | 116 tracked files | plus selected root manifests, tests, deploy files |
| `SonyaTools` | `src/sonya/tools/` | 30 Python files | source boundary only; same-process runtime |
| `SonyaSkills` | `src/sonya/skills/` | 15 Python files | source boundary only; same-process runtime |
| `SonyaAdmin` | `src/sonya/admin/` | 7 Python files | first-stage Atrium backend remains here |
| `Atrium` | `packages/atrium/` | 52 tracked files | excluding `node_modules`, build output |
| `SonyaTgUserBot` | `packages/tg-userbot/` | 4 tracked files | self-contained package |

### 6.2 Execution order

1. Commit the final documentation baseline in the current repo.
2. Archive current repo as `SonyaLegacy` with full `.git`.
3. Create fresh empty repos for:
   - `SonyaCore`
   - `SonyaTools`
   - `SonyaSkills`
   - `SonyaAdmin`
   - `Atrium`
   - `SonyaTgUserBot`
4. Copy source into each new repo according to the split map.
5. Rebuild local editable-install bootstrap.
6. Introduce package registry loading in `SonyaCore`.
7. Migrate VPS checkout layout without replacing substrate/secrets.
8. Only after bootstrap works, touch multi-repo deploy automation.

## 7. Decisions And Recommendations

### 7.1 Resolved recommendations

- **Archive strategy:** current repo becomes `SonyaLegacy` with full git
  history preserved.
- **Fresh core strategy:** `SonyaCore` starts as a new repo with no inherited
  history.
- **Package registry:** use `~/.sonya/package_registry.json`.
- **Admin runtime:** keep `SonyaAdmin` as a same-process importer of
  `SonyaCore` short-term.
- **Atrium backend placement:** keep Atrium endpoints in `SonyaAdmin`
  short-term; do not invent a separate backend repo yet.
- **Git hosting:** prefer one GitHub org, `SonyaProject`; fallback is the
  `jester-sonya` user if org setup is not ready.

### 7.2 Remaining implementation decisions

- Whether package bootstrap installs use editable installs only, or editable in
  dev plus pinned wheel builds in production.
- Whether `SonyaTools` / `SonyaSkills` are pulled via sibling checkout paths or
  git submodules during the first migration stage.

## 8. Tools And Skills Split

Default rule:

- tools Sonya is expected to modify as part of routine selfmod workflows move
  to **`SonyaTools`** if they are low-coupling;
- tools that are tightly coupled to Substrate, provider state, project/work
  state, or selfmod governance stay in **`SonyaCore`**;
- skills that are generic behavior modules move to **`SonyaSkills`**;
- skills tied directly to identity/memory/substrate-sensitive runtime remain in
  **`SonyaCore`**.

### 8.1 Tools

| File | Repo | Justification |
|---|---|---|
| `src/sonya/tools/browser_tool.py` | `SonyaTools` | low-coupling external capability |
| `src/sonya/tools/code_tool.py` | `SonyaTools` | write-safe selfmod target |
| `src/sonya/tools/filesystem.py` | `SonyaTools` | write-safe selfmod target |
| `src/sonya/tools/hot_loader.py` | `SonyaTools` | package-loading utility with low coupling |
| `src/sonya/tools/knowledge.py` | `SonyaTools` | content-management capability, low core coupling |
| `src/sonya/tools/module_loader.py` | `SonyaTools` | write-safe selfmod target |
| `src/sonya/tools/sanitize.py` | `SonyaTools` | write-safe helper utility |
| `src/sonya/tools/web_tool.py` | `SonyaTools` | low-coupling external capability |
| `src/sonya/tools/__init__.py` | `SonyaTools` | package root |
| `src/sonya/tools/plugins/__init__.py` | `SonyaTools` | package namespace root |
| `src/sonya/tools/env_tool.py` | `SonyaCore` | touches runtime state / protected environment logic |
| `src/sonya/tools/import_history.py` | `SonyaCore` | migration utility tied to memory/runtime history |
| `src/sonya/tools/import_omniroute_keys.py` | `SonyaCore` | provider-secret import path |
| `src/sonya/tools/import_openclaw.py` | `SonyaCore` | provider/account import path |
| `src/sonya/tools/import_provider_accounts.py` | `SonyaCore` | substrate/provider import path |
| `src/sonya/tools/memory_migration_manifest.py` | `SonyaCore` | memory migration bookkeeping |
| `src/sonya/tools/memory_semantic_dedup.py` | `SonyaCore` | semantic-memory maintenance tied to substrate |
| `src/sonya/tools/memory_tool.py` | `SonyaCore` | direct memory/substrate access |
| `src/sonya/tools/model_eval_tool.py` | `SonyaCore` | provider/model scorecard coupling |
| `src/sonya/tools/projects_tool.py` | `SonyaCore` | project runtime owner |
| `src/sonya/tools/providers_tool.py` | `SonyaCore` | provider/account governance |
| `src/sonya/tools/selfmod_tool.py` | `SonyaCore` | identity-sensitive selfmod governance |
| `src/sonya/tools/self_inspect.py` | `SonyaCore` | introspects live runtime state |
| `src/sonya/tools/shell_tool.py` | `SonyaCore` | high-risk capability with policy coupling |
| `src/sonya/tools/skills_tool.py` | `SonyaCore` | tied to skill registry/governance |
| `src/sonya/tools/subagent_model_picker.py` | `SonyaCore` | model-routing logic tied to provider state |
| `src/sonya/tools/subagent_tool.py` | `SonyaCore` | subagent orchestration owner |
| `src/sonya/tools/tasks_tool.py` | `SonyaCore` | legacy task/work compatibility |
| `src/sonya/tools/work_tool.py` | `SonyaCore` | work-state lifecycle owner |
| `src/sonya/tools/workspace_transport.py` | `SonyaCore` | workspace/project boundary enforcement |

### 8.2 Skills

| File | Repo | Justification |
|---|---|---|
| `src/sonya/skills/activation.py` | `SonyaSkills` | generic skill activation logic |
| `src/sonya/skills/executor.py` | `SonyaSkills` | generic skill runtime executor |
| `src/sonya/skills/injection.py` | `SonyaSkills` | generic skill injection logic |
| `src/sonya/skills/registry.py` | `SonyaSkills` | skill registry belongs to the skill system source boundary |
| `src/sonya/skills/skill.py` | `SonyaSkills` | core skill abstraction |
| `src/sonya/skills/trust.py` | `SonyaSkills` | generic skill trust model |
| `src/sonya/skills/builtins/dialog_tone.py` | `SonyaSkills` | low-coupling builtin behavior |
| `src/sonya/skills/builtins/osint.py` | `SonyaSkills` | low-coupling builtin content/behavior |
| `src/sonya/skills/builtins/sqli.py` | `SonyaSkills` | low-coupling builtin content/behavior |
| `src/sonya/skills/builtins/wp_pentest.py` | `SonyaSkills` | low-coupling builtin content/behavior |
| `src/sonya/skills/__init__.py` | `SonyaSkills` | package root |
| `src/sonya/skills/builtins/__init__.py` | `SonyaSkills` | package root |
| `src/sonya/skills/gap_detector.py` | `SonyaCore` | directly coupled to substrate/proposal flow |
| `src/sonya/skills/builtins/identity_check.py` | `SonyaCore` | identity-sensitive builtin |
| `src/sonya/skills/builtins/memory_search.py` | `SonyaCore` | memory-sensitive builtin |

## 9. Deployment Rework

### 9.1 Current problem

The current `deploy/update.sh` assumes one repo:

- fetch
- fast-forward merge
- optional fallback branch handling for selfmod changes
- restart services

This is not enough once code is split across multiple active repos.

### 9.2 New deployment shape

Add `deploy/multi_update.py` as the real deploy orchestrator. Keep
`deploy/update.sh` as a thin wrapper that calls Python.

`multi_update.py` responsibilities:

1. Read `~/.sonya/package_registry.json`.
2. Resolve all registered active repos.
3. For each repo:
   - fetch latest changes
   - fast-forward when clean
   - detect selfmod-authored local commits
   - commit/push pending selfmod deltas where allowed
   - create rollback branch on update failure
4. Enforce deploy order:
   - `SonyaCore`
   - `SonyaTools`
   - `SonyaSkills`
   - `SonyaAdmin`
   - `SonyaTgUserBot`
   - `Atrium`
5. Notify operator on failure through admin-visible status/event surfaces.

### 9.3 Rollback model

For each repo update attempt:

- create `rollback/<timestamp>-<repo>` branch before risky move;
- if pull/apply/push fails, leave repo on safe previous commit and record the
  failure;
- never clobber runtime-only files such as sessions or secrets.

### 9.4 Shell wrapper

`deploy/update.sh` becomes:

- environment/bootstrap check
- call to `python -m deploy.multi_update`
- pass-through exit code

This keeps current operator habits intact while moving the logic out of bash.

### 9.5 Service semantics

Do **not** change the meaning of:

- `sonya.service`
- `sonya-admin.service`

Systemd semantics stay stable. Only the code checkout/install/update procedure
changes beneath them.

## 10. Runtime State Migration And Bootstrap

This split is only valid if the same live Sonya carries forward.

### 10.1 Canonical runtime state to preserve

The following state is canonical and must be imported into the new fresh-repo
layout without reset:

- `~/.sonya/sonya_substrate.db`
- `~/.sonya/package_registry.json`
- encrypted provider/account secrets
- provider/account/offering observations
- web-proxy auth/session artifacts
- Telegram session state
- current service env/runtime files that are intentionally outside git

### 10.2 Rules

- Git history is archived in `SonyaLegacy`; it is **not** the continuity
  carrier.
- Runtime state remains outside git and is mounted/reused by the new repos.
- New `SonyaCore` must point to the **same substrate path** on VPS unless a
  carefully verified migration explicitly moves it.
- If a schema migration is needed during the split, it must be treated as a
  separate audited change with backup and proof.

### 10.3 Bootstrap sequence on VPS

1. Freeze current repo as legacy checkout.
2. Back up substrate and runtime secret directories.
3. Check out fresh repos beside the archive.
4. Install `SonyaCore`, `SonyaTools`, `SonyaSkills`, `SonyaAdmin`,
   `SonyaTgUserBot` in the target runtime environment.
5. Recreate package registry entries for the new paths.
6. Start services against the same `~/.sonya/` state.
7. Verify:
   - substrate readable
   - provider secrets readable
   - account offerings still present
   - Telegram session still valid
   - Atrium/admin reachable
8. Only after that retire the old active checkout from service use.

### 10.4 Acceptance rule

The split is not complete until the fresh-repo runtime starts on VPS while
preserving the existing memory, provider state, and auth continuity with no
reinitialized “new Sonya” state.
