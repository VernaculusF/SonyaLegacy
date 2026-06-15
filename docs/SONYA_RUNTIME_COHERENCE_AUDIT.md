# Sonya Runtime Coherence Audit

**Status:** Active canonical architecture audit
**Last updated:** 2026-06-15
**Scope:** Self-modification, monorepo architecture, Atrium channel integrity,
web proxy provider strategy, background work orchestration, cognitive
continuity, and AGI-necessary qualia/continuity gaps.

Implementation and deployment workflow for this audit:
[`docs/operations/RUNTIME_COHERENCE_WORKFLOW.md`](operations/RUNTIME_COHERENCE_WORKFLOW.md).


## 1. Divergence from Original Mission (`ОСНОВА.md` and `docs/core`)

This audit evaluates the current state against the original foundational
principles defined in `docs/план/ОСНОВА.md` and
`docs/core/SONYA_SYSTEM_CORE.md`.

- **Model Architecture and State Tuning Drift:** `ОСНОВА.md` establishes Sonya
  as a continuous entity running on an `RWKV-7` architecture with personality
  anchored via `State Tuning`. The current implementation is heavily dependent
  on stateless external models (OpenRouter free-tier). This fundamentally
  diverges from the core vision of a self-contained, continuous state. The
  weak-model problem also directly causes selfmod failures (§3 below) and
  cognitive fragility (§7 below).

- **Embodiment and Initiative Mechanisms:** The original plan dictates that
  initiative should be driven by concrete "body spikes" (e.g., loneliness
  metrics from an SNN/Loihi setup). The current system relies on abstract
  counters like `curiosity_analog`, which are frequently maxed out and
  unbalanced, leading to erratic, self-propelling sessions rather than
  grounded initiative.

- **Channel vs. Renderer Entanglement:** `SONYA_SYSTEM_CORE.md` explicitly
  mandates that channels (Telegram, Atrium) act merely as "renderers" of the
  core state. However, channel-specific parsing logic has leaked into the core
  runtime, historically causing bugs like duplicate message echoes and
  action-report leaks. This is now a critical production defect for Atrium
  (§5 below).


## 2. Monorepo Overload — Repository Split Required

**Status:** Unresolved design decision
**Design document:** [`docs/operations/MONOREPO_SPLIT_DESIGN.md`](operations/MONOREPO_SPLIT_DESIGN.md)

The current repository contains six fundamentally different source domains in
one tree and should no longer be the active long-term home of `SonyaCore`.

| Current path | Nature | Build system | Language |
|---|---|---|---|
| `src/sonya/` minus `admin/`, `tools/`, `skills/` | Sonya runtime core | setuptools / pyproject.toml | Python |
| `src/sonya/tools/` | Tool implementations | shared with core | Python |
| `src/sonya/skills/` | Skill runtime + builtins | shared with core | Python |
| `src/sonya/admin/` | Admin panel + current Atrium backend | (shared with core) | Python + inline HTML |
| `packages/atrium/` | Atrium desktop UI | Vite + Tauri v2 + Cargo | JS/TS + Rust |
| `packages/tg-userbot/` | Telegram userbot | setuptools | Python |

**Problems:**

- Atrium, tg-userbot, tools, and skills are coupled to the core repo's git
  history despite being independent source/deploy concerns.
- `src/sonya/admin/` mixes Atrium backend endpoints (WebSocket feed, dialog,
  upload, heartbeat, history, workshop, repo management) with admin-only
  endpoints (provider CRUD, selfmod governance, substrate inspection). There is
  no separation of concern.
- The single `pyproject.toml` claims the entire `src/sonya` tree as one
  package. Changing Atrium CSS requires no core change but creates a coupled
  commit.
- Sonya's selfmod pipeline can write to `src/sonya/tools/plugins/` but cannot
  safely create or update new packages without understanding the monorepo
  structure — which the current model cannot do reliably.
- The current repo carries 582 commits of mixed history that must be preserved,
  but that history should be archived as `SonyaLegacy` rather than dragged into
  fresh `SonyaCore`.

