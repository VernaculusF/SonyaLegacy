# HANDOFF.md — current continuation point

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-12

## Deployed Baseline

- Branch: `develop`
- Latest pushed/deployed baseline before this slice: `c5c8839`
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

## Latest Implemented Slice In Progress

Atrium UI cleanup after hosted-stack proof:

- `inner stream` / reason logs moved out of the main layout into a top-bar
  debug drawer;
- main right pane no longer renders raw inner thoughts or drive counters;
- global reason stream filters out project/subagent trace noise because those
  belong in the active project runtime panel;
- Atrium dialog history and live chat no longer mirror Telegram
  `incoming.telegram_message` / `outgoing.telegram_*` events into the main
  chat;
- assistant messages strip accidental outer quotes and prose-only empty fenced
  blocks;
- live assistant messages reveal text progressively and keep the typing row in
  view while `her_typing` is true.

VPS verification already passed for this uncommitted slice:

- `pytest -q tests/sonya/test_atrium_one_sonya_static.py
  tests/sonya/test_atrium_etap1.py::test_history_excludes_telegram_social_channel
  tests/sonya/test_atrium_etap1.py::test_history_initial_page_returns_newest_dialog_events
  tests/sonya/test_atrium_etap1.py::test_dialog_records_workspace_id_and_history_filters_by_it
  tests/sonya/test_atrium_etap1.py::test_events_history_returns_non_private_scrollback`
  -> `14 passed`;
- `python -m compileall -q src/sonya` -> passed;
- `cd packages/atrium && npm run build` -> passed.

This slice still needs commit, push, VPS fast-forward, service restart, and
post-restart status/journal check.

## Remaining Immediate Work

1. Finish/deploy the Atrium UI cleanup slice above.
2. Inspect real production `drive_state` and evolution pressure values:
   drive counters are internal initiative accumulators, not emotions; if they
   saturate unexpectedly, fix runtime normalization separately from UI.
3. Recheck live Atrium behavior after refresh:
   typing indicator, progressive reveal, Telegram/Atrium separation, and
   inner-stream drawer.
4. Continue provider/model evaluation automation and web-proxy model bridge
   only after Atrium chat UX is stable again.

## Key Docs

- `docs/MASTER.md`
- `docs/STATE.md`
- `docs/ATRIUM_PROJECT_PLAN.md`
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `docs/operations/PROVIDER_SYSTEM_DESIGN.md`
- `docs/operations/PROVIDER_MODEL_CATALOG.md`
- `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`
