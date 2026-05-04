# CHANNELS AND TELEGRAM PLAN

**Status:** Active
**Type:** System Plan
**Scope:** Governing plan for Telegram/Userbot integration, channel contracts, principal resolution, and channel-to-action flow
**Depends on:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md), [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md), [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
**Used by:** Telegram bridge work, future channel implementations, principal resolution, runtime orchestration
**Last reviewed:** 2026-05-02

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

## Minimum Runtime Actions

The first stable action set should be:

- `reply_text`
- `analyze_vision`
- `generate_image`
- `reply_and_generate_image`
- `ask_clarification`

Telegram must be able to execute the result of these actions, but should not be the place where they are semantically invented.

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