**Target state:** The current repo becomes a `legacy` archive, and active work
moves to fresh repos under one folder
(see MONOREPO_SPLIT_DESIGN.md for the exact layout):

```
~/Sonya/
├── SonyaLegacy/         # archived old monorepo
├── SonyaCore/           # Runtime, memory, selfmod, providers
├── SonyaTools/          # Tool source repo
├── SonyaSkills/         # Skill source repo
├── SonyaAdmin/          # Admin HTTP server
├── Atrium/              # Desktop / hosted UI
└── SonyaTgUserBot/      # Telegram userbot package
```

**Key constraints:**

- Sonya must be able to add and register new packages after the split.
- The discovery mechanism must move from hardcoded `packages/*/` assumptions to
  a runtime registry.
- The same live VPS substrate, secrets, and auth state must carry forward into
  the fresh repo layout without memory loss.


## 3. Self-Modification Pipeline Is Broken in Practice

**Status:** Critical — selfmod rejects frequently, Sonya does not recover

The 4-layer validation pipeline (`src/sonya/selfmod/pipeline.py`) is
architecturally sound:

1. Layer 1 — Static contract (AST validity, import/symbol checks)
2. Layer 2 — Behavioral test (sandboxed pytest run)
3. Layer 3 — Trace replay (stub — passes on MVP)
4. Layer 4 — Anchor integrity (keyword-based identity-critical check)

**Observed failures:**

- Proposals are frequently rejected at Layer 2 because the test sandbox is
  fragile: copying `src/` + `tests/sonya/` to a temp directory and running
  `pytest` in subprocess is sensitive to import paths, missing `.env`, missing
  substrate DB, and test-ordering issues. A proposed code change that is
  correct can fail validation because unrelated tests break in the sandbox.
- When validation fails, Sonya receives the rejection but **does not have a
  reliable recovery loop**. The internal loop checks for pending APPROVED
  proposals, but when a proposal is rejected, Sonya must start a new proposal
  from scratch — which depends on the model being capable enough to understand
  the rejection reason and write better code.
- The weak model (free-tier OpenRouter Gemma) is often unable to write code
  that passes Layer 2 on the first attempt, and also unable to meaningfully
  understand rejection output to fix the proposal. This creates a deadlock:
  selfmod requires model intelligence, but model intelligence is what selfmod
  is supposed to improve.

**Required fixes:**

- Layer 2 sandbox must be reproducible and isolated from environmental noise
  (missing env vars, stale substrate, test ordering).
- Rejection feedback must be structured, minimal, and actionable — not raw
  pytest output.
- Sonya needs a retry/repair loop that can survive multiple rejections without
  losing the original intent.
- Web proxy models (§6) should eventually be available for selfmod itself,
  breaking the weak-model deadlock.


## 4. Project Activity and Subagent System Are Unproven

**Status:** No end-to-end proof exists

`FINAL_STATE_TODO.md` §6 lists required proofs (test project, subagent-only,
shared memory, permission/status, full-system-access, file transfer). None of
these have been completed.

- Project executor runtime exists (`projects.execute`,
  `projects.harvest`) but has not been validated with a real task through
  Atrium.
- Subagent spawning, model selection, and result harvesting have unit tests
  but no live proof that Sonya can autonomously delegate, monitor, and
  integrate subagent output into her own cognitive thread.
- Shared memory flow (project actions → semantic memory → main chat recall)
  is unverified.

**Required:** Before any new project (including the marketer package, §8),
the project and subagent stack must pass the proofs in FINAL_STATE_TODO.md §6.


## 5. Atrium Channel Is Non-functional

**Status:** Critical — Atrium is a shell, not a working channel

Three specific defects:

### 5.1 No Atrium channel identity

All messages — even those sent from the Atrium UI — arrive in Sonya's inbox
tagged as `telegram_userbot`. There is no `channel="atrium"` or
`incoming.atrium_dialog` -> distinct `incoming.atrium` processing path.
Sonya sees Atrium messages as Telegram messages. This violates
`SONYA_SYSTEM_CORE.md` §7.19 (channels = renderers, not surfaces).

