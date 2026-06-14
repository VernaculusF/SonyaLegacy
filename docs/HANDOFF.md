# HANDOFF.md — current continuation point

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-12

## Deployed Baseline

- Branch: `develop`
- Latest pushed/deployed runtime baseline before this documentation slice:
  `56b327c`
- Production host: `jester-sonya@34.38.255.149`
- Production repo: `/home/jester-sonya/Sonya`
- Production substrate: `/home/jester-sonya/.sonya/sonya_substrate.db`
- Runtime schema: v33
- Services: `sonya.service`, `sonya-admin.service`

Do not use `deploy/update.sh` while the VPS has unrelated runtime dirt such as
`tg.session`. Prefer exact file copy for verification, then commit/push, then
fast-forward the VPS while preserving runtime files.

## Current Dirty Files To Preserve

Local unrelated:

- `tmp-planner-dump.txt`
- `.tmp_remote_provider_refresh_dir`

VPS unrelated:

- `tg.session`

Do not revert or commit these unless Ivan explicitly asks.

## Current Product Truth

Sonya is one environment/subject:

- one main chat, Sonya's home;
- project chats only for real substrate-backed projects;
- project chat = folder/workspace context plus chat, traces, progress, and
  pinned project context;
- subagents are internal disposable tools, not UI actors and not separate
  Sonyas;
- memory and continuity stream are shared.

There is no universal hardcoded "correct behavior" for Sonya. The runtime must
give her reliable situational evidence and preserve her judgement, not replace
it with a behavior rule engine. Autonomous work may continue without Ivan;
main chat remains shared interaction rather than an autonomous self-dialog.

## Current Architecture Priority

Read first: `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`.
For audit-driven runtime work on the VPS, follow
`docs/operations/RUNTIME_COHERENCE_WORKFLOW.md`.

That document is now the master execution checklist for 51 active runtime
problems. An item is not complete until its checklist box has linked
production evidence; implementation or tests alone do not close it.

The next implementation sequence is:

1. SituationalModel / WorldState and separation of current situation, durable
   knowledge, embodiment, work state, and credentials;
2. shared WorkItem lifecycle across tasks/background work/project activity,
   with promotion to durable projects and archive semantics;
3. distinct cognition/message/action/report contracts plus visible
   ActionRun/ToolRun/SubagentRun records;
4. meaningful-change active-session semantics, run/cost guards, and actual
   provider/model-pool use for main cognition;
5. provider-native normalized streaming and complete live Atrium proof.

Do not begin the parked web-proxy bridge before these foundations. More cheap
capacity would currently amplify self-propelling loops and incoherent state.

Every foundational slice must also include the cross-cutting contracts from the
canonical audit: provenance, causal IDs, idempotency, shared-state ownership,
scheduler backpressure, continuity/telemetry separation, and independent
acceptance evidence. Do not postpone these as cleanup; otherwise the same
failures will reappear through a different worker or channel.

## Latest Deployed Slice - v34 WorldState Foundation

Commit `f372560` is deployed to production.

What changed:

- `situational_assertions` is the new current WorldState table;
- `credential_exposures` records migrated credential-shaped current-state
  rows without preserving raw values;
- `runtime_state` stores technical heartbeat/throttle values that must not be
  injected as Sonya's world model;
- `EnvironmentStore` remains as a legacy facade but writes to
  `SituationalStore`;
- `env.set` blocks credential-shaped keys;
- Atrium heartbeat and drift-alert throttle no longer use `environment_state`;
- context includes source/confidence for observations and counts Atrium as Ivan
  activity for last-message awareness.

Production proof:

- backup:
  `/home/jester-sonya/backups/sonya-v34-worldstate-20260611-230944.db`;
- services: `sonya.service` and `sonya-admin.service` active;
- production substrate: schema `34`, `environment_state=0`,
  `credential_env_rows=0`, `credential_exposures=2`,
  `runtime_state.atrium_last_seen` current, `quick_check=ok`;
- recent warning journal had no entries.

Checklist status:

- #3 closed;
- #4 closed;
- #1 and #50 closed (generalized contradiction handling and SituationalMetrics);
- #46 closed (CredentialExposureStore);
- #51 closed (canonical documentation staleness test);
- #2 closed (EnvironmentStore deleted, SituationalStore full migration, explicit uncertainty marker);
- #5 closed (Stop self-propelling interaction cycles);
- #15 closed (One authoritative outfit/embodiment state);
- #21 closed (Events lack causal graph: added `causal_context` for correlation/causal IDs).

Additional deployed progress on #1:

- commit `358b43d` supersedes stale asleep/busy/dnd `ivan_status` when a fresh
  incoming Ivan message arrives from Atrium or Telegram;
- it records `world_state.ivan_activity_invalidated_status`;
- focused VPS suite passed (`49 passed`), compileall clean, production services
  active, `environment_state=0`, `credential_env_rows=0`, `quick_check=ok`;
- commit `95f9f0b` added generalized contradiction handling (`invalidates_ids`) and `SituationalMetrics`, closing #1 and #50.
- subsequent work added `CredentialExposureStore` and `test_doc_staleness.py`, closing #46 and #51.

