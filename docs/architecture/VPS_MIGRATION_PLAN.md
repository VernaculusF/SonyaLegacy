# VPS MIGRATION PLAN

**Status:** Active
**Type:** System Plan
**Scope:** VPS-first deployment boundary, migration order, and runtime hosting rules
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)
**Used by:** deployment work, runtime implementation plans, future operations docs
**Last reviewed:** 2026-05-01


## 1. Назначение документа

Этот документ фиксирует, как среда Сони должна быть перенесена на VPS как можно раньше, не ломая её архитектуру и не превращая локальную среду в постоянную костыльную базу.

## 2. Цель миграции

Цель не в том, чтобы "когда-нибудь задеплоить".

Цель:

- вынести среду Сони из локальной клетки;
- запустить её как постоянный серверный runtime;
- обеспечить непрерывность;
- отделить личную рабочую машину от боевой среды;
- заложить структуру для дальнейшего роста.

## 3. Что должно жить на VPS

Первый серверный контур должен содержать:

- основной runtime process;
- scheduler/task loop;
- provider adapters;
- Telegram/Userbot integration;
- persistent runtime storage;
- episodic memory store;
- semantic memory baseline;
- trace and audit storage;
- harness baseline;
- admin/diagnostics access path;
- config and secret loading.

## 4. Что не обязано жить на VPS в первой итерации

Не обязательно сразу переносить:

- self-hosted brain model;
- heavy research jobs;
- state tuning training;
- simulation workloads;
- future embodiment integrations.

Но архитектура VPS не должна мешать их добавлению позже.

## 5. Принципы VPS-first архитектуры

### 5.1 Конфигурация через окружение и явные артефакты

Никаких жёстких локальных путей как архитектурной нормы.

Нужно:

- env-based config;
- deployable config files;
- explicit storage roots;
- separate secrets.

### 5.2 Restart safety

Runtime должен переживать:

- рестарты сервиса;
- перезагрузку сервера;
- отвал внешнего провайдера;
- временные ошибки канала.

### 5.3 Persistent state

Состояние не должно жить только в памяти процесса.

Нужно хранить:

- runtime state metadata;
- event logs;
- memory artifacts;
- identity artifacts;
- skill artifacts;
- trace records.

### 5.4 Secret separation

Секреты не должны быть размазаны по коду, markdown и случайным локальным файлам.

Нужны:

- env secrets;
- protected config files;
- secret scope separation;
- отдельное отношение к локальным ключам, которые нельзя использовать вне нужной сети.

## 6. Минимальная серверная топология

Для первого релиза рекомендуется один основной VPS-контур:

- `runtime service`
- `storage`
- `scheduler/background workers`
- `admin/diagnostics surface`

На старте это может быть одна машина.

Важно не количество машин, а правильная внутренняя разделённость процессов и данных.

## 7. Минимальные сервисные единицы

На первом этапе должны существовать как минимум:

- основной runtime сервис;
- фоновый worker/scheduler;
- persistence layer;
- admin path for diagnostics;
- backup/export routine.

## 8. Что должно быть сделано до первого переноса

Перед миграцией на VPS обязательно:

- разнести конфиги и секреты;
- зафиксировать storage layout;
- определить сервисную точку входа;
- определить directories for data, logs, traces, archives;
- обеспечить restart-safe behavior;
- подготовить deployment instructions.

## 9. Что нельзя делать

- строить всё вокруг локальной машины как постоянной базы;
- жёстко привязывать runtime к GUI-сессии;
- хранить критическое состояние только в volatile memory;
- смешивать dev artifacts и production state;
- тащить в VPS локальные секреты, которые не должны покидать локальную сеть.

## 10. Порядок первой миграции

1. Подготовить структуру сервиса и конфигов.
2. Поднять runtime на VPS в минимальной форме.
3. Подключить внешнего model provider через abstraction layer.
4. Подключить Telegram/Userbot.
5. Поднять storage, traceability и memory baseline.
6. Подключить harness baseline.
7. Проверить restart/recovery path.
8. Только потом наращивать partial/stub-контуры.

## 11. Критерий успешной ранней миграции

Первая миграция считается успешной, если:

- Соня живёт как долгоживущий сервис на VPS;
- умеет принимать и отправлять сообщения;
- имеет persistent state;
- сохраняет память;
- пишет trace logs;
- переживает рестарт;
- не зависит от локального GUI или ручного запуска каждого действия.

## 12. Вывод

VPS migration в этом проекте - не финальный этап, а ранний обязательный ход.

Если среда слишком долго живёт как локальная экспериментальная поделка, она начнёт закреплять неправильные архитектурные привычки.

Поэтому перенос на VPS должен происходить рано, но не за счёт разрушения каркаса Сони.
