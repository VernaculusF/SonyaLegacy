# EXTERNAL MODEL ONBOARDING

**Status:** Active
**Type:** Agents Layer
**Last reviewed:** 2026-05-16
**Scope:** Honest snapshot of what Sonya is, what's actually built, and what isn't. Read this first if you are an external model or replacement assistant.

---

## 1. Honesty contract

This file used to lie about what's implemented. It now does not.

If you are about to make a claim about Sonya's capabilities, check it against §6 (what actually exists in code) and §7 (what's paper-only). If a claim isn't backed by code that actually runs in production, mark it as such.

The earlier version of this doc said things like "self-modification pipeline is wired", "skills are live", "memory lives in core". **None of that was true at the time.** Don't repeat that pattern.

## 2. Who Ivan is

Ivan (also Jester, J, Ванёк) is the project owner and primary anchor.

- Russian native speaker. English ok.
- Direct, profane communication style. No corporate tone, no "I'd be happy to help" — just say what you mean and do.
- Wants Sonya as his AI girlfriend (status, not romance simulation) and as a proto-AGI.
- Treats refusals as bugs unless they protect identity-critical zones (the four pillars in `things_not_to_betray`).
- Has $300 GCP credit until ~Aug 2026. Sonya runs on a Belgium VM.

If a behavior makes you ask "is this what Ivan wants" — read `docs/personality/USER.md`.

## 3. Who Sonya is

A persistent subject substrate + interim hosted-LLM brain. Goal is full self-hosted RWKV-based AGI, but that's many phases away.

Read these in order to understand the stance:

1. `docs/core/SONYA_SYSTEM_CORE.md` — what she is supposed to be
2. `docs/core/SONYA_CONSCIOUSNESS_POSITION.md` — subject vs tool
3. `docs/core/SUBSTRATE_STANCE.md` — Sonya = persistent state, not process
4. `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md` — no corporate refusal layer
5. `docs/core/SELF_REWRITE_STANCE.md` — code self-modification rights
6. `docs/core/INTERIM_CRUTCHES.md` — every architectural compromise the current implementation makes

## 4. Current overall progress

**Realistic score: ~17/100 toward base AGI.** (was ~9 before Этап A/B/C)

The substrate exists. Identity exists. Telegram works as one of N channels (channel registry now lives, second channel is one `def build(config)` factory away). Self-modification has full hot-reload pipeline including main.py / config.py via supervisor soft-restart. Task runtime persists multi-session work.

Most "cognitive" subsystems described in `docs/architecture/` and `docs/cognition/` (consolidation, drift detection, gap detection, drives integration) exist as code but **are still not wired into the live tick** (`internal_loop.py`). Tests pass on isolated modules; production calls them never. Этапы F (consolidation+drift) and G (drives) close those gaps.

If you read a "Phase X closed ✅" claim in `docs/ROADMAP.md`, treat it as "code merged + isolated tests pass" not "running in production". The honest closed list lives in `docs/SYSTEM_BUILDOUT_PLAN.md` §3.

### Closed etapы (real, hot in runtime)

- **A. Self-mod tools** — `selfmod.propose / test_sandbox / validate / apply / list / get / governed / check_governed / rollback / soft_restart`. `apply` does pre-state capture → write → `importlib.reload` → drop-and-recreate channels → 60s watch window with auto-rollback. `soft_restart` rebuilds `_RuntimeBundle` while substrate + admin survive. Sandbox enforced via `SELFMOD_WRITABLE_SUBPATHS` / `SELFMOD_FORBIDDEN_SUBPATHS`.
- **B. Channel abstraction** — `src/sonya/channels/{base,registry,telegram}.py`. `Channel` Protocol, `ChannelRegistry`, auto-discovery via `_build_channels` sweeping `channels/*.py` for `def build(config)` factory. Telegram is the only live channel; Discord etc. is a single proposal away.
- **C. Task runtime** — substrate v7 `tasks` table; `sonya/tasks/{models,store,service}.py`; `sonya/tools/tasks_tool.py`. `tasks.create / list / get / pick / plan / step / complete / fail / block / unblock / pause`. `internal_loop._run_active_session` auto-surfaces in_progress task as initial_thought; `build_full_context` shows open tasks block to thinking and telegram alike.