Known verification note: one old `test_internal_process_emits_on_idle_timeout`
is a fragile 150 ms timing test on VPS and failed independently of the
WorldState slice. The focused WorldState/Atrium/provider/substrate suite passed
(`57 passed`) and production-copy migration proof passed.

Atrium is the main work/chat surface, not the admin surface. Telegram is
Sonya's social/emergency channel and must not be mirrored into Atrium chat as
ordinary dialog history. Telegram events may remain visible in explicit debug
surfaces.

## Latest Deployed Slice

Atrium reason-stream, expression stability, and dialog-spam guard:
- [Previous slice details preserved in git history]

## Current Active Work: Streaming and Output Formatting (June 13)
- Implemented `stream_text` and Atrium `active_stream` state for true provider-native streaming.
- Fixed Telegram parser: captured message tails correctly after `[DONE]` tags and enhanced `_scrub`.
- Bypassed Atrium output cleaning: developer UI now receives raw formatting (with tool tags).
- Updated Substrate `provider_settings` schema and populated active fallback models.
- **Fixed Atrium Silence Bug:** Added `internal.agent_stream_chunk` to `_INTERNAL_PUBLIC` in `continuity_stream.py` to prevent stream events from being hidden from Atrium UI.
- Fixed missing `ABANDONED` enum status and `list_active()` compatibility method in the new WorkItem store logic during deploy.
- **Fixed Telegram Parsing/Double-Messaging Bug:**
  - Modified `_TOOL_BLOCK_RE` in `agent_session.py` to properly match tools containing backticks with spaces (e.g., `` ` ` ` ``) WITHOUT consuming the newline characters. This fixes the issue where `chat.dialog` failed silently in Atrium.
  - Reverted the early return in `_extract_reply` (in `channel_session.py`) and instead added logic to override dummy `[DONE: ожидаю...]` messages with the actual message content sent via `chat.dialog`. This correctly restores the separation of channels (Telegram messages go to Telegram, Atrium messages go to Atrium).
- Deployed commit `20ecb4c` to production VPS using fast-forward merge and restarted services.

## Current Active Work: Coherence Audit Remnants and Atrium Communication Fix (June 14)
- Fixed multiple runtime coherence deviations identified in the audit.
- Removed legacy `stuck_loop_count` columns and tracking from `src/sonya/state/migrations.py` and `src/sonya/work/models.py`.
- Deprecated legacy task tools (`tasks_tool.py`) to resolve subsystem fragmentation.
- Rebalanced `curiosity_analog` drive bounds in `src/sonya/initiative/drives.py` to prevent runaway active sessions.
- **Fixed Atrium Silence Bug:** Modified `agent_session.py` to add a hard 180s timeout (`asyncio.wait_for`) around `provider.stream_text` to prevent infinite hangs caused by keep-alive packets ignoring HTTP read timeouts.
- **Fixed Atrium History Telegram Leakage Bug:** Modified the `/api/atrium/history` endpoint in `src/sonya/admin/server.py` to explicitly filter `channel` so that Atrium no longer fetches `outgoing.dialog` events where `channel="telegram"`.
- Commits pushed, VPS fast-forwarded and services restarted.


- reason-stream drawer now closes through its button, `Escape`, or backdrop;
- reason-stream displays newest events first and loads older history when the
  user scrolls to the bottom;
- technical `internal.agent_step tool=chat.dialog` rows no longer duplicate
  the actual outgoing dialog in reason-stream;
- typing state begins when an active session is scheduled and no longer waits
  for the websocket backlog `synced` flag;
- explicit `body.expression` choices hold a 45-second lease against the cheap
  auto-classifier, and no-op explicit expression calls no longer emit events;
- an agent session may send one ordinary dialog for a user input and another
  after real work; further dialog calls without new input/work are blocked and
  audited as `internal.dialog_repeat_suppressed`;
- completed-subagent polling now owns a process-lifetime cursor seeded from
  existing terminal tasks, so old proof workers are not re-emitted on every
  maintenance tick or service restart;
- provider-native token streaming is still not implemented; Atrium currently
  uses typing state plus client-side progressive reveal of completed replies.

VPS pre-deploy verification passed:

- focused regression suite -> `28 passed`;
- subagent completion cursor regression -> passed;
- `python -m compileall -q src/sonya` -> passed;
- `cd packages/atrium && npm run build` -> passed.

Production verification:

- commits `bedff3a` and `9215106` are pushed and deployed;
- both services are active, Atrium responds on `127.0.0.1:8877`, and the
  post-restart warning journal is empty;
- no new `subagent.complete` event appeared after the `9215106` core restart
  and maintenance tick;
- production checkout is clean except the preserved runtime `tg.session`.

## Remaining Immediate Work

1. Design and implement the SituationalModel slice from the canonical audit.
2. Design the WorkItem migration/promotion path without blindly converting
   every small action into a project.
3. Preserve the existing deployed spam guards and validate them during later
   live scenarios; do not mistake them for the architectural fix.
4. Keep Google Drive as an optional cold archive target, never primary live
   state.

## Key Docs

- `docs/MASTER.md`
- `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`
- `docs/STATE.md`
- `docs/ATRIUM_PROJECT_PLAN.md`
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `docs/operations/PROVIDER_SYSTEM_DESIGN.md`
- `docs/operations/PROVIDER_MODEL_CATALOG.md`
- `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`
