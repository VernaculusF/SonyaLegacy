# HERMES ANALYSIS

**Status:** Active
**Type:** Reference Analysis
**Scope:** Hermes as orchestration role, shell/brain split, and world-facing adapter logic
**Depends on:** [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
**Used by:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), future channel and embodiment work
**Last reviewed:** 2026-05-01


## 1. Статус Hermes в текущем проекте

В текущем workspace `Hermes` не обнаружен как локальный репозиторий или готовый модуль.

Поэтому здесь `Hermes` анализируется не как существующая кодовая база, а как архитектурная роль, описанная в [`ОСНОВА.md`](C:/Users/Jester/Desktop/план/ОСНОВА.md:460).

## 2. Что такое Hermes по смыслу плана

Hermes в проекте - это внешний оркестратор Сони.

Его роль:

- принимать сообщения из каналов;
- управлять adapters;
- собирать body/signal events;
- вызывать brain backend;
- передавать назад ответы и действия;
- быть world-facing shell for Sonya runtime.

## 3. Почему эта роль полезна

### 3.1 Разделение мозга и оболочки

Это хорошая идея.

Она позволяет:

- менять brain backend без переписывания channel logic;
- изолировать channels and world interfaces from cognition core;
- перейти к hybrid or self-hosted brain later.

### 3.2 Естественное место для adapters

Hermes-role естественно держит:

- Telegram adapter;
- Web/admin adapter;
- avatar adapter;
- embodiment adapter;
- future simulation bridge.

### 3.3 Event-driven orchestration

Это хорошо ложится на Sonya architecture, потому что помогает мыслить среду как:

- события;
- сигналы;
- действия;
- последствия.

## 4. Главный риск Hermes

Есть опасность превратить `Hermes` в мешок вообще всего внешнего.

То есть оркестратор может распухнуть до состояния, где в нём окажется:

- routing;
- cognition shortcuts;
- memory shortcuts;
- business logic;
- embodiment logic;
- channel rules.

Так нельзя.

## 5. Что берём в Sonya core

- Hermes как архитектурную роль;
- разделение shell and brain;
- adapter-first thinking;
- event bridge between world and cognition.

## 6. Что не делаем

- не делаем Hermes mandatory blocker before MVP;
- не тащим body complexity в critical path first runtime slice;
- не смешиваем orchestration with identity core;
- не даём оркестратору стать новым монолитом.

## 7. Итоговый вывод

Для Сони `Hermes` должен быть переосмыслен не как конкретный чужой компонент, а как:

- orchestration shell;
- adapter host;
- world bridge.

То есть Hermes в Sonya project - это архитектурная функция, которую мы реализуем сами, а не священная внешняя зависимость.


## 8. Appendix: Code-Level Audit (2026-05-13)

This section records observations after explicitly searching for Hermes as code or artifact inside the live OpenClaw host and the Sonya repo.

### 8.1 Search Results

- `C:\Users\Jester\.openclaw\` does not contain a `Hermes` directory, a Hermes package, or a Hermes entry in `plugins/`, `subagents/`, `flows/registry.sqlite`, `cron/jobs.json`, or `openclaw.json`.
- `C:\Users\Jester\.openclaw\_tmp_omniagent\` does not reference Hermes in its package tree (`omniagent/agents`, `omniagent/gateway`, `omniagent/channels`, `omniagent/rl`, `omniagent/security`, `omniagent/tools`). The README only mentions Hermes as a comparison column, not as a dependency or embedded module.
- `C:\Users\Jester\Desktop\Sonya\` does not reference Hermes in code or work docs.

Conclusion: Hermes has no runtime footprint available for code-level audit in the current workspace. It remains **architectural-role-only**, not a file tree we can inspect.

### 8.2 Consequence for Reference Analysis

The absence is not a gap in the analysis. It clarifies a rule:

- Everything this project says about Hermes must be treated as **design inspiration**, not **code inheritance**.
- No code path in Sonya may claim to be “compatible with Hermes” or “pluggable into Hermes” until a concrete external Hermes surface is actually available for inspection.
- When Hermes-like concepts are discussed (orchestration shell, adapter-first routing, body/signal layer), the source of truth is this document plus [`docs/план/ОСНОВА.md`](C:/Users/Jester/Desktop/Sonya/docs/план/ОСНОВА.md), not any speculative external repository.

### 8.3 What Already Plays The Hermes Role Locally

Several subsystems in OpenClaw already carry pieces of the Hermes role, even without that name:

- `C:\Users\Jester\.openclaw\telegram-bridge.mjs` acts as a single-channel ingress/egress shell, connecting Telegram to the cognition path (model call + memory hook).
- `openclaw.json.channels.telegram` + `gateway` together approximate an adapter + routing + auth front door.
- `C:\Users\Jester\.openclaw\flows\registry.sqlite` plus `cron/jobs.json` and `delivery-queue/` are the closest thing to an active orchestration surface currently on the host.
- `workspace/hooks/` holds the only currently enabled hook pipeline (`working-memory-logger`), which functions as a post-cognition side-effect step.

The aggregate of those is the *de facto* Hermes-analog in the live host, even though none of them is labeled that way.

### 8.4 Implication For Sonya

- The Sonya-side counterpart to Hermes is not a future external dependency; it is the part of Sonya that will own `channels/`, `routing/`, `scheduler/`, `delivery/`, and `hooks/`. That responsibility is ours to build.
- We should not leave “orchestration shell” as a vague future slot. The Hermes role should be explicitly absorbed into `sonya_runtime/channels/*`, `sonya_runtime/routing/*`, and the future `sonya_runtime/scheduler/*`, all sitting between subject core and provider/tool layers.
- Any contract that we later label “Hermes-compatible” must start from the real list of responsibilities the live host already demonstrates: polling, ingress normalization, raw-update audit, allowlist policy, per-channel timeouts, outbound chunking and HTML fallback, media download, post-response hook invocation, and persistent state offset — not from marketing-level descriptions.

### 8.5 Honest Limitation

Until an actual Hermes codebase is provided for inspection in this workspace, this document should remain a **role specification**, not a comparison. A real code-level audit of Hermes will be added to this file if and when that code becomes available.
