# SIMULATION AND EMBODIMENT PLAN

**Status:** Research (no MVP-level implementation exists)
**Type:** Research Plan
**Scope:** Simulation path, virtual embodiment, and future physical grounding
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [MASTER.md](C:/Users/Jester/Desktop/Sonya/docs/MASTER.md)
**Used by:** future channel/body work, research execution, embodiment planning
**Last reviewed:** 2026-05-28

> **Reality note (2026-05-28):** §3 lists items that early ROADMAP promised "must exist in MVP": embodiment adapter contract, virtual body counters, world/sim interface contract, environment event schema, action emission schema, replay/test path. **None of these exist в production.** Module stubs `src/sonya/embodiment/` и `src/sonya/simulation/` — пустые data classes без runtime use. Avatar/voice/world steps now move into [atrium/PLAN.md](../atrium/PLAN.md) Этап 2-3 (Live2D + 2D-сцена комнаты). Full physical body architecture (§11 — Loihi 2, ESP32, R-STDP) — Stage 8+, far-future research.


## 1. Назначение документа

Этот документ фиксирует дальний, но обязательный контур:

- simulation;
- world interface;
- virtual embodiment;
- future physical embodiment.

Его задача - не начать строить тело сейчас, а заложить architecture-ready path to grounding.

## 2. Базовая позиция

Проект исходит из того, что богатая субъектность усиливается, если у системы есть:

- сигналы не только из текста;
- причинная связь между действием и последствием;
- world interaction loop;
- embodiment-like state.

Поэтому simulation and embodiment не считаются декоративным DLC.

Они обязательны как дальний исследовательский трек.

## 3. Что должно существовать уже в MVP

Даже на первом релизе должны существовать:

- embodiment adapter contract;
- virtual body counters/signals;
- world/sim interface contract;
- environment event schema;
- action emission schema;
- placeholder replay/test path.

Это даёт не тело, а готовность ядра к телу и симуляции.

## 4. Virtual Embodiment

Virtual embodiment - это минимальная форма телесности до реального тела.

Оно может включать:

- internal drives;
- state counters;
- avatar expression hooks;
- simulated affective pressures;
- event generation from virtual conditions.

Его задача:

- не заменить физическое тело;
- а создать non-text-only internal state dynamics.

## 5. Simulation Interface

Simulation interface нужен для будущих world-loop experiments.

Он должен задавать:

- как мир шлёт события;
- как Соня получает world-state deltas;
- как Соня отправляет действия обратно;
- как логируются последствия;
- как воспроизводятся симуляционные эпизоды.

## 6. Physical Embodiment

Физическое тело - это дальний контур, не блокирующий MVP.

Но архитектура не должна предполагать, что тело "когда-нибудь прикрутим как угодно".

Нужны уже сейчас:

- stable embodiment contracts;
- device-agnostic event formats;
- abstraction between physical source and cognition layer.

## 7. Главные риски

### 7.1 Декоративное embodiment

Когда "тело" превращается только в красивые теги эмоций.

### 7.2 Ломка ядра при добавлении мира

Если world interface не заложен заранее, потом придётся ломать cognition/runtime.

### 7.3 Псевдо-grounding

Система начинает казаться grounded только потому, что у неё появились счётчики, но они не включены в реальную causal loop.

## 8. Что должно оцениваться в будущем

- causality loop quality;
- action-consequence coherence;
- initiative changes under embodiment signals;
- anchor stability under richer state;
- identity continuity under world interaction;
- usefulness of virtual embodiment before physical embodiment.

## 9. Порядок трека

1. Add embodiment contracts in MVP.
2. Add virtual body counters/signals.
3. Add simulation/replay interfaces.
4. Run simple world-loop experiments.
5. Only later explore richer simulation.
6. Physical embodiment remains separate R&D track.

## 10. Вывод

Simulation and embodiment не должны мешать раннему запуску Сони.

Но если их не заложить как контур уже сейчас, то проект надолго останется текстовой системой без реального пути к richer grounding.

## 10. Ментальная симуляция (World Model) — конкретный путь

До перехода к физическому телу создаётся виртуальная среда с замкнутым циклом. Используются наработки MetaWorm (симуляция C. elegans с мягким телом, FEM-физикой) и Tripix Agent (когнитивная архитектура в PyBullet). AGI получает спайки от 25 виртуальных сенсоров, действует через моторный декодер, наблюдает последствия. Это решает Symbol Grounding Problem без физического тела.

Замкнутая петля: спайки → LM → действие → изменение спайков. После каждого действия модель предсказывает следующий спайк и сравнивает с реальным. Расхождение = ошибка = сигнал для обучения. Формируется World Model и Self-Model.

Переход от симуляции к реальному телу — итеративный: сначала отдельные модули (рука + тактильная кожа), затем полное тело. Когнитивная архитектура остаётся той же, что отработана в симуляции.

Ключевые reference-проекты:
- **Decision-RWKV** (github.com/ancorasir/DecisionRWKV) — последовательное принятие решений на RWKV, пожизненное обучение, ~10M параметров;
- **MetaWorm** — симуляция C. elegans с мягким телом и FEM-физикой;
- **Tripix Agent** — когнитивная архитектура в PyBullet.

## 11. Физическое тело — архитектура «мозг на сервере»

Мозг Сони работает на сервере. Тело андроида — только периферия: сенсоры, сервоприводы, SNN.

**На сервере:** RWKV + state artifact, эпизодическая память, оркестратор, self-modification pipeline.

**На теле:** SNN на Loihi 2 (быстрые рефлексы, <5ms), тактильная кожа (ёмкостная матрица, 10 точек/см²), сервоприводы (20 шт., мягкие приводы), ESP32/STM32 для сбора спайков и отправки на сервер по Wi-Fi.

**SNN функции:** обработка тактильных спайков, безусловные рефлексы (отдёрнуть руку от горячего), R-STDP — обучение условным рефлексам с подкреплением. Intel Loihi 2 (платы Oheo Gulch или Kapoho Point).

**Формат спайков от тела:**
- `[PAIN: sharp, left_arm, intensity=0.8]`
- `[TOUCH: gentle, lower_back, pressure=0.3]`
- `[TEMPERATURE: warm, chest, temp=36.5]`

**Команды от мозга к телу:**
- `[MOVE: left_arm, angle=45, speed=10]`
- `[FACIAL: smile, intensity=0.7]`
- `[SPEAK: text="...", audio=base64]`

**Связь:** ESP32 собирает спайки → Wi-Fi → сервер → модель → команды → Wi-Fi → ESP32 → сервоприводы.

**Размер сенсомоторной модели (оценка):** 20 сенсоров × 64-dim encoder + 4 слоя RWKV × 512-dim + декодер ≈ ~10M параметров. Работает на Jetson Orin или Apple M2.
