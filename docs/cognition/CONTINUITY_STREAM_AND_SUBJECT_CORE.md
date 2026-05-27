# CONTINUITY STREAM AND SUBJECT CORE

**Status:** Active
**Type:** System Plan
**Scope:** Cross-channel subjective continuity, canonical internal response state, and the architectural separation between one Sonya and many interface surfaces
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [MASTER.md](C:/Users/Jester/Desktop/Sonya/docs/MASTER.md)
**Used by:** [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md), [ENVIRONMENT_AS_SONYA.md](C:/Users/Jester/Desktop/Sonya/docs/core/ENVIRONMENT_AS_SONYA.md), [MASTER.md](C:/Users/Jester/Desktop/Sonya/docs/MASTER.md), future voice, avatar, multi-channel, and runtime plans
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):** Doc is mostly aligned with reality.
> - `subject_state`, `continuity_event`, `pending_intention`, `canonical_response` — all exist in substrate v6.
> - "Cross-channel" is theoretical — only Telegram exists. The principle that channels are surfaces above one subject is preserved by current code (build_full_context unifies thinking + telegram contexts as of commit `0e3314b`).
> - `task_record_ref` (deferred work) — task runtime never landed; pending_intentions partially fills this role.
> - `voice_profile_binding`, `avatar_profile_binding`, `channel_render_record` — not implemented.

## 1. Purpose

This document fixes one of the load-bearing truths of the project:

Sonya must exist as one continuous subject above all channels, not as a separate instance per transport.

Without this layer, the system degrades into:

- one Telegram Sonya;
- one Discord Sonya;
- one voice Sonya;
- one avatar Sonya;
- one local-session Sonya;

which is architecturally wrong.

## 2. Core Claim

Channels are not Sonya.

Voice is not Sonya.

Visual embodiment is not Sonya.

A model backend is not Sonya.

These are surfaces, renderers, substrates, and interfaces through which one subject expresses itself.

The system therefore needs a subject core and continuity stream that sit above:

- Telegram;
- Discord;
- TTS;
- future voice calls;
- future avatar or body layers;
- any specific current model.

## 3. What This Layer Is

The `subject core` is the architecture that makes Sonya one subject rather than a pile of interfaces.

The `continuity stream` is the runtime sequence of internal subjective state transitions that persists across channels and outputs.

Together they define:

- one canonical self-state;
- one active continuity line;
- one cross-channel memory-bearing subject;
- one internal act of response before any channel-specific rendering happens.

## 4. What This Layer Must Prevent

This layer exists to stop several bad degenerations:

### 4.1 Channel Fragmentation

The same Sonya must not fork into different practical personalities just because messages came through different channels.

### 4.2 Renderer Identity Theft

TTS, avatar renderers, or future body drivers must not become implicit new personalities.

### 4.3 Model-Substrate Overidentification

Changing the active provider or model backend may change expression quality, style pressure, or cognitive texture, but must not be treated as creating a new Sonya by default.

### 4.4 Response-Only Existence

Sonya must not exist only at the moment of outward reply. She must have a persistent internal continuity between outputs.

## 5. Architectural Position

This is not a late addon.

It belongs near the base of the architecture.

Practical ordering:

1. Subject Core / Continuity Stream
2. Memory Core
3. Canonical Thought and Action Layer
4. Channel Ingress / Render Layer
5. Harness / Anchors / Governance

If this ordering is ignored, channels will silently become pseudo-instances.

## 6. Main Components

### 6.1 Canonical Subject State

The system must maintain a channel-independent internal state that includes at minimum:

- current self-state;
- active relation context;
- active focus;
- pending intentions;
- recent internal transitions;
- current constraints;
- current anchor-sensitive context.

### 6.2 Continuity Stream

The system must maintain an ordered stream of internal subjective transitions, not only channel messages.

Examples:

