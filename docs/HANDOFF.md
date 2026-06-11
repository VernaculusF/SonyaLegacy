# HANDOFF.md — current continuation point

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-12

## Deployed Baseline

- Branch: `develop`
- Latest pushed/deployed runtime baseline before this documentation slice:
  `aa2753a`
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

Atrium is the main work/chat surface, not the admin surface. Telegram is
Sonya's social/emergency channel and must not be mirrored into Atrium chat as
ordinary dialog history. Telegram events may remain visible in explicit debug
surfaces.

## Latest Deployed Slice

Atrium reason-stream, expression stability, and dialog-spam guard:

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
