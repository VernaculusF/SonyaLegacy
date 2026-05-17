# CHANNELS AND TELEGRAM PLAN

**Status:** Stale (target architecture, not implemented)
**Type:** System Plan
**Scope:** Target architecture for channel layer. Most of this is aspirational. **Implementation guide is `docs/SYSTEM_BUILDOUT_PLAN.md` Etap B.**
**Depends on:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md), [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md), [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
**Used by:** future channel work
**Last reviewed:** 2026-05-16

---

## ⚠️ Reality check (2026-05-16)

This doc describes a channel abstraction that **does not exist in code**. Current state:

- Only Telegram works, hardcoded directly in `src/sonya/main.py` (`_start_userbot`, `_tg_handler`, `_on_incoming`)
- No `Channel` Protocol, no `ChannelRegistry`, no normalized event contract
- `packages/tg-bridge/` was removed entirely. `tg-userbot` is just a Telethon wrapper used inline from main.py
- The "Action Routing Rule" / "Task Flow" sections below depend on a task/action runtime that also doesn't exist

This file is preserved as **target shape**. When Etap B from `SYSTEM_BUILDOUT_PLAN.md` is executed, this doc becomes the spec. Until then, treat everything below as future direction, not current behavior.

The principles that ARE still valid for current code:
- Anti-fake-agency rules (do not narrate work that didn't happen)
- Principal resolution conceptually (Telegram sender_id → Principal)
- Authority boundary (replies vs side-effects)

---

## Purpose

This document fixes the long-lived rules for channel integration.

It exists so Telegram/Userbot does not remain a one-off transport hack and so future channels can follow the same contracts.

## Scope

This document governs:

- Telegram/Userbot as the first live channel;
- channel event contracts;
- principal resolution at channel ingress;
- channel-specific authority boundaries;
- channel-to-runtime action flow;
- how a channel may trigger text reply, vision, image generation, and future actions.

It does not define:

- full memory internals;
- global identity theory;
- skill evolution internals;
- research-stage embodiment or simulation details.

## Channel Role

The channel layer is not Sonya.

The channel layer is the boundary that:

- receives external input;
- normalizes raw transport data into internal events;
- resolves principal evidence;
- attaches channel metadata;
- routes the event into runtime action selection;
- emits results back outward.

Telegram/Userbot is the first production channel for this layer.

The governing rule from [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md) applies here directly:

- channels are surfaces of one subject;
- channels are not separate Sonya instances;
- TTS, Discord, and future renderers must consume the same canonical internal result rather than create parallel personalities.

## Telegram/Userbot Responsibilities

Telegram/Userbot is responsible for:

- receiving Telegram updates;
- downloading attached media;
- normalizing text, images, stickers, and video;
- resolving sender/chat evidence into channel principal candidates;
- passing structured input into runtime services;
- delivering outbound text and generated media;
- recording raw updates and operational logs.

Telegram/Userbot must not become:

- the place where Sonya's identity lives;
- the place where core memory logic lives;
- the place where capability policy is invented ad hoc;
- the place where one-off image-generation hacks accumulate.

## Channel Event Contract

Every channel event must normalize into a runtime-facing structure that can survive channel swaps.

Minimum fields:

- `channel`
- `channel_message_id`
- `channel_chat_id`
- `channel_sender_id`
- `principal_candidate_evidence`
- `input_mode`
- `text`
- `attachments`
- `received_at`
- `transport_metadata`

`input_mode` must support at least:

- `text`
- `vision`
- `image_generation`
- future internal action requests

## Principal Resolution Rules

Telegram identity is evidence, not identity itself.

The channel layer must:

- collect Telegram sender ID;
- collect chat ID;
- preserve channel type metadata;
- pass that evidence into principal resolution;
- never treat display name as authority evidence.

A Telegram account may map to:

- a trusted principal;
- an untrusted principal;
- an unknown principal candidate.

No trusted authority may be granted from label, tone, or apparent familiarity alone.

## Authority Boundary

Channel trust and anchor significance are not the same thing.

The Telegram layer may establish:

- who likely sent the message;
- whether the sender is allowlisted;
- what transport context exists.

The Telegram layer may not alone decide:

- anchor reassignment;
- identity-core mutation;
- harness-policy changes;
- privileged self-modification approval.

Those decisions must remain in higher runtime policy.

## Deferred Work Rule

Telegram is not allowed to simulate background work.

That means the channel must not present text like:

- "I'm checking the files now"
- "I'll come back in 15 minutes"
- "I already created the document"

unless the runtime actually created or executed the corresponding action.

The correct flow is:

- planner selects `create_task` or `reply_and_create_task`
- runtime persists the task
- worker executes the allowed safe handler
- channel later renders `task_update` or `task_result`

## Telegram Input Modes

Telegram/Userbot must support these live modes:

### Text

Plain text input routed to the main cognitive model.

### Vision

Triggered by attached images, stickers, image documents, and video.

The bridge must be able to pass:

- image attachments as image parts;
- video attachments as video parts when provider/model supports them.

### Image Generation

Triggered either by:

- explicit user request for an image;
- or future runtime action selection when Sonya decides an image should be produced.

Image generation must use the configured `imageModel`, not the main text/vision model.

## Current Telegram Rules

At the current stage:

- `model` is the main text and vision path;
- `imageModel` is the image generation path;
- `/img` may remain as a low-level fallback trigger;
- natural-language image requests must also be supported;
- video vision support must route through the same `vision` action path, not a separate side system.

## Action Routing Rule

The long-term contract must be:

`channel input -> normalized event -> principal resolution -> action selection -> capability execution -> outbound response`

This means Telegram must not own final decisions like:

- whether to answer with text only;
- whether to generate an image;
- whether to reply and generate;
- whether to ask a clarification question.

Those are runtime actions, not Telegram transport rules.

This also means Telegram must consume a canonical response object produced above the channel layer, not invent channel-local "versions" of Sonya.

## Runtime Actions

Telegram must be able to execute the current runtime action set, but must not be the place where any of those actions is invented or extended.

The canonical list of action types, their required fields, and their lifecycle live in [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md §4](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md). Do not restate them here.

## Task Flow

For deferred work, the Telegram channel must support:

1. user asks for analysis or delayed work
2. planner returns `create_task` or `reply_and_create_task`
3. runtime task store writes a real task record
4. Telegram confirms task creation
5. worker completes the task later
6. user asks for status or result
7. Telegram renders the runtime answer from task state

## Media Rules

The Telegram/Userbot path must preserve enough fidelity for provider calls.

Minimum support:

- photo
- sticker
- image document
- video
- video note
- future audio/voice path if adopted later

Every attachment must keep:

- local path
- mime type
- transport identifiers
- data-url or equivalent provider payload material

## Logging and Diagnostics

Telegram/Userbot must log:

- bridge start/stop;
- update failures;
- model call failures;
- attachment download failures;
- image-generation failures;
- raw updates;
- enough metadata to distinguish transport failure from model failure.

Operational logs must not be mistaken for model-generated narrative.

## Invariants

The Telegram layer is considered healthy only if all of these remain true:

- real bidirectional ingress/egress exists;
- principal evidence is preserved;
- image generation uses `imageModel`;
- vision uses the main configured model path;
- attachments are normalized without silent loss of type;
- channel logic remains separate from cognition core;
- no label-based authority leak exists.

## Done Criteria

This document is satisfied only when Telegram/Userbot can:

- receive text, image, sticker, and video input;
- route text and vision through the main model;
- route image generation through `imageModel`;
- preserve principal evidence correctly;
- support future runtime-driven image generation without rewriting the channel layer;
- remain a reusable adapter rather than a monolith.

