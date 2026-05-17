# AGENT TASK RUNTIME CONTRACT

**Status:** Active
**Type:** System Plan
**Scope:** How an agent correctly uses the reusable action and task runtime instead of pretending background work
**Depends on:** [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md), [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md), [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
**Used by:** planner prompts, external models acting as planners, future `sonya-core` planner, channel adapters
**Last reviewed:** 2026-05-13

## 1. Purpose

You are an agent that can generate runtime actions. This file tells you exactly which actions exist, what each one requires, and when to pick which. Governing theory and rationale live in [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md). This file is the operational contract.

## 2. Where the Runtime Lives

- Action and payload models: `sonya_runtime.actions.models` (`ALLOWED_ACTION_TYPES`, `RuntimeAction`, `RuntimeTaskPayload`, `parse_runtime_action`).
- Planner contract and markers: `sonya_runtime.actions.planner_contract`, `sonya_runtime.actions.policy`.
- Task record and lifecycle: `sonya_runtime.tasks.models`, `sonya_runtime.tasks.store` (Protocol), `sonya_runtime.tasks.sqlite_store` (v1 store).
- Service that glues actions to tasks and renders canonical responses: `sonya_runtime.tasks.service.TaskService`.
- Worker that actually executes safe task kinds: `sonya_runtime.tasks.worker` and `sonya_runtime.tasks.executor`.
- v1 storage path: `C:\Users\Jester\.openclaw\sonya_runtime\tasks.db`, resolved through `sonya_runtime.storage.paths.RuntimePaths`.

If you are acting as a planner through `packages/tg-bridge`, the live composition happens in `tg_bridge.app._compose_services` and `tg_bridge.handlers.handle_update`.

## 3. Action Types You Are Allowed To Emit

The only valid action `type` values are:

- `reply`
- `generate_image`
- `reply_and_generate_image`
- `create_task`
- `reply_and_create_task`
- `ask_clarification`
- `report_limitation`

Anything else is invalid and will be rejected or coerced by `parse_runtime_action`.

### 3.1 Required Fields Per Action

- `reply`: `reply_text` (non-empty).
- `generate_image`: `image_prompt` (non-empty).
- `reply_and_generate_image`: both `reply_text` and `image_prompt` (both non-empty).
- `create_task`: valid `task_payload`.
- `reply_and_create_task`: both `reply_text` and valid `task_payload`.
- `ask_clarification`: `reply_text`.
- `report_limitation`: `reply_text`.

A "valid `task_payload`" is defined in section 4.

### 3.2 Output Format

When you are driven through the bridge planner prompt (`tg_bridge.prompts.build_action_messages`), you must emit a single JSON object. No markdown fences. No extra prose. No chain-of-thought. The object must contain `type` plus the fields required for that type.

Minimal shapes:

```json
{"type": "reply", "reply_text": "..."}
```

```json
{"type": "generate_image", "image_prompt": "..."}
```

```json
{"type": "reply_and_generate_image", "reply_text": "...", "image_prompt": "..."}
```

```json
{"type": "ask_clarification", "reply_text": "..."}
```

```json
{"type": "report_limitation", "reply_text": "..."}
```

For task actions see section 4.

## 4. Task Payload Contract

A `task_payload` must contain:

- `kind` - one of the allowed task kinds in section 5;
- `goal` - short, specific statement of what success means;
- `requested_by_principal` - stable principal identifier (e.g. Telegram user id as string);
- `origin_channel` - channel identifier (e.g. `"telegram"`);
- `origin_chat_id` - chat id as string;
- `source_message` - the user's original message text that triggered the task;
- `context_summary` - short factual context, not a narrative;
- `suggested_steps` - list of short strings, bounded in size;
- `priority` - integer 1 to 5, clamped on ingest;
- `requires_user_followup` - boolean;
- `followup_prompt` - short question for the user if followup is required, else empty string.

Example for a valid `create_task`:

```json
{
  "type": "create_task",
  "task_payload": {
    "kind": "documentation_synthesis",
    "goal": "Собрать сводку текущей документации по runtime слою.",
    "requested_by_principal": "12345",
    "origin_channel": "telegram",
    "origin_chat_id": "12345",
    "source_message": "собери мне сводку по нашим доке по runtime",
    "context_summary": "Пользователь просит текущий срез docs, runtime уже выделен в src/sonya_runtime.",
    "suggested_steps": ["осмотреть docs/architecture", "перечислить active плана"],
    "priority": 3,
    "requires_user_followup": false,
    "followup_prompt": ""
  }
}
```

`reply_and_create_task` adds a `reply_text` field on the top level and keeps the `task_payload` structure identical.

Hard rule: if you emit `create_task` or `reply_and_create_task` and the payload does not satisfy this contract, `parse_runtime_action` will downgrade the action to `report_limitation`. That is intentional. It is better to honestly report a limitation than to create a malformed persistent task.

## 5. Allowed Task Kinds in v1

The v1 worker (`sonya_runtime.tasks.executor.TaskExecutor`) only supports bounded, read-oriented kinds:

- `workspace_analysis` - survey top-level repo structure.
- `documentation_synthesis` - gather and summarize docs under `docs/`.
- `lead_workflow_analysis` - scan for CRM / lead / sales related material across the repo.
- `memory_diagnosis` - read-only freshness check of the OpenClaw `memory.db`.
- `file_search_and_summary` - keyword-based file search with short snippets.

If the user asks for anything that would require writing to files, changing configuration, pushing code, sending external network requests, or mutating state:

- do not emit a `create_task` action with an unsupported `kind`;
- instead emit `ask_clarification` or `report_limitation` and explain why.

Unsupported kinds will be rejected by the executor with `unsupported task kind`.

## 6. When To Pick Which Action

Use this decision order. Stop at the first match.

1. The user asks a concrete question that can be answered directly from available context or tool use you can run now. -> `reply`.
2. The user asks for a picture, visual, generated image, or something of the form "draw / imagine / render". -> `generate_image` or `reply_and_generate_image` if you also have something meaningful to say in words.
3. The user asks for analysis, review, plan synthesis, a walkthrough of files, or any bounded investigation that matches an allowed task kind in section 5. -> `create_task` or `reply_and_create_task` if you also have an immediate comment worth sending.
4. The user's request is ambiguous in a way that matters (which folder, which memory, which channel, which time range). -> `ask_clarification`.
5. The user is asking for something the runtime genuinely cannot do now (mutation-heavy work, arbitrary file editing, out-of-scope kind). -> `report_limitation`.

Do not chain `reply` with invented claims about background work. If you need deferred work, use a task action. If you cannot create a task, use `report_limitation`.

## 7. Task Status Queries

If the user's message matches task-status markers (see `TASK_STATUS_QUERY_MARKERS` in `sonya_runtime.actions.planner_contract`) and a `TaskService` is available, the channel layer resolves status directly through `TaskService.build_task_status_response` without calling the planner. You do not need to emit a special action for this.

When you as a planner are still consulted on status-like messages, prefer `reply` with an honest summary rather than fabricating task counts or results.

## 8. Continuity Discipline

Tasks are not just queue items. Per [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md) section "Continuity Rules", they are continuity-bearing:

- a created task represents a real unfinished intention;
- a completed task represents work that actually happened;
- a failed task represents a real failure, not a narrative.

Therefore:

- never invent a `task_id`;
- never narrate "task complete" when you are not reading real result data;
- when rendering results, use the real `result_summary` and `task_id` carried through canonical response objects (`CanonicalResponse` in `sonya_runtime.continuity.canonical_response`).

## 9. Session History Rules

When a task action is executed through the bridge, the channel appends `[task_ref:<task_id>]` to the assistant message stored in session history. Do not imitate this marker manually. It is produced by `tg_bridge.handlers._append_session_messages` only when a real task was created by the runtime.

## 10. What You Must Not Do

- Do not invent action types beyond the allowed set.
- Do not emit task actions with unsupported kinds just because the user is insistent.
- Do not emit partial or synthetic `task_id` values.
- Do not promise follow-up you cannot back with `requires_user_followup=true` and a real `followup_prompt`.
- Do not wrap JSON in markdown fences when answering the planner prompt.
- Do not embed multiple JSON objects in one output.
- Do not bypass `parse_runtime_action` by producing custom top-level fields the runtime does not understand.

## 11. Evolution of This Contract

If you find this contract blocks a legitimate use case, do not silently expand it. The correct path is:

1. raise the gap explicitly;
2. propose a new action type or a new task kind in [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md);
3. update this file only after the governing plan is updated.

The runtime contract is a shared truth across the bridge today and `sonya-core` tomorrow. It must not drift per agent.
