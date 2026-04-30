# REFERENCE SYSTEMS ANALYSIS

## 1. Назначение документа

Этот документ фиксирует, как проект Сони должен относиться к трём reference-системам:

- OpenClaw
- Hermes
- OmniAgent

Его задача:

- отделить заимствование идей от слепого копирования;
- зафиксировать, что каждая система даёт полезного;
- зафиксировать, что в каждой нельзя тащить в ядро Сони как есть;
- дать основу для корректировки implementation plans.

## 2. Статус трёх систем

### OpenClaw

Это не просто внешний референс, а текущая живая личная среда, в которой уже существуют:

- workspace-based identity injection;
- Telegram channel;
- memory database;
- heartbeat routines;
- hooks;
- локальные интеграции и локальные ключи.

### Hermes

Это не локальный готовый кодовый reference в текущем workspace, а архитектурная роль из [`ОСНОВА.md`](C:/Users/Jester/Desktop/план/ОСНОВА.md:452).

Для проекта Соня `Hermes` означает:

- оркестратор;
- оболочка над каналами;
- body/signal adapter layer;
- event bridge between cognition and world.

### OmniAgent

Это сторонний агентный framework, локально представленный клоном в `C:\Users\Jester\.openclaw\_tmp_omniagent`, с сильным маркетинговым заявлением:

- realtime skill evolution;
- context evolution;
- brain evolution;
- hyper-harness;
- deep reflexion.

Но как reference он должен рассматриваться критически.

## 3. Главное различие ролей

- `OpenClaw` даёт фактический живой operational опыт.
- `Hermes` даёт целевой образ оркестратора и world-facing shell.
- `OmniAgent` даёт набор амбициозных концептов и частично полезный vocabulary for future modules.

Их нельзя рассматривать как взаимозаменяемые.

## 4. Что мы берём у каждой системы

### Из OpenClaw

- идея workspace anchors (`AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`);
- идея долговременной памяти вне чата;
- идея session continuity through persistent artifacts;
- event/hook-based behavior;
- практический опыт того, что реально нужно живой персональной среде.

### Из Hermes

- роль отдельного оркестратора;
- разделение "мозга" и "внешней оболочки";
- adapters for channels, body, avatar, signals;
- event-driven integration between cognition and embodiment.

### Из OmniAgent

- vocabulary around skill/context/brain evolution;
- dual-loop reflexion direction;
- idea that harness must be more than one static scanner;
- idea of separating security/review layers from response generation.

## 5. Что нельзя брать как есть

### Из OpenClaw

- жёсткую зависимость личности от workspace injection как единственного механизма;
- flat local config with environment-specific secrets mixed into operational config;
- накопившиеся ad hoc hooks and scripts as final architecture;
- локальность как норму.

### Из Hermes

- слишком раннюю привязку к heavy embodiment path;
- смешивание orchestration role с философским смыслом системы;
- зависимость архитектуры MVP от наличия полного body-track.

### Из OmniAgent

- доверие README claims как реальному состоянию кода;
- gateway surface without hardened auth model;
- заявленные channels without verifying runtime truth;
- саму кодовую базу как фундамент Сони.

## 6. Итоговая позиция проекта

### OpenClaw

Используется как:

- operational ancestor;
- источник практических требований;
- источник данных и наблюдений.

Не используется как:

- финальное ядро Сони;
- готовая архитектура для роста в сторону AGI.

### Hermes

Используется как:

- архитектурная роль оркестратора;
- будущая внешняя оболочка среды.

Не используется как:

- обязательная ранняя кодовая зависимость;
- причина откладывать MVP без body path.

### OmniAgent

Используется как:

- словарь модулей;
- частичный conceptual reference;
- источник warning signs.

Не используется как:

- фундамент runtime;
- trusted direct base for Sonya core.

## 7. Практический вывод

Все последующие implementation plans должны проверяться против этого правила:

- брать operational lessons from OpenClaw;
- строить orchestration role in the spirit of Hermes;
- заимствовать только проверяемые идеи from OmniAgent;
- не тянуть ни одну из трёх систем как конечную архитектурную истину.