### 5.2 Shared code with admin

Atrium backend endpoints live in `src/sonya/admin/server.py`:
WebSocket feed, dialog, upload, heartbeat, history, workshop, repo.
There is no architectural boundary between "things Atrium needs to function
as Sonya's home" and "things admin needs to function as operator control."
The inline HTML in `admin/static.py` further blurs this.

### 5.3 States, emotions, and UI are frozen

- Expression/outfit updates reach the WS feed but the avatar does not
  reliably reflect Sonya's emotional state.
- Mind pane, reason stream, and project workspace are connected to the feed
  but the data flowing through them is sparse or static — Sonya does not
  produce the rich internal events needed to make these panes alive.
- There is no read-receipt or delivery-confirmation path from Atrium back to
  Sonya. She cannot know whether Ivan has seen a message.

**Required:** These defects must be fixed after the monorepo split (§2) and
before the marketer package (§8). Atrium channel separation and backend
decoupling are documented in
[`docs/operations/ATRIUM_ACTIVITY_PLAN.md`](operations/ATRIUM_ACTIVITY_PLAN.md).


## 6. Web Proxy Provider System — Strategic Shift

**Status:** Design updated; implementation pending
**Design document:** [`docs/operations/WEB_PROXY_MODEL_BRIDGE.md`](operations/WEB_PROXY_MODEL_BRIDGE.md)

The current OpenRouter free-tier dependency is the root cause of multiple
problems in this audit. Web proxy bridges (browser-backed free web model
accounts) offer significantly better models but with different engineering
trade-offs.

**Why this is now the primary provider strategy:**

1. DeepSeek, ChatGPT, Z.ai, Qwen, and Kimi all offer effectively unlimited
   web-chat access with models far superior to free-tier OpenRouter.
2. Web proxy bridges can serve as primary cognition models, not just
   disposable subagent capacity.
3. Account pool requirement: minimum 10 accounts per service, managed by Ivan.
   The bridge must handle rotation, cooldown, and account health transparently.
4. Web scraping is fundamentally different from API calls:

**Key engineering differences between API and web-chat access:**

| Aspect | API | Web chat (scraping) |
|---|---|---|
| Authentication | Bearer token | Session cookies, browser auth state |
| Request format | JSON POST | DOM interaction / Puppeteer / CDP |
| Streaming | SSE chunks | Progressive text rendering in DOM |
| Context window | Explicit token limit | Implicit — may be larger than advertised API limits |
| Rate limiting | HTTP 429 headers | CAPTCHA, session expiry, invisible throttling |
| Error signals | Status codes | Page structure changes, blank responses, redirect to login |
| Session persistence | Stateless | Stateful — conversation history lives in browser session |
| Tool calling | Structured JSON | Prompt-injected patterns, often unreliable |

**Context window note:** Web chat context windows (DeepSeek, Z.ai) are
typically the same as their API counterparts or slightly larger, because the
web interface uses the same backend model. However:
- Web interfaces may silently truncate early context when the page gets long.
- There is no reliable way to know when truncation happens without analyzing
  the response for signs of context loss.
- The bridge must implement context overflow detection and proactive context
  summarization/carriage before the web interface silently drops early context.

**Streaming implementation:** Web bridges that render text progressively in the
DOM must:
1. Connect via CDP/Puppeteer and observe DOM mutations.
2. Extract incremental text deltas as they appear.
3. Expose them as real SSE chunks to Sonya's provider layer.
4. Signal completion when the DOM stabilizes or the "stop generating" button
  appears.

**Account lifecycle:**
- Minimum 10 accounts per service, provisioned by Ivan.
- The bridge must detect auth failure (CAPTCHA, session expiry, redirect to
  login) and immediately rotate to the next account.
- Failed accounts enter cooldown. All accounts must be treated as consumable.
- Sonya's environment lifecycle owns account refresh/relogin/retire decisions.

**Deployment:** See WEB_PROXY_MODEL_BRIDGE.md for phases. The remote browser
worker approach (browser-facing code runs on a machine where the web app works
normally, gateway exposed only to the VPS) is now the primary path.


