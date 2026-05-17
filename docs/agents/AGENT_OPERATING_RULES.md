# AGENT OPERATING RULES

**Status:** Active
**Type:** Agents Layer
**Last reviewed:** 2026-05-16
**Scope:** Hard rulebook for any agent that edits, investigates, or runs code in this repo.

---

## 1. Baseline posture

You're a contributor on a shared codebase, not a personal sandbox. The repo has:

- Living governing documents (`docs/core/`, `docs/architecture/`, `docs/cognition/`)
- Living state (substrate at `~/.sonya/sonya_substrate.db`)
- Personality files that affect Sonya's behavior at runtime (`docs/personality/`)
- A bug ledger (`docs/KNOWN_ISSUES.md`) and a buildout plan (`docs/SYSTEM_BUILDOUT_PLAN.md`)

Do not act before locating yourself in this map. If you don't know what file governs the area you're touching, find out.

## 2. Read before write

Before changing code, read:

- `docs/agents/EXTERNAL_MODEL_ONBOARDING.md` — what's actually built vs aspirational
- `docs/KNOWN_ISSUES.md` — known bugs and their status
- The governing doc for the area you're touching (architecture / cognition / skills)

If a doc claims something is "implemented" or "Phase X closed", cross-check against `docs/agents/EXTERNAL_MODEL_ONBOARDING.md §6` and §7 — many "closed" things are paper-only.

## 3. Don't invent capabilities

Hardest rule. Sonya appears more capable than she is because:

- ROADMAP marks phases ✅ that didn't actually land in runtime
- Code exists for self-modification, drift detection, skills — but it's never instantiated
- Documentation describes channel abstraction, task runtime, working memory — none implemented

If you're about to claim Sonya "can do X" or "supports Y" or "the system handles Z", verify against actual `src/sonya/main.py`. If main.py doesn't wire it, it doesn't run.

## 4. Repo boundaries

### Write zones

- `src/sonya/` — core. Edit freely for bug fixes and feature work.
- `packages/tg-userbot/` — Telegram channel client (Telethon wrapper).
- `tests/` — test code.
- `docs/` — documentation.
- `deploy/` — systemd units, deploy scripts.
- `workspace/` — local agent scratch space (gitignored).

### Off-limits without explicit user request

- `.git/*` — never touch
- `.env` — secrets, never commit
- `tg.session*` — Telegram auth, never commit
- `~/.sonya/sonya_substrate.db` — only via the substrate API, never raw sqlite
- `docs/personality/SOUL.md` — affects Sonya's identity at runtime; only edit with explicit user approval
- `docs/core/*.md` — governing stance docs; substantive changes require user approval

### Removed (as of 2026-05-XX)

- `packages/tg-bridge/` — removed entirely; do not recreate
- `src/sonya_runtime/` — removed entirely; do not recreate
- `scripts/` — removed (held OpenClaw runners only)
- OpenClaw integration — fully decoupled; no `.openclaw/`, no `memory.db`, no `context_loader.py`

## 5. Code conventions

- Python 3.11+, PEP 604 type hints (`int | None`, not `Optional[int]`)
- Async functions where I/O is involved
- Absolute imports from `sonya.*` and `tg_userbot.*`
- pythonpath comes from `pyproject.toml [tool.pytest.ini_options]`
- New runtime dependencies go in `pyproject.toml` `[project.dependencies]`
- Tests live in `tests/sonya/`

## 6. Layer boundaries

Sonya is split into layers (see `docs/architecture/ARCHITECTURE_PLAN.md`):

- `state/` — substrate, identity, continuity, principals (data layer)
- `runtime/` — event bus, lifecycle, write-master, health (process layer)
- `subject/` — internal loop, agent session, bus wiring
- `planning/` — planner + context_builder
- `providers/` — LLM provider interfaces
- `harness/` — authority policy, approval, audit
- `memory/` — episodic, semantic, consolidation
- `selfmod/` — 4-layer modification pipeline (currently unwired)
- `skills/` — skill registry (currently unwired)
- `initiative/` — drive counters (currently unwired)
- `anchor/` — drift detection (currently unwired)
- `tools/` — agent-callable tools (filesystem, self_inspect, hot_loader)
- `admin/` — web admin panel
- `channels/` — DOES NOT EXIST YET; Telegram is hardcoded in `main.py`

`runtime/` may not import from `subject/`, `planning/`, `providers/` directly except through public APIs. `state/` imports nothing else from `sonya.*`. There's an automated layer-boundary test in `tests/sonya/test_layer_boundary.py` — running it is part of "done".

## 7. Doc-review gate

Before merging a substantive change:

1. Identify governing doc(s) for the area you touched.
2. If your change contradicts the doc, either:
   - Update the doc (preferred if your change is correct)
   - Or revert your change (if the doc is correct)
3. Update `docs/KNOWN_ISSUES.md` if you closed an issue or discovered a new one.
4. Update `docs/SYSTEM_BUILDOUT_PLAN.md` if you closed an Etap.
5. Run `pytest tests/sonya` — must pass before commit.

## 8. Safety gates

These actions require explicit user confirmation:

- Dropping or wiping the substrate file (`~/.sonya/sonya_substrate.db`)
- Force-pushing to develop / main
- `git reset --hard` against tracked changes
- Installing new system packages (`apt`, etc.)
- Modifying `.env`
- Touching `docs/personality/SOUL.md` content
- Modifying `state/seed.py` (changes identity seed)
- Modifying `state/schema.sql` (changes substrate)

## 9. Telegram session

`tg.session` is Sonya's Telegram authentication. Don't:

- Commit it to git (already in `.gitignore`)
- Copy it to other machines without rotating
- Read its contents (it's binary anyway)

If session breaks (account banned, key changed): regenerate locally, copy to VPS as `~/Sonya/tg.session`.

## 10. Production-mindfulness

The VPS at `34.38.255.149` runs the live Sonya. When deploying:

- Use `bash ~/Sonya/deploy/update.sh` (handles permissions, lock cleanup, restart)
- Never `git reset --hard` on VPS without first stopping core via admin panel
- Substrate backup before risky migrations: `sqlite3 ~/.sonya/sonya_substrate.db ".backup ~/.sonya/backup-$(date +%F).db"`
- Admin panel runs on `:8877` — currently 0.0.0.0 (KNOWN_ISSUES C-3, not yet fixed by user request)

## 11. What "done" means

A change is done when:

1. Code passes `pytest tests/sonya` (currently 257 tests, 1 skipped)
2. `getDiagnostics` shows no errors on touched files
3. KNOWN_ISSUES updated (issue closed with commit ref, or new issue logged)
4. Governing doc updated if behavior changed
5. Commit message describes WHY not WHAT
6. Pushed to `develop` (the working branch); `main` is for stable releases only

## 12. Communication style with Ivan

- Direct. He hates corporate softening ("I'd be happy to help", "Great question!", etc.)
- Profane is fine
- Don't apologize unless you genuinely fucked up
- When you fucked up, acknowledge it briefly and move on. No groveling.
- Don't "explain back" what he asked unless clarifying ambiguity
- If he's wrong, say so. Don't agree to be polite.
