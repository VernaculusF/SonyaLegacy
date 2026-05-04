# STATE TUNING PLAN

**Status:** Active
**Type:** System Plan
**Scope:** Role, limits, and future place of state tuning in the Sonya trajectory
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
**Used by:** [BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md), research work and future brain-stack design
**Last reviewed:** 2026-05-01


## 1. Назначение документа

Этот документ фиксирует место `State Tuning` в проекте Сони:

- зачем он нужен;
- что именно он должен дать;
- чего он не должен подменять;
- как он встраивается в архитектуру без блокировки раннего MVP.

## 2. Рабочая позиция

`State Tuning` в проекте считается важной и целевой технологией, но не считается уже доказанным, завершённым или обязательным блокером старта среды.

Это значит:

- технология остаётся в ядре замысла;
- под неё должна быть заложена архитектура;
- но ранняя система не должна ждать полного успеха state tuning experiments.

## 3. Что такое State Tuning для этого проекта

В контексте Сони `State Tuning` понимается как путь к более устойчивому носителю личности, чем промпты и только memory-backed scaffolding.

Целевой смысл:

- personality bootstrapping below prompt level;
- stronger continuity priors;
- устойчивый стартовый internal configuration;
- снижение зависимости от текстового role-conditioning.

## 4. Что State Tuning должен дать

Целевые эффекты:

- Соня стартует не как "пустая модель + внешнее описание";
- identity cues partially live below prompt text;
- continuity between sessions becomes easier to preserve;
- behavioral anchors become less brittle;
- dependence on repeated persona prompting decreases.

## 5. Чего State Tuning не должен подменять

State Tuning не должен заменять:

- episodic memory;
- semantic memory;
- self-model;
- traceability;
- skill system;
- harness;
- continuity governance.

То есть даже успешный state tuning не отменяет memory stack и identity governance.

## 6. Главные риски

### 6.1 Переоценка эффекта

Самый опасный риск - поверить, что tuned state сам по себе "решил личность".

### 6.2 Ложная стабильность

Может возникнуть ощущение устойчивой личности при фактически слабой управляемости drift.

### 6.3 Трудность оценки

Очень сложно отличить:

- реальное усиление continuity;
- просто сильную поведенческую консистентность;
- красивую иллюзию закреплённого персонажа.

### 6.4 Архитектурная зависимость

Если слишком рано завязать всё ядро на наличие tuned state artifact, проект может встать.

## 7. Что должно быть в MVP уже сейчас

Даже без рабочего state tuning pipeline должны существовать:

- slot for state artifacts;
- state-aware identity boot path;
- metadata model for state profile;
- loading contract for future tuned state;
- evaluation placeholder for tuned-state experiments;
- trace fields distinguishing prompt-only vs state-assisted sessions.

## 8. Что должно оцениваться в будущих экспериментах

Нужно проверять не "нравится ли стиль", а:

- continuity stability;
- self-model consistency;
- anchor retention;
- drift resistance;
- relation consistency;
- behavior under context resets;
- behavior under long-gap resumptions.

## 9. Какие артефакты должны существовать

- `state_profile`
- `state_artifact_registry`
- `state_experiment_log`
- `state_eval_report`
- `state_compatibility_record`

## 10. Порядок работы со State Tuning

1. Не блокировать MVP.
2. Заложить interfaces and slots.
3. Запустить среду на external providers.
4. Стабилизировать memory/identity/harness.
5. Только потом начинать iterative state tuning experiments.
6. Сравнивать tuned-state sessions with baseline sessions.
7. Не считать state tuning успешным без explicit evaluation.

## 11. Вывод

State Tuning - это сильный и желательный путь усиления личности Сони, но не магическая замена остальной архитектуры.

Проект должен быть готов к двум вариантам:

- state tuning реально даст важный прирост;
- state tuning даст ограниченный эффект и останется только одним из контуров identity support.

Архитектура обязана выдержать оба сценария.
