# MVP BOUNDARIES

**Status:** Active (with caveats — many "must exist" items don't)
**Type:** System Plan
**Scope:** Defines the mandatory floor of the first release without dropping load-bearing AGI contours
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md), [SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md)
**Used by:** runtime implementation plans, VPS migration
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):** Doc defines the **target** MVP shape ("full-scope shell with uneven maturity"). Honest progress vs target — many §3.1 "должно быть в боевом виде" items are not yet wired, many §3.3 "хотя бы как shell/stub" items are paper-only. See `docs/agents/EXTERNAL_MODEL_ONBOARDING.md §6-§7` for what actually runs and `docs/SYSTEM_BUILDOUT_PLAN.md` for path to closing the gap. Doc is preserved as direction, not a claim that MVP is done.


## 1. Назначение документа

Этот документ фиксирует, что именно считается MVP в проекте Сони, а что нет.

Он не сокращает идею проекта. Он удерживает границы первого релиза так, чтобы:

- не выкинуть обязательные AGI-контуры;
- не утонуть в бесконечной реализации;
- не переписывать всё заново после первого запуска.

## 2. Определение MVP

MVP в этом проекте:

`первый рабочий релиз, в котором существуют все обязательные контуры среды Сони, пусть и с разной зрелостью`

MVP не равен:

- "самый простой бот";
- "версия без сложных частей";
- "давайте сначала чатик, остальное потом";
- "временно забьём на identity/memory/harness".

## 3. Что обязательно должно быть в MVP

### 3.1 Обязательно в боевом виде

- long-lived runtime;
- provider abstraction;
- OpenRouter integration;
- persistent storage;
- episodic memory baseline;
- Telegram/Userbot channel;
- admin/diagnostics path;
- traceability baseline;
- harness baseline;
- restart-safe state handling;
- VPS-ready config and deploy layout.

### 3.2 Обязательно в частичном виде

- identity layer;
- semantic memory;
- context evolution;
- dual-layer reflexion;
- self-observation;
- skill injection;
- initiative layer.

### 3.3 Обязательно хотя бы как shell/stub/manual-gated

- real-time skill evolution;
- hyper-harness;
- self-modification framework;
- brainmodel evolution layer;
- embodiment adapter;
- simulation/world interface;
- future state tuning slot.

## 4. Что не обязано быть полноценно готово в MVP

Следующие вещи не обязаны быть зрелыми на первом релизе:

- полноценный self-hosted brain model;
- рабочий state tuning pipeline;
- production-grade real-time skill evolution;
- полностью автоматическая self-modification;
- реальная world simulation;
- физическое тело или device integration beyond virtual embodiment.

Но у них уже должны быть:

- место в архитектуре;
- интерфейсы;
- артефактные слоты;
- контракты;
- trace hooks.

## 5. Что не входит в MVP как обязательный результат

MVP не обещает:

- доказанное AGI;
- доказанное сознание;
- fully autonomous self-improvement;
- embodied intelligence;
- local self-hosted cognition;
- замену всех внешних моделей.

MVP обещает другое:

- полноценную среду, где путь к этим вещам уже заложен.

## 6. Красные линии MVP

MVP считается проваленным, если на выходе получится что-то из следующего:

- stateless bot;
- prompt wrapper;
- память как тупая история чата;
- отсутствие traceability;
- отсутствие harness baseline;
- отсутствие identity structures;
- отсутствие VPS-ready deployment;
- отсутствие explicit slots для future brain/state/simulation layers.

## 7. Что можно сознательно отложить после MVP

После первого релиза можно выносить в следующий цикл:

- улучшение semantic consolidation;
- усиление initiative sophistication;
- deeper self-observation metrics;
- full hyper-harness;
- stronger self-modification automation;
- state tuning experiments;
- simulation experiments;
- embodiment track.

Но только если базовый каркас уже реально присутствует.

## 8. Главный принцип границ

Если приходится выбирать между:

- красивой работающей игрушкой без AGI-контуров;
- более жёстким shell-MVP со всеми контурами, но разной зрелостью,

проект выбирает второе.

## 9. Практический вывод

MVP не должен быть маленьким по смыслу.

Он должен быть минимальным только по степени зрелости отдельных подсистем, но не по самому каркасу Сони.