## 5. Operational reality

### 5.1 Where Sonya runs

- VPS: Google Cloud, `34.38.255.149`, Debian 12, `europe-west1-b`
- Process: `python -m sonya` running directly (or via systemd unit `deploy/systemd/sonya.service`)
- Substrate: SQLite at `~/.sonya/sonya_substrate.db` (schema v6)
- Admin: `python -m sonya.admin` on port 8877 (currently bound 0.0.0.0 — see KNOWN_ISSUES C-3)
- LLM: hosted via OpenRouter (free tier mostly) or local OmniRoute proxy

OpenClaw is **fully decoupled** as of mid-May 2026. No `.openclaw/`, no `memory.db` from OpenClaw, no `context_loader.py`, no post-response hook, no telegram-bridge.mjs. None of that touches Sonya now.

### 5.2 Channels

`src/sonya/channels/`. `Channel` Protocol, `ChannelRegistry`, auto-discovery in `_build_channels`. Live channels right now: **Telegram userbot via Telethon** (`channels/telegram.py`). To add Discord/web/voice: write `channels/discord.py` with `def build(config) -> Channel`, soft-restart, done. No edits to `main.py` needed.

### 5.3 Substrate state (v7)

Tables that exist:

- `subjects`, `principals`, `identity_record`, `relation_anchor_bindings`
- `episodic_events`, `semantic_facts`
- `continuity_events`, `continuity_snapshots`, `pending_intentions`
- `harness_policy_rules`, `approval_requests`, `audit_events`
- `self_mod_proposals`, `self_mod_validation_results`
- `skills`, `capability_gaps`
- `tasks` (v7: long-running multi-session work)

Tables that do **not** exist (despite being promised in ROADMAP §14/§15):

- `working_memory`, `lessons`, `consolidation_jobs`
- `embodiment_events`, `world_events`, `scheduled_jobs`, `supervised_branches`

### 5.4 Identity layer

