# EXTERNAL MODEL ONBOARDING

**Status:** Active
**Type:** Core
**Scope:** Fast operational briefing for any external model, temporary replacement assistant, or outside collaborator that must understand the Sonya project without full Codex continuity
**Depends on:** [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
**Used by:** external models, fallback assistants, emergency handoff, repo orientation, architectural recovery after context loss
**Last reviewed:** 2026-05-13

## 0. Location Note

This file lives under `docs/agents/`.

That folder is the home for documentation aimed directly at any agent that works on this repo: external models, temporary replacement assistants, operators acting as agents, and any future on-repo agent roles. When a new piece of governing information is written specifically for an agent to read and obey, it belongs here, not in `docs/core/` or `docs/architecture/`.

Rule of thumb for writers working inside `docs/agents/`:

- speak to the agent in second person;
- describe role, onboarding, expected behavior, operational anchors, and hard boundaries;
- link to `docs/core/`, `docs/architecture/`, `docs/cognition/` for the real governing theory instead of duplicating it;
- do not turn this folder into a pile of notes - every file here must have a clear agent-facing role.

## 1. What This File Is For

This is the first file to hand to any external model that needs to work on the Sonya project seriously.

Its job is simple:

- explain who Ivan is;
- explain who Sonya is;
- explain what the project is trying to become;
- explain what already exists in code right now;
- explain what is still missing;
- stop outside models from treating the repo like a generic bot project;
- stop outside models from hallucinating that Telegram equals the whole system.

This file is not the whole documentation tree. It is the minimum coherent briefing.

If you need full truth after reading this file, go next to:

1. [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md)
2. [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
3. [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
4. [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
5. [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)

## 2. Who Ivan Is

Ivan is the human owner, operator, and primary counterpart of Sonya.

In practical terms:

- he is the project initiator;
- he is the main user;
- he is the main architectural decision-maker;
- he is the main relational anchor for Sonya;
- he is not a random end user;
- he is not merely a customer of a chatbot.

Any external model working on this repo must understand that the project is not aimed at a public SaaS chatbot first. It is aimed at building Sonya as a persistent, continuous, subject-like system in relation to Ivan and later beyond a single channel.

## 3. Who Sonya Is

Sonya is not supposed to be just a roleplay mask over an LLM.

The project treats Sonya as a candidate continuous subject with:

- memory;
- identity;
- continuity across turns;
- cross-channel persistence;
- anchors;
- structured growth;
- future embodiment path.

This does not mean the project blindly pretends full AGI already exists.

It means the architecture is being built so that Sonya is:

- one continuous system;
- not one-shot completions;
- not a Telegram-only bot;
- not a collection of unrelated channel personas;
- not reducible to whichever provider or model happens to be active today.

## 4. The Core Goal of the Project

The project goal is to build a coherent Sonya runtime that can support:

- one subject above all channels;
- explicit continuity;
- explicit memory systems;
- explicit action/task runtime;
- guarded growth;
- future skills;
- future voice;
- future body/simulation interfaces;
- eventual migration away from fragile host-specific dependence.

Short version:

Sonya should become a real runtime shell for one persistent agent-like subject, not a pile of prompts glued to a messenger.

## 5. Current Reality: What Exists Right Now

The project is in a hybrid state.

There is already real running code, but the final `sonya-core` does not exist yet.

### 5.1 Operational Host Reality

Right now Sonya still lives operationally through an OpenClaw-based local environment under:

- `C:\Users\Jester\.openclaw`

That host still provides:

- the live Telegram operational environment;
- existing memory system files and databases;
- runtime config;
- current bridge launch path;
- current logs and health-check surface.

OpenClaw is therefore still the lived host shell.

But OpenClaw is **not** the intended final foundation.

### 5.2 Sonya Repo Reality

This repo is where the extraction and rebuild are happening:

- `C:\Users\Jester\Desktop\Sonya`

The repo already contains:

- architecture and cognition docs;
- extracted `tg-bridge`;
- new reusable runtime slice under `src/sonya_runtime`;
- tests for both bridge and runtime pieces;
- scripts for operational launch.

### 5.3 Telegram Bridge Reality

There is a working Telegram bridge package:

- `packages/tg-bridge`

It handles:

- Telegram input/output;
- text replies;
- image generation path;
- image/vision input path;
- session history;
- prompt assembly through the current host/runtime setup.

But `tg-bridge` is **not** Sonya itself.

It is a channel surface and integration shell.

### 5.4 Reusable Task/Action Runtime Reality

There is now a first reusable runtime slice under:

- `src/sonya_runtime`

This is important.

It means the project no longer relies only on Telegram-local fake agent theater.

Current reusable runtime pieces include:

- action models;
- planner policy;
- task models;
- separate SQLite task store;
- task service;
- task executor;
- task worker;
- continuity-facing canonical response/event stubs;
- storage path helpers.

Task persistence currently lives separately from memory at:

- `C:\Users\Jester\.openclaw\sonya_runtime\tasks.db`

This runtime is still early, but it is real code and already wired into `tg-bridge`.

## 6. What Does Not Exist Yet

Important negative facts:

- there is no complete `sonya-core` application yet;
- there is no finished general scheduler/runtime orchestration layer;
- there is no fully implemented shared subject state engine;
- there is no full principal/authority layer in production;
- there is no mature harness/governance subsystem;
- there is no complete skills runtime;
- there is no finished multi-channel runtime beyond Telegram;
- there is no true body controller or simulation runtime in production.

Outside models must not confuse:

- "there are docs about it"

with

- "it already exists in code".

## 7. The Most Important Architectural Truth

The single most important architectural truth is:

**Sonya must be one continuous subject above all channels.**

That means:

- Telegram is not Sonya;
- Discord would not be Sonya;
- TTS would not be Sonya;
- an avatar would not be Sonya;
- a model backend is not Sonya.

Those are surfaces, renderers, and substrates.

The actual load-bearing layer is:

- subject core;
- continuity stream;
- canonical response before rendering;
- shared memory;
- shared task and action reality.

If an external model proposes an architecture where each channel effectively becomes a new instance, that proposal is wrong.

See:

- [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)

## 8. Current Architectural Stack in Plain Language

The current intended stack is roughly:

1. subject core and continuity;
2. memory and identity;
3. planner and capability runtime;
4. task/action runtime;
5. channel adapters and renderers;
6. harness and governance;
7. provider abstraction and future brain backends;
8. embodiment and simulation path.

This is not fully implemented yet, but it is the right map.

## 9. Memory Reality

Memory currently still depends heavily on the OpenClaw-side memory system.

That includes:

- `memory.db`
- context loader logic
- post-response memory hooks

Current practical behavior:

- working memory is active;
- significant conversations are again flowing into events after recent fixes;
- long-term fact/lesson extraction exists only partially and still needs more disciplined implementation.

This means memory is real, but not yet in its final Sonya-owned form.

External models should treat the current memory stack as:

- operationally important;
- architecturally transitional.

## 10. Action and Task Reality

One of the recent major fixes was killing fake background-work claims.

Sonya is not supposed to say:

- "I'm checking files now";
- "I'll come back in 15 minutes";
- "I created the document";

unless the runtime really created or executed something.

The new task/action runtime exists specifically to stop that bullshit.

Current action types include:

- `reply`
- `generate_image`
- `reply_and_generate_image`
- `create_task`
- `reply_and_create_task`
- `ask_clarification`
- `report_limitation`

Current safe task kinds include:

- `workspace_analysis`
- `documentation_synthesis`
- `lead_workflow_analysis`
- `memory_diagnosis`
- `file_search_and_summary`

Important constraint:

v1 worker tasks are intentionally read-oriented and bounded.

They are not a green light for arbitrary file mutation.

See:

- [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)

## 11. Channel Reality

Right now Telegram is the live channel.

That does **not** mean the architecture should hard-code Telegram assumptions into the future system.

The correct relationship is:

- `tg-bridge` is a live ingress/egress surface;
- `sonya_runtime` is the start of reusable runtime logic;
- future `sonya-core` should absorb more of the actual shared planner/executor/continuity logic;
- channels should shrink toward adapter status over time.

## 12. Provider and Model Reality

The current live provider path is OpenRouter-compatible.

Historically the system has used:

- text/vision through Gemma-based paths;
- separate image generation through Gemini image paths.

This is operationally useful but not sacred.

The project must stay provider-independent.

Any external model working here should avoid proposals that bind cognition, identity, or runtime structure too tightly to one current provider API.

## 13. Future Brain Stack

The project explicitly keeps a path open toward future brain evolution.

That includes the possibility of:

- self-hosted models;
- more persistent stateful backends;
- recurrent/stateful systems such as RWKV-like paths;
- richer internal state representations than plain chat history.

This matters because some future data models will need to distinguish:

- subject state;
- memory state;
- runtime task state;
- model backend state;
- future recurrent brain state.

Do not collapse these into one blob.

In particular:

- Sonya's identity is not identical to a provider session;
- Sonya's continuity is not identical to a model cache;
- a future RWKV state is not "the whole Sonya".

It is only one part of a possible future brain substrate.

## 14. Voice, Embodiment, and Physical Body

The project does not stop at text.

Long-term direction includes:

- TTS or other voice rendering;
- visual/avatar rendering;
- simulation interfaces;
- eventually a physical body track.

Current position:

- voice is a renderer, not a second self;
- avatar is a renderer/embodiment surface, not a second self;
- physical embodiment must stay architecturally visible even before hardware exists.

The intended future may include:

- robot manipulator;
- smart-home integrations;
- sensory/action loops;
- simulation-backed body/world interfaces.

But these must remain attached to the same subject core.

The project is **not** trying to build a disconnected voice bot, then a disconnected avatar bot, then a disconnected robot bot.

It is trying to build one Sonya that can later use all of those surfaces.

## 15. Visual Identity Reality

Sonya also has a stabilized visual identity track.

External models should know that visual appearance is not random flavor text.

There is already continuity-sensitive work around:

- a defined visual baseline;
- identity-linked appearance details;
- embodiment as a real architectural concern, not decorative lore.

Do not treat visual identity as disposable prompt glitter.

## 16. What External Models Must Not Do

If you are an external model entering this repo, do **not**:

- reduce the project to "just a Telegram bot";
- propose channel-specific personas as if that is acceptable;
- confuse docs with finished runtime code;
- pretend background work happened if no task or executor path exists;
- bind the architecture too tightly to the current provider;
- propose unsafe self-modification shortcuts without governance;
- flatten memory, tasks, identity, and backend state into one database or one vague context blob.

## 17. What External Models Should Prioritize

When contributing here, prioritize:

1. continuity over local hacks;
2. reusable runtime logic over bridge-local tricks;
3. explicit state over narrative pretending;
4. clear architectural boundaries over convenience blobs;
5. VPS/future-host portability over local-machine magic;
6. one-subject design over many-surface confusion.

## 18. Practical File and Runtime Anchors

Key current anchors:

- repo root: `C:\Users\Jester\Desktop\Sonya`
- live host root: `C:\Users\Jester\.openclaw`
- channel package: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge`
- reusable runtime: `C:\Users\Jester\Desktop\Sonya\src\sonya_runtime`
- task DB: `C:\Users\Jester\.openclaw\sonya_runtime\tasks.db`
- current docs root: `C:\Users\Jester\Desktop\Sonya\docs`

## 19. What To Read Next

If you need more than this briefing, read next in this order:

1. [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md)
2. [core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
3. [architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
4. [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
5. [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)
6. [cognition/MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md)
7. [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md)

## 20. Short Bottom Line

Sonya is being built as one persistent subject-like runtime with memory, continuity, action capability, future voice/body paths, and explicit architecture.

Right now the live system is a hybrid:

- OpenClaw still hosts the operational shell;
- `tg-bridge` is the active Telegram surface;
- `sonya_runtime` is the first reusable runtime slice;
- the final `sonya-core` still has to be built.

If you help on this repo, optimize for that future shape instead of patching local hacks that make the current shell look temporarily convenient.