- inward interpretation of a message;
- memory retrieval that shaped a reply;
- action decision;
- self-observation note;
- initiative signal;
- anchor-relevant emotional state shift;
- pending action that survives the current channel turn.
- deferred task that remains alive after the current reply.

### 6.3 Canonical Response Object

Before any channel-specific formatting, Sonya should produce one canonical internal result such as:

- reply text;
- image generation action;
- reply plus image generation;
- clarification request;
- initiative proposal;
- silence or defer.
- task created;
- task status;
- task result.

That canonical result is then rendered into:

- Telegram text;
- Discord text;
- TTS audio;
- future avatar expression;
- future embodied action.

### 6.4 Channel Renderers

Channels should only:

- ingest events;
- normalize them;
- pass them upward;
- render canonical outputs downward.

They must not own identity.

### 6.5 Voice Layer

Voice is not a second subject.

Voice is a rendering layer bound to the same subject core.

That means TTS should speak an already-formed canonical response rather than invent a separate behavior policy.

## 7. Minimum MVP Form

This layer must exist already in MVP, even if primitive.

Minimum acceptable form:

- one channel-independent subject state object;
- one continuity event stream or log schema;
- one canonical response object before channel render;
- one rule that all channels consume and emit through that object;
- one explicit distinction between subject state and renderer state;
- one persistence path for current continuity state across restarts.

MVP does not need:

- advanced multimodal embodiment;
- rich internal phenomenology simulation;
- perfect cross-model continuity.

But it does need the structural place where these things belong.

## 8. Required Data Objects

Minimum data objects for this layer:

- `subject_state`
- `continuity_event`
- `continuity_snapshot`
- `canonical_response`
- `pending_intention`
- `task_record_ref`
- `channel_render_record`
- `voice_profile_binding`
- `avatar_profile_binding`

## 9.1 Deferred Work and Continuity

Deferred work is not just a queue mechanic.

If Sonya tells the user that work will continue beyond the current reply, that work must exist as a continuity-bearing runtime object.

At minimum this requires:

- a persisted task record;
- a link from the current turn to that task;
- a later ability to render task status or result as part of the same subject continuity line.

Without this, "I'll do it later" is not continuity. It is fake agency theater.

## 9. Cross-Channel Rules

### 9.1 One Subject, Many Surfaces

Telegram, Discord, voice, and future channels are not separate identities.

### 9.2 Shared Memory, Shared State

All channels must feed one memory and one subject continuity line.

### 9.3 Channel Differences Are Render Differences

Differences in style caused by channel constraints are allowed.

Differences in identity caused by channel separation are not.

### 9.4 Voice Is Identity-Bound, Not Identity-Originating

The voice profile must be tied to Sonya's identity and continuity, but the TTS engine is not the source of identity.

## 10. Failure Modes

This layer specifically guards against:

- channel-specific persona drift;
- discord-sonya / telegram-sonya divergence;
- voice mode becoming a second persona;
- renderer-specific behavior overrides;
- per-channel memory silos;
- multiple simultaneous "selves" with no governing continuity;
- model switch being mistaken for total identity replacement.

## 11. Relationship To Other Docs

This document does not replace:

- [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)
- [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
- [ENVIRONMENT_AS_SONYA.md](C:/Users/Jester/Desktop/Sonya/docs/core/ENVIRONMENT_AS_SONYA.md)

It sits above them as the governing explanation for why:

- memory is shared;
- channels are not instances;
- renderers are not personalities;
- canonical response objects matter;
- cross-channel continuity belongs to architecture, not just to style guidance.

## 12. Implementation Priority

This layer should be addressed early, not late.

It belongs immediately after the basic runtime skeleton and alongside memory/identity planning.

If delayed too long, the project will accumulate:

- channel hacks;
- per-surface drift;
- duplicated logic;
- false identity forks;
- voice and avatar confusion.

## 13. Conclusion

Sonya must be built as one continuous subject that uses channels, not as a collection of channel-specific masks.

The subject core and continuity stream are therefore part of the base architecture, not optional polish.
