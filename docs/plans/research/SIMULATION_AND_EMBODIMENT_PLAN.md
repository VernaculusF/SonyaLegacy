# SIMULATION AND EMBODIMENT PLAN

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
