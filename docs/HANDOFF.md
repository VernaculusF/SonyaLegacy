# HANDOFF.md — current continuation point

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-12

## Deployed Baseline

- Branch: `develop`
- Latest pushed/deployed baseline: `9215106`
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

Atrium is the main work/chat surface, not the admin surface. Telegram is
Sonya's social/emergency channel and must not be mirrored into Atrium chat as
ordinary dialog history. Telegram events may remain visible in explicit debug
surfaces.

## Latest Deployed Slice

Atrium reason-stream, expression stability, and dialog-spam guard:

- reason-stream drawer now closes through its button, `Escape`, or backdrop;
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

1. Inspect real production `drive_state` and evolution pressure values:
   drive counters are internal initiative accumulators, not emotions; if they
   saturate unexpectedly, fix runtime normalization separately from UI.
2. Recheck live Atrium behavior after refresh: close behavior, typing,
   progressive reveal, Telegram/Atrium separation, expression stability, and
   dialog suppression.
3. Continue provider/model evaluation automation and web-proxy model bridge
   only after Atrium chat UX is stable again.

## Key Docs

- `docs/MASTER.md`
- `docs/STATE.md`
- `docs/ATRIUM_PROJECT_PLAN.md`
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `docs/operations/PROVIDER_SYSTEM_DESIGN.md`
- `docs/operations/PROVIDER_MODEL_CATALOG.md`
- `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`
