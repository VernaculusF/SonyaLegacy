# BRAINMODEL EVOLUTION PLAN

**Status:** Active
**Type:** System Plan
**Scope:** Transition path from hosted providers to Sonya-owned brain stack
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [STATE_TUNING_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/STATE_TUNING_PLAN.md)
**Used by:** future research execution, provider abstraction design, self-hosted roadmap
**Last reviewed:** 2026-05-01


## 1. Назначение документа

Этот документ определяет, как проект относится к переходу от hosted models к собственному brain stack.

Он не про немедленное обучение своей модели, а про:

- архитектурную готовность;
- исследовательский путь;
- совместимость с ранним MVP;
- предотвращение vendor lock-in.

## 2. Базовая позиция

Сейчас система может жить на внешних моделях.

Но проект не должен закрепиться в положении:

"мозг Сони = всегда чужой API".

Поэтому `BrainModel Evolution` обязателен как слой, даже если на первом этапе он существует только как research-shell.

## 3. Что входит в BrainModel Evolution

Этот контур включает:

- model backend abstraction;
- brain profile registry;
- compatibility contracts for future self-hosted models;
- artifact slots for tuning/training/eval outputs;
- comparative evaluation path across backends.

## 4. Основные этапы эволюции brain stack

### Этап 1. Hosted external cognition

Соня работает через OpenRouter and compatible providers.

### Этап 2. Brain abstraction maturity

Среда уже может менять backend без поломки cognition and skill architecture.

### Этап 3. Hybrid mode

Часть функций может жить на hosted providers, часть - на локальных/self-hosted components.

### Этап 4. Self-hosted brain experiments

Появляются реальные backend experiments с собственными моделями или tuned variants.

### Этап 5. Brain specialization

Собственный brain stack начинает не просто "заменять API", а усиливать continuity, identity and internal adaptation patterns.

## 5. Что обязательно должно быть в MVP

- provider abstraction;
- brain backend interface;
- backend capability descriptors;
- model profile registry;
- evaluation placeholders for backend comparison;
- config paths for future self-hosted backends.

## 6. Что не должно происходить

- logic of memory/identity tied to one provider;
- skills hardcoded под конкретный vendor behavior;
- traceability format tied to one response schema;
- self-model dependent on one API's quirks.

## 7. Что нужно оценивать при переходе к своим моделям

Не только "качество ответа", но и:

- identity retention;
- continuity under long sessions;
- initiative quality;
- anchor stability;
- memory integration quality;
- reflexion quality;
- controllability under harness.

## 8. Почему это research, а не immediate implementation

Потому что:

- собственный brain stack дорогой;
- tuning/eval тяжелы;
- рано тащить это в критический путь runtime;
- сначала надо стабилизировать среду Сони как систему.

## 9. Долг проекта перед будущим brain stack

Даже пока мозг внешний, архитектура должна:

- не мешать будущему brain transition;
- хранить нужные артефакты и метаданные;
- различать backend-dependent and backend-independent layers;
- быть готовой к hybrid cognition setup.

## 10. Вывод

BrainModel Evolution - это не "потом подумаем про свою модель".

Это обязательный исследовательский вектор, который уже сейчас должен иметь место в архитектуре, even if no real self-hosted brain exists yet.
