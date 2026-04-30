# HERMES ANALYSIS

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