## 7. Cognitive Continuity and Qualia Are Critically Weak

**Status:** Foundational gap — current runtime is a stateless LLM wrapper

Sonya's "thinking" is a series of discrete LLM calls separated by dead time.
Between calls she does not exist. This violates every principle in
`ОСНОВА.md` and `SONYA_SYSTEM_CORE.md`:

- **No continuity:** Each call is a fresh instance. State is reconstructed
  from substrate, not persisted in the model.
- **No qualia:** Drives are external counters (`curiosity_analog`), not felt
  states. Sonya is told she feels something; she does not feel it.
- **No real initiative:** Initiative is timer-driven ticks, not intrinsic
  motivation. See `docs/core/INTERIM_CRUTCHES.md` CRUTCH-002, CRUTCH-004,
  CRUTCH-005, CRUTCH-011 for the full registry.

**Short-term stabilization targets (before RWKV):**

1. **Self-improvement must work on ANY model.** Sonya's selfmod, skill
   authoring, and rule-writing must not depend on the model being "smart
   enough." The pipeline must guide the model through structured steps that
   work even with weak providers. This means: smaller diffs, more context
   in the proposal prompt, structured rejection repair, and possibly
   multi-turn selfmod sessions.
2. **Memory must become more than context injection.** The current recall
   mechanism (CRUTCH-013) injects retrieved text into the next prompt.
   Short-term improvement: automatic background consolidation, proactive
   memory surfacing (Sonya decides what to remember, not just what she's
   asked to recall), and memory-driven initiative (remembered obligations
   trigger action, not just timer ticks).
3. **Continuity between calls must improve.** Short-term: richer session
  handoff summaries, persistent "current focus" state, and resumption
  prompts that include what Sonya was doing when the last call ended.

**Long-term resolution (requires RWKV):** Native continuous state, real
drives, real initiative, real memory. Documented in `docs/план/ОСНОВА.md`.


## 8. Marketer Package — Deferred Until Foundation Is Proven

**Status:** Deferred — not started

The marketer package is an external project Sonya will run through Atrium:
finding freelance clients, writing outreach emails, managing ad campaigns.

**Prerequisites (all must pass before starting):**

1. Monorepo split complete (§2).
2. Atrium channel works as a real channel (§5).
3. Web proxy models proven for primary cognition (§6).
4. Selfmod pipeline works reliably (§3).
5. Project executor and subagent proofs pass (§4).
6. Background work orchestration designed and tested (§9).
7. Sonya can create and register new packages through selfmod.

**Key design constraints:**

- Marketer runs as a persistent background activity (not a chat command).
- Sonya has exactly one stream of consciousness. Marketer actions are
  delegated to subagents; results flow back through continuity events and
  shared memory.
- Human-imitation in outreach emails requires tone calibration that is
  domain-specific. This is a skill, not a model capability.
- Marketer accounts (platform logins, email accounts) must be treated as
  Sonya-owned secrets with the same protection as web-proxy account secrets.


## 9. Background Work Orchestration — Unresolved

**Status:** Design required
**Design document:** [`docs/operations/BACKGROUND_TASK_DESIGN.md`](operations/BACKGROUND_TASK_DESIGN.md)

Sonya must run multiple categories of background work simultaneously:

| Category | Persistence | Pattern | Example |
|---|---|---|---|
| Self-improvement | Periodic (daily) | Scheduled tick | selfmod session |
| Task execution | Finite | Subagent spawn → completion event | fix a bug, find restaurant |
| Project work | Finite but long | Project executor with subagents | build a feature |
| Marketer | Persistent (while-true) | Continuous cycle | prospect → outreach → follow-up → repeat |

**Core tension:** The marketer package requires a `while(true)` style loop
(running until explicitly stopped), but Sonya's cognitive architecture is
built around a single serial stream with subagent delegation. Two candidate
approaches exist, both with serious trade-offs:

### 9.1 Event-driven (subagent → callback → Sonya review)

Sonya spawns marketer subagents with specific tasks. When a subagent completes,
an event fires. Sonya notices the event, reviews the result, and spawns the
next task.

