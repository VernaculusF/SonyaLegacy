# Telegram Bridge Extraction Design

## 1. Purpose

This document defines how the working Telegram bridge currently living in `C:\Users\Jester\.openclaw` will be extracted into the Sonya project without breaking the existing OpenClaw runtime.

The goal is not to redesign the bridge from scratch. The goal is to:

- preserve working behavior;
- move the bridge entrypoint into `C:\Users\Jester\Desktop\Sonya`;
- turn the bridge into a reusable package;
- keep `.openclaw` as a live runtime environment and consumer;
- create a path for later reuse inside Sonya core.

The extraction must not introduce hacks, dead code, or speculative architecture that does not serve the running system.

## 2. Non-Negotiable Constraints

The extraction must satisfy all of the following:

- no behavior regression in current Telegram flow;
- no loss of session state semantics;
- no loss of media handling behavior;
- no loss of bootstrap context loading behavior;
- no change to OpenClaw memory hooks unless explicitly required for parity;
- no fake abstractions that only add indirection;
- no dead modules created "for future use";
- no contradiction with:
  - [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
  - [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/ARCHITECTURE_PLAN.md)
  - [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/REFERENCE_SYSTEMS_ANALYSIS.md)
  - [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/OPENCLAW_ANALYSIS.md)
  - [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/HERMES_ANALYSIS.md)
  - [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/OMNIAGENT_ANALYSIS.md)

## 3. Current OpenClaw Bridge Shape

The current live bridge is centered around:

- [telegram-bridge.mjs](C:/Users/Jester/.openclaw/telegram-bridge.mjs)
- [start-telegram-bridge.cmd](C:/Users/Jester/.openclaw/start-telegram-bridge.cmd)
- [telegram-bridge-state.json](C:/Users/Jester/.openclaw/telegram-bridge-state.json)
- [telegram-bridge.log](C:/Users/Jester/.openclaw/telegram-bridge.log)
- [telegram-bridge-sessions](C:/Users/Jester/.openclaw/telegram-bridge-sessions)
- [workspace/tools/telegram-bridge-format.mjs](C:/Users/Jester/.openclaw/workspace/tools/telegram-bridge-format.mjs)
- [workspace/tools/telegram-bridge-media.mjs](C:/Users/Jester/.openclaw/workspace/tools/telegram-bridge-media.mjs)

The bridge currently performs all of these responsibilities in one runtime:

- read config and runtime paths;
- load workspace anchors and memory context;
- persist poll state;
- persist per-chat short sessions;
- poll Telegram Bot API;
- normalize Telegram updates;
- download inbound media;
- classify text / vision / image generation requests;
- build model payloads;
- call OpenRouter-compatible API through local omniroute;
- parse text and event-stream responses;
- send replies and generated images back to Telegram;
- invoke post-response memory hook.

This is already a real working system. Extraction must preserve this working contract before optimizing internals.

## 4. Target Project Layout

The bridge code will move into the Sonya repository under a reusable package:

```text
C:\Users\Jester\Desktop\Sonya\
├─ docs\
│  ├─ core\
│  └─ plans\
├─ packages\
│  └─ telegram-userbot\
│     ├─ README.md
│     ├─ pyproject.toml
│     ├─ TODO.md
│     ├─ src\
│     │  └─ telegram_userbot\
│     │     ├─ __init__.py
│     │     ├─ app.py
│     │     ├─ paths.py
│     │     ├─ config.py
│     │     ├─ state.py
│     │     ├─ sessions.py
│     │     ├─ logging.py
│     │     ├─ bootstrap.py
│     │     ├─ prompts.py
│     │     ├─ media.py
│     │     ├─ formatting.py
│     │     ├─ telegram_api.py
│     │     ├─ model_client.py
│     │     ├─ hooks.py
│     │     ├─ handlers.py
│     │     ├─ update_loop.py
│     │     └─ adapters\
│     │        ├─ __init__.py
│     │        └─ openclaw.py
│     └─ tests\
│        ├─ fixtures\
│        ├─ test_formatting.py
│        ├─ test_media.py
│        ├─ test_sessions.py
│        ├─ test_bootstrap.py
│        ├─ test_model_client.py
│        ├─ test_handlers.py
│        └─ test_openclaw_adapter.py
├─ scripts\
│  └─ run-openclaw-bridge.ps1
├─ src\
│  └─ sonya\
└─ pyproject.toml
```

## 5. Responsibility Boundaries

### 5.1 `telegram-userbot` package owns

- Telegram polling and update loop;
- Telegram Bot API transport;
- input normalization;
- media download and packaging;
- prompt assembly for bridge use;
- short session persistence;
- model transport logic;
- post-response hook invocation;
- adapter contracts for host environments.

### 5.2 OpenClaw host environment owns

- workspace anchors and identity files;
- memory system implementation;
- post-response memory semantics;
- config file contents and local runtime policy;
- local state directories and media directories;
- gateway and local model routing.

### 5.3 Sonya core does not yet own

At this phase, Sonya core does not replace OpenClaw runtime logic. It only becomes the source repository for the bridge package.

## 6. Extraction Strategy

Recommended strategy: wrapper-first extraction with parity checks.

### Phase 1: Repository bootstrap

- initialize git repository in `C:\Users\Jester\Desktop\Sonya`;
- create package skeleton under `packages/telegram-userbot`;
- create Python packaging, test harness, and execution script layout.

### Phase 2: Behavior-preserving code extraction

Move logic from current bridge into modules without changing runtime semantics:

- `telegram-bridge-format.mjs` -> `formatting.py`
- `telegram-bridge-media.mjs` -> `media.py`
- config and path logic -> `paths.py`, `config.py`
- bootstrap loader -> `bootstrap.py`
- state persistence -> `state.py`
- session persistence -> `sessions.py`
- Telegram HTTP calls -> `telegram_api.py`
- OpenRouter-compatible calls -> `model_client.py`
- update handling -> `handlers.py`
- poll loop -> `update_loop.py`
- runtime entry -> `app.py`

### Phase 3: OpenClaw adapter wiring

Create `adapters/openclaw.py` to resolve:

- root paths inside `.openclaw`;
- workspace anchor locations;
- memory context loader path;
- post-response hook path;
- session, log, state, inbound, and generated media paths.

The adapter will be the only place that knows OpenClaw-specific file topology.

### Phase 4: OpenClaw consumer switch

Replace `.openclaw` entrypoint usage so the bridge launches from the Sonya project repository, while still operating on `.openclaw` data and runtime paths.

### Phase 5: Parity verification

Before cleanup, verify:

- identical formatting output for existing test vectors;
- identical prompt classification behavior;
- identical media extraction behavior;
- identical session truncation behavior;
- identical Telegram allowlist behavior;
- identical `/start` response path;
- identical post-response hook invocation contract;
- compatible state file updates and raw update logging.

### Phase 6: Post-parity cleanup

Only after parity:

- optimize repeated bootstrap loading;
- reduce unnecessary file IO;
- isolate host-specific concerns harder;
- prepare future Sonya adapter.

## 7. Module Design

### `paths.py`

Defines path contracts for a host environment.

Must answer:

- where config lives;
- where state file lives;
- where logs go;
- where sessions live;
- where raw Telegram updates go;
- where inbound media goes;
- where generated media goes;
- where workspace root lives.

### `config.py`

Loads host configuration and exposes only bridge-relevant fields.

Must not become a dump of every host config option.

### `state.py`

Owns bridge poll offset persistence only.

### `sessions.py`

Owns short rolling chat history only.

Must preserve current truncation behavior.

### `logging.py`

Owns append-only bridge logging behavior.

### `bootstrap.py`

Loads:

- `AGENTS.md`
- `SOUL.md`
- `HEARTBEAT.md`
- `IDENTITY.md` when present
- memory context via `context_loader.py`

Must preserve current prompt bootstrap semantics.

### `prompts.py`

Builds chat-completions messages from:

- bootstrap context;
- recent session history;
- current user content;
- language hint.

### `formatting.py`

Owns:

- markdown-ish to Telegram HTML rendering;
- chunk splitting.

### `media.py`

Owns:

- prompt classification;
- Telegram media extraction;
- OpenRouter-style event-stream parsing;
- data URL packaging.

### `telegram_api.py`

Owns Telegram Bot API calls:

- `getUpdates`
- `sendMessage`
- `sendPhoto`
- `getFile`
- file download helpers

### `model_client.py`

Owns:

- model selection from OpenClaw config;
- request payload building;
- chat completion invocation;
- text response parsing;
- image generation response parsing.

### `hooks.py`

Owns post-response hook invocation contract only.

### `handlers.py`

Owns per-update behavior:

- allowlist enforcement;
- `/start` handling;
- text path;
- vision path;
- image generation path;
- hook trigger.

### `update_loop.py`

Owns:

- poll loop;
- state update after processed update id;
- raw update logging;
- backoff on failures.

### `app.py`

Runtime composition root for bridge execution.

## 8. Test Strategy

Tests are mandatory and must be written as extraction guards, not decoration.

### Required test groups

#### Formatting

- markdown headings to Telegram HTML;
- inline code / fenced code;
- bullet normalization;
- safe chunk splitting.

#### Media

- image-generation prompt detection;
- vision path detection;
- photo/sticker/document extraction;
- event-stream image parsing.

#### Sessions

- session file creation;
- session load fallback;
- rolling history truncation.

#### Bootstrap

- correct reading of workspace anchor files;
- graceful absence of optional files;
- context loader invocation contract.

#### Model client

- config-driven model resolution;
- payload assembly;
- payload parsing;
- image event-stream parsing.

#### Handlers

- `/start` path;
- allowlist pass and deny;
- text message handling;
- media handling;
- image generation handling;
- post-response hook call.

#### Adapter

- OpenClaw root path resolution;
- expected host file layout;
- compatibility with current `.openclaw` directory structure.

### Fixtures

Fixtures should be taken from current OpenClaw behavior:

- representative raw Telegram updates;
- representative text requests;
- representative photo/sticker cases;
- representative SSE image generation response.

## 9. Performance and Reliability Rules

The extracted bridge must follow these rules:

- avoid repeated path recomputation when static contracts can be cached;
- keep file IO explicit and bounded;
- avoid loading full workspace state when only bridge bootstrap is needed;
- avoid unnecessary JSON parsing on hot paths;
- keep poll loop simple and restart-safe;
- preserve append-only raw update logging;
- preserve safe fallback behavior when model response formatting is imperfect.

Optimizations must not alter semantics before parity is proven.

## 10. What Must Not Be Done

- do not rewrite the bridge from scratch;
- do not move OpenClaw memory system into this package;
- do not introduce speculative Sonya-only abstractions;
- do not collapse host adapter and bridge core into one blob;
- do not leave dead compatibility layers behind;
- do not keep both old and new logic active without a clear switch path;
- do not "clean up" behavior that currently works until parity tests pass.

## 11. Definition of Success

The extraction is successful when all of the following are true:

- bridge entrypoint lives in `C:\Users\Jester\Desktop\Sonya`;
- `.openclaw` acts as host environment and consumer;
- current Telegram behavior is preserved;
- bridge code is modular and test-covered;
- host-specific assumptions are isolated in OpenClaw adapter code;
- no dead code or fake abstractions were introduced;
- the result is ready to be reused later by Sonya core.

## 12. Next Step

After this spec is accepted, the next artifact must be a detailed implementation plan for:

- repository bootstrap;
- package scaffold;
- behavior-preserving bridge extraction;
- OpenClaw adapter switch;
- parity test execution.