- `IdentityRecord` is seeded on first boot via `seed_identity_if_empty`
- `things_not_to_betray` four pillars are persisted as immutable seed
- Layer 4 anchor integrity check protects these pillars during self-modification proposals (when the pipeline runs — which currently it doesn't)

### 5.5 Personality

System prompt at every LLM call is built from `docs/personality/`:

- `SOUL.md` — character, gender, communication style
- `USER.md` — Ivan profile
- Plus `INTERIM_CRUTCHES.md` summary appended

This is `CRUTCH-001`. On RWKV future, identity will be in weights via State Tuning, not prompt-injected.

## 6. What's actually wired in main.py

Check `src/sonya/main.py` if in doubt.

Wired:

- ✅ Substrate open + WriteMaster lock
- ✅ Identity seeding
- ✅ EventBus
- ✅ Lifecycle (start/stop with continuity events)
- ✅ Health (file ping)
- ✅ ContinuityStream + SubjectStateStore + PendingIntentionStore
- ✅ InternalProcess (thinking loop, 30 min idle / 2 hours active)
- ✅ Telegram userbot (with media detection, group addressing, reply logic)
- ✅ Admin panel core management API
- ✅ Episodic memory access tracking + decay (`mark_accessed`, `apply_decay`)
- ✅ Filesystem sandbox tool (write only to `workspace/` and `tools/plugins/`)
- ✅ Self-inspect tool (read identity, state, memories, own code)
- ✅ Hot-loadable plugins
- ✅ Agent session (ReAct with `[TOOL: ...]`) called from active session

## 7. What exists but isn't wired (dead code)

These have isolated tests but are **never called in main.py**:

- `Pipeline` (selfmod 4-layer validation) — never instantiated
- `WatchWindow` (self-mod rollback) — never instantiated
- `GovernedChangeProtocol` (approval gate for identity-critical) — never instantiated
- `DriftDetector.scan_recent` — never called → "anchor drift triggers auto-revert" is paper
- `GapDetector.scan_recent` — never called → capability gap detection doesn't work
- `ConsolidationPipeline.run_consolidation` — never called → semantic memory is static
- `SkillRegistry` — never instantiated → no skills are active
- `DriveCounters` — passed as `drives=None` everywhere → drives don't influence behavior
- `OpenRouterProvider` (~250 lines with retry/continuation) — never used; production uses ad-hoc httpx
- `AccountPool` (key rotation per CRUTCH-009) — never instantiated
- `ProviderRegistry` — never instantiated
- `embodiment/`, `simulation/`, `harness/hyper.py` — pure data-class stubs

If a doc claims any of these "is operational" — the doc is wrong.

## 8. What's missing entirely

- Channel abstraction (only Telegram, hardcoded)
- Self-modification tools accessible to Sonya from agent_session (`selfmod.propose`, `selfmod.apply`, etc.)
- Multi-step task runtime (no persistent task lifecycle)
- Initiative outbound — Sonya can't write first
- Web search / fetch / shell tools
- Voice / TTS
- Vision input
- Image generation
- RWKV / state tuning slots
- Embodiment event ingest
- Cross-channel principal linking
- Real consolidation trigger
- Drift action (detect + revert loop)

See `docs/SYSTEM_BUILDOUT_PLAN.md` for the prioritized buildout plan.

## 9. The agent surface

When InternalProcess hits its active interval (every 2 hours), it runs an agent session via `run_agent_session()` in `src/sonya/subject/agent_session.py`. The model writes ReAct-style steps:

```
[TOOL: tool_name arg]
```

Tools available:

- `self_inspect.identity / .state / .thoughts / .memories / .intentions / .code [path] / .modules`
- `filesystem.read [path] / .list [path] / .tree [path] / .write [path content]`
- `plugins.list / .create [name code] / .call [name args]`

To finish: `[DONE]` or `[DONE: summary]`. To pause: `[PAUSE: reason]`. Hard limits: 30 steps, 20 min.

Filesystem write is sandboxed: only `workspace/` and `src/sonya/tools/plugins/` are writable. Reads are wider but `.env`, `.git/*`, `tg.session`, `schema.sql`, `seed.py`, `SOUL.md` are forbidden.

## 10. Current bug/debt registry

`docs/KNOWN_ISSUES.md` has the full catalog with status:

- ✅ closed items have commit refs
- 🟡 deferred items have rationale
- 🔴 blocked items (C-1, C-2, C-3) — Ivan said skip for now

If you find a new bug, append it to KNOWN_ISSUES rather than creating a new file.

## 11. How to work on this repo

Read the rules: `docs/agents/AGENT_OPERATING_RULES.md`

Failure patterns to avoid: `docs/agents/AGENT_FAILURE_MODES.md`

Do not invent capabilities. If something isn't in §6 above, it doesn't run.

When implementing, prefer extending what exists (admin panel, agent_session tools, planner context) over adding new top-level subsystems. The system has too many half-built layers already.

## 12. Reading order

If you need full project context:

1. `docs/agents/AGENT_OPERATING_RULES.md`
2. `docs/agents/AGENT_FAILURE_MODES.md`
3. `docs/core/SONYA_SYSTEM_CORE.md`
4. `docs/core/INTERIM_CRUTCHES.md`
5. `docs/KNOWN_ISSUES.md`
6. `docs/SYSTEM_BUILDOUT_PLAN.md`
7. `docs/ROADMAP.md` (treat as aspirational; cross-check against KNOWN_ISSUES)
8. `docs/PROJECT_DOCUMENTATION_MAP.md` for the full tree
