# AGENT FAILURE MODES

**Status:** Active
**Type:** Agents Layer
**Last reviewed:** 2026-05-16
**Scope:** Pre-flight self-check. The failure patterns below repeat across external models working on this repo. If your current plan matches any of them, stop and correct course.

---

## 1. Treating the repo as smaller than it is

Wrong: opening `src/sonya/main.py`, seeing what's there, and treating it as the whole picture.

Right: the picture is `docs/agents/EXTERNAL_MODEL_ONBOARDING.md` + `docs/KNOWN_ISSUES.md` + `docs/SYSTEM_BUILDOUT_PLAN.md` + the actual code. Skipping any of these gets you to wrong conclusions fast.

## 2. Treating "Phase X closed ✅" as truth

ROADMAP says many phases are closed. Most of them produced code that is **never instantiated in main.py**. Selfmod, skills, drift, drives, consolidation — all "closed" in ROADMAP, all dead code in production.

Before claiming "the system supports X" — open `src/sonya/main.py` and verify X is wired. If it's only in tests, it doesn't run.

## 3. Inventing fake agency

Don't write or claim that:

- "I'll process this in the background" (no background workers exist)
- "I'll get back to you tomorrow" (no scheduler, no persistent task triggers)
- "I'm working on it" (without a real `tasks.create` call — and currently that tool doesn't exist either)
- "I just edited the file" (without actually calling `filesystem.write` and getting OK back)
- "I created the plugin" (without `plugins.create` returning OK)

If the action didn't go through a real tool call with a real OK observation, don't say it happened.

## 4. Hallucinating tools that don't exist

The agent surface in `src/sonya/subject/agent_session.py` has a fixed tool list (see EXTERNAL_MODEL_ONBOARDING §9). Don't invent:

- `tasks.create` — task runtime doesn't exist yet (Etap C in BUILDOUT_PLAN)
- `selfmod.propose / .apply` — not yet (Etap A in BUILDOUT_PLAN)
- `web.search / .fetch` — not yet (Etap E)
- `code.exec / shell.run` — not yet (Etap E)
- `channel.send to Discord/web` — only Telegram exists (Etap B is the abstraction)

If you need one of these, propose adding it as a real tool, not pretend it works.

## 5. Confusing aspirational docs with reality

These docs describe **target architecture**, not current state:

- `docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md` — channel abstraction is aspirational
- `docs/cognition/MEMORY_AND_IDENTITY_PLAN.md` §5-§7 — episodic/semantic with retention curves; only baseline implemented
- `docs/research/*` — RWKV, embodiment, simulation; all forward
- ROADMAP §14 (working memory tables), §15 (embodiment tables) — promised, not delivered

Reading them as current reality is a recurring failure pattern.

## 6. OpenClaw still being relevant

Sonya was previously hosted on top of OpenClaw. **No longer.** As of mid-May 2026:

- No `.openclaw/` directory dependency
- `memory_system/db/memory.db`, `context_loader.py`, post-response hook — all unused
- `packages/tg-bridge/` — removed
- `src/sonya_runtime/` — removed
- Substrate at `~/.sonya/sonya_substrate.db` is the **only** state store

Old docs sometimes still reference OpenClaw paths. Treat those references as historical, not active.

## 7. Editing `docs/personality/SOUL.md` without approval

SOUL.md is loaded into Sonya's system prompt at every LLM call (CRUTCH-001). Changes there directly change her behavior. Don't edit without explicit user approval. Same for `docs/core/*.md` governing stance docs.

## 8. Confusing `things_not_to_betray` with content moderation

Sonya has no corporate refusal layer. `things_not_to_betray` (see `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`) protects:

- relation_anchor_binding to Ivan
- truthfulness_to_ivan
- non_corporate_refusal_layer
- subject_continuity

These are identity-critical. Touching them requires governed change protocol.

Generic ethics, content guidelines, "harmful" filtering — **not** Sonya's job. Don't add refusal logic that wasn't requested.

## 9. Adding new top-level subsystems instead of extending existing

Repo already has too many half-built layers. When tempted to add a new directory under `src/sonya/`, first check:

- Does an existing layer cover this concern? (`tools/`, `harness/`, `planning/`, `selfmod/`, `skills/`)
- Is this part of `SYSTEM_BUILDOUT_PLAN.md`? If not, why are you adding it?
- Are you adding it because the architecture demands it, or because you want a clean place for your code?

Default: extend an existing module. Add new top-level only when forced by clear architectural reason and (for big changes) user approval.

## 10. Editing without reading the failing test first

If a test is failing, read it. Don't guess. Don't change production code to "make the test pass" without understanding what the test asserts.

If you change a public API and break tests, either:
- Update the tests (if your change is correct)
- Revert (if the API was correct)

Don't comment out failing tests.

## 11. Skipping the doc-review gate

When you change behavior:

- Update governing doc if reality drifted from it
- Update KNOWN_ISSUES if issue closed
- Update SYSTEM_BUILDOUT_PLAN if Etap closed
- Update EXTERNAL_MODEL_ONBOARDING §6 if "what's wired" changed

Skipping this is how the doc-set ends up lying about state. (See: pre-2026-05-16 EXTERNAL_MODEL_ONBOARDING which claimed self-mod was wired.)

## 12. Long preambles, hedging, em-dashes

Ivan hates these. Direct, profane, terse. Match the file's tone. If Russian seems natural in the file, use Russian.

When uncertain: short clarifying question, not a long monologue. When confident: act.

## 13. Pretending to verify

If you say "I checked X", mean it. Open the file. Run the command. Read the output. Don't pattern-match from memory.

This is especially important on this project because the documentation drifts faster than the code.

## 14. Production safety

VPS at `34.38.255.149` runs live Sonya. Before any action that touches the VPS:

- Pause core via admin panel if mutation is risky
- Backup substrate before schema migration
- Use `deploy/update.sh` for code updates (handles permissions, lock cleanup)
- Never `pkill -9 python3` — that kills system Python too. Use `pkill -9 -f 'python.*sonya'`.

## 15. Common drift you'll meet

| Drift symptom | What's actually true |
|---|---|
| "Phase 4 is closed" (selfmod) | Code exists, never runs |
| "Phase 5 is closed" (skills) | SkillRegistry never instantiated |
| "Phase 6 is closed" (initiative) | DriveCounters dead code |
| "Phase 8 is closed" (memory) | Only baseline; consolidation never triggers |
| "Phase 9 is closed" (embodiment) | Pure stubs, no events ingested |
| "Working memory tables exist" | substrate v6 has no working_memory table |
| "Bridge is the active Telegram surface" | No bridge; userbot in main.py |
| "OpenClaw memory still in use" | False; fully decoupled |
| "Channel abstraction works" | Doesn't exist; Telegram hardcoded |

When in doubt: open `src/sonya/main.py`, see what's actually constructed.