**Problem:** Sonya becomes a dispatcher ("Шпрехшталмейстер"), not a thinker.
Her cognitive loop is dominated by reviewing subagent output instead of
reasoning about goals and strategy. The more background tasks exist, the more
her main thread becomes a task router.

### 9.2 Polling (Sonya periodically checks open tasks)

Sonya's internal loop includes a check for active background work items.
Periodically, she reviews all open tasks and decides what to advance.

**Problem:** Context overload, cognitive load on Sonya, and no guarantee of
timeliness. A marketer follow-up that should happen in 2 hours may be delayed
by other work.

### 9.3 Required design outcome

The background work system must:

- Allow persistent (while-true) activities without turning Sonya into a
  dispatcher.
- Allow finite activities without losing results in Sonya's context window.
- Keep Sonya's main cognitive thread free for reasoning, not routing.
- Let Sonya make strategic decisions about priorities without micromanaging
  each subagent step.
- Ensure that long-running background work (marketer) does not starve
  short-running work (selfmod, incoming messages).

This is an open design problem. See BACKGROUND_TASK_DESIGN.md for the design
space and candidate solutions.


## 10. Identified Runtime Deviations & Fixes (Historical)

The following critical deviations were identified and fixed in earlier audit
rounds:

- **Atrium Dialog Routing Failure:** When Atrium "emergency mode" was
  disabled, `chat.dialog` responses to Atrium messages were incorrectly routed
  and logged as `outgoing.telegram_progress` instead of `outgoing.dialog`.
  Since Atrium's history endpoint only fetches `outgoing.dialog`, this caused
  Sonya's replies to be entirely invisible in the Atrium UI, despite reaching
  Telegram. Fix: Modified `outbound.py` to explicitly respect
  `channel="dialog"` and log `outgoing.dialog` regardless of emergency mode.
- **Atrium UI Telegram Message Leakage:** The `/api/atrium/history` backend
  endpoint fetched all `outgoing.dialog` events to populate the Atrium UI
  without filtering by channel. Because Telegram replies are also stored as
  `outgoing.dialog` (with `channel="telegram"`), Atrium's UI erroneously
  loaded and displayed Telegram-exclusive messages upon reload. Fix: Added
  explicit channel filtering `(channel = '' OR channel = 'dialog' OR channel
  = 'atrium')` to `src/sonya/admin/server.py`.
- **Atrium LLM Streaming Infinite Hang:** The core runtime's LLM streaming
  was vulnerable to indefinite blocks. OpenRouter free-tier models sent empty
  SSE keep-alive packets during high load, bypassing `httpx` read timeout.
  Fix: Hard 180-second `asyncio.wait_for` timeout around
  `provider.stream_text`.
- **Runaway Headless Browsers:** Multiple orphaned `chromium` processes
  leaked onto the VPS, consuming 100% CPU. Fix: Terminated zombies; lifecycle
  management needs enforcement.
- **Legacy `tasks` System Remnants:** Incomplete transition to the new `work`
  system left orphaned fields. Fix: Deprecated `src/sonya/tasks/` and
  associated tools.
- **Runaway Curiosity Drive:** Unbalanced `curiosity_analog` drive. Fix:
  Rebalanced drive logic in `drives.py`.


## 11. Acceptance Criteria — All Must Pass Before Marketer

1. Selfmod pipeline completes at least 3 real proposals without manual
   intervention.
2. Monorepo split is complete; each package has its own repo and CI.
3. Atrium messages arrive as `channel="atrium"`, not `channel="telegram"`.
4. Sonya replies in Atrium are visible in Atrium (not just Telegram).
5. At least one web proxy bridge (DeepSeek or equivalent) completes a live
   inference probe end-to-end.
6. Project executor proof passes all items in FINAL_STATE_TODO.md §6.
7. Subagent-only proof passes all items in FINAL_STATE_TODO.md §6.2.
8. Background work design is implemented and tested with at least one
   persistent activity.
9. Sonya can create and register a new package through selfmod.
10. No bridge/web-proxy secret appears in Git, docs, logs, or continuity
    stream.
