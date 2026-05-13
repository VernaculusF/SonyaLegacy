# TASK AND ACTION RUNTIME PLAN

**Status:** Active
**Type:** System Plan
**Scope:** Reusable runtime action contract, task lifecycle, planner and executor boundary, and anti-fake-agency policy
**Depends on:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md), [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
**Used by:** `tg-bridge`, future `sonya-core`, future schedulers, future workers, capability runtime, continuity implementation
**Last reviewed:** 2026-05-08

## 1. Purpose

This document fixes the first reusable runtime layer for actions and deferred work.

It exists to solve a concrete problem:

- Sonya must not fake background work;
- channels must not become fake autonomous minds;
- delayed work must have a real runtime representation;
- planner output must be reusable outside Telegram.

## 2. Core Rule

There is a strict difference between:

- conversational text;
- runtime action selection;
- actual execution.

Sonya is not allowed to claim:

- "I'm checking files now";
- "I created the document";
- "I'll come back in 15 minutes";
- "I'm working in the background";

unless the runtime has actually created or executed the corresponding action.

## 3. Architectural Position

This layer sits between:

- subject/continuity state;
- planner output;
- capability execution;
- channel rendering.

It is not Telegram-specific.

Telegram is only the first live ingress and egress surface for it.

## 4. Runtime Action Contract

The minimum action set is:

- `reply`
- `generate_image`
- `reply_and_generate_image`
- `create_task`
- `reply_and_create_task`
- `ask_clarification`
- `report_limitation`

Rules:

- `reply` carries `reply_text`
- `generate_image` carries `image_prompt`
- `reply_and_generate_image` carries both
- `create_task` carries `task_payload`
- `reply_and_create_task` carries `reply_text` and `task_payload`
- `ask_clarification` carries `reply_text`
- `report_limitation` carries `reply_text`

## 5. Task Payload Contract

The minimum task payload is:

- `kind`
- `goal`
- `requested_by_principal`
- `origin_channel`
- `origin_chat_id`
- `source_message`
- `context_summary`
- `suggested_steps`
- `priority`
- `requires_user_followup`
- `followup_prompt`

This payload must stay reusable across channels.

## 6. Task Record Contract

The persistent runtime task record contains:

- `task_id`
- `kind`
- `goal`
- `context_summary`
- `source_message`
- `status`
- `priority`
- `created_at`
- `updated_at`
- `requested_by_principal`
- `origin_channel`
- `origin_chat_id`
- `result_summary`
- `result_payload`
- `error_text`
- `claimed_actions`
- `followup_required`
- `followup_prompt`

This is operational state, not memory.

It must not be stored inside `memory.db`.

## 7. Task Lifecycle

Minimum lifecycle:

1. planner selects `create_task` or `reply_and_create_task`
2. runtime validates the payload
3. task is persisted
4. channel returns a canonical `task_created` response
5. worker claims the task
6. worker executes the allowed safe handler
7. runtime marks `done` or `failed`
8. later follow-up can render `task_update` or `task_result`

Allowed v1 statuses:

- `pending`
- `running`
- `done`
- `failed`
- `cancelled`

## 8. Planner Boundary

Planner is allowed to:

- choose an action;
- ask for clarification;
- choose deferred work;
- synthesize task payload intent.

Planner is not allowed to:

- pretend the work already happened;
- bypass task persistence;
- bypass worker execution;
- mutate files directly through narrative text.

## 9. Executor Boundary

The v1 executor is a separate runtime component.

It may:

- claim tasks from the task store;
- run safe read-oriented analyses;
- write structured result payloads;
- mark tasks done or failed.

It may not:

- perform arbitrary repo mutation;
- self-authorize broad write access;
- silently edit user files because a planner asked nicely.

## 10. v1 Allowed Task Kinds

The first worker only supports bounded safe kinds:

- `workspace_analysis`
- `documentation_synthesis`
- `lead_workflow_analysis`
- `memory_diagnosis`
- `file_search_and_summary`

This is intentional.

Mutation-capable tasks require a later approval layer.

## 11. Persistence Rules

v1 task persistence uses a separate SQLite database.

For the current host mode, the default location is:

- `C:\Users\Jester\.openclaw\sonya_runtime\tasks.db`

The code must accept the path from outside so it can move to VPS later.

## 12. Continuity Rules

Tasks are not just queue items.

They are continuity-bearing runtime objects because they represent:

- unfinished intention;
- deferred agency;
- work promised to the user;
- cross-turn operational continuity.

So task creation, task progress, and task completion must be renderable as canonical continuity-relevant events.

## 13. Channel Rules

Channels may:

- create tasks through planner-selected actions;
- ask for current task status;
- render task results;
- preserve task references in session history.

Channels may not:

- keep private hidden task state that the runtime cannot see;
- simulate background work locally;
- act like their own worker runtime.

## 14. Anti-Fake-Agency Rules

These rules are mandatory:

- no fake file scanning claims;
- no fake delayed completion claims;
- no fake "I already made the file" claims;
- no fake "I'll return later" claims without a persisted task;
- no channel-local theater pretending to be execution.

If the runtime cannot do the work now and does not create a task, the model must respond with limitation or clarification.

## 15. Current v1 Reality

As of this review:

- reusable action models exist under `src/sonya_runtime/actions`
- reusable task models and SQLite store exist under `src/sonya_runtime/tasks`
- a worker entrypoint exists under `python -m sonya_runtime.tasks.worker`
- `tg-bridge` now uses the runtime task layer instead of faking background work
- task status queries can be answered from the runtime store

This is not full `sonya-core`.

It is the first reusable runtime slice that can survive extraction from Telegram.

## 16. What Comes Next

Next layers above this plan:

- move more planner logic out of `tg-bridge`
- add canonical response production in shared runtime code
- connect task lifecycle to a fuller continuity event model
- add principal-aware task policy
- add approval-gated mutation tasks
- add scheduler coordination beyond simple worker polling

## 17. Conclusion

This layer is the first serious step away from fake agent theater.

It makes deferred work:

- explicit;
- persistent;
- inspectable;
- reusable across channels;
- compatible with the future Sonya runtime.
