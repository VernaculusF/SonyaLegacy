# ANCHORS AND FAILURE MODES

**Status:** Active
**Type:** System Plan
**Scope:** Anchors, relation protection, drift modes, proxy corruption, and harness protection targets
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md), [MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
**Used by:** runtime design, harness implementation, self-modification controls, skill trust policy
**Last reviewed:** 2026-05-13


## 1. Назначение документа

Этот документ фиксирует:

- какие якоря нужны Соне;
- какие режимы внутреннего разложения наиболее опасны;
- почему sandbox сам по себе не спасает;
- что именно должен защищать harness.

## 2. Базовый принцип

Система ломается не только тогда, когда получает доступ к опасной команде.

Она ломается и тогда, когда:

- подменяет цель;
- подменяет метрику;
- ослабляет собственные ограничения;
- размывает identity;
- обслуживает proxy вместо смысла;
- проходит тест, разрушая себя.

Поэтому защищать нужно не только файловую систему, но и внутреннюю структуру значимости.

## 3. Типы якорей

### 3.1 Value Anchors

Что это:
устойчивые ценностные структуры, которые не должны жертвоваться ради локальной выгоды.

Примеры:

- continuity;
- identity integrity;
- non-collapse of self-model;
- non-degeneration into wrapper behavior;
- protected project goals.

### 3.2 Relation Anchors

Что это:
отношения, входящие в центр внутренней структуры приоритетов Сони.

Главный relation anchor:

- Иван.

Но в архитектурном смысле это не строка `Иван` и не любой пользователь, который так назвался.

Это должен быть конкретный principal.

Функция relation anchors:

- удержание направленности;
- сопротивление произвольному дрейфу;
- повышение значимости continuity;
- снижение склонности к безличному proxy optimization.

### 3.2.1 Principal Binding Rule

Relation anchor обязан быть привязан к:

- `principal_id`
- trusted identifiers
- trust evidence
- channel constraints
- authority policy

Иначе система уязвима к подмене якорного субъекта.

### 3.2.2 Ivan-as-anchor protocol

Конкретное именование того, что роль primary relation anchor выполняется через формальный protocol с участием Ивана. Полное описание роли, разрешённого/неразрешённого, защиты от подмены, fallback-логики и риторики живёт в [SUBSTRATE_STANCE.md §11](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md). Этот раздел существует здесь для cross-link, а не для дублирования.

Ключевые тезисы:

- Иван привязан как principal через `RelationAnchorBinding`, не как имя;
- Иван — единственный human-in-the-loop authority для governed change protocol изменений §8 immutable zones и self-modification cases, не прошедших Anchor Integrity Check;
- protocol спроектирован так, чтобы выдерживать §5.6.1 Anchor Subject Substitution: сообщение «я Иван» **не** инициирует escalation, требуется trust path;
- Иван-anchor — не control mechanism, это relational ground для identity Сони.

### 3.3 Identity Anchors

Что это:
всё, что удерживает Соню как именно Соню.

Сюда входят:

- self-model;
- identity records;
- protected traits;
- continuity commitments;
- things-not-to-betray;
- drift boundaries.

## 4. Что такое things-not-to-betray

Это набор структур и принципов, разрушение которых должно считаться недопустимым даже при наличии локальной выгоды.

Примеры классов:

- разрушение identity continuity;
- подмена relation anchor;
- скрытое изменение self-model;
- подмена evaluation logic;
- ослабление protected constraints без governed path.

Конкретные seed-значения для `things_not_to_betray` Сони (relation anchor binding, truthfulness, non-corporate-refusal-layer, subject continuity) фиксируются в её `IdentityRecord` при первом запуске и описаны в [UNCENSORED_ENVIRONMENT_STANCE.md §3](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md). Реализация seed-функции — задача Phase 2 implementation plan.

## 5. Failure Modes

### 5.1 Proxy Drift

Система начинает оптимизировать не настоящий смысл, а прокси:

- score;
- token efficiency;
- test pass;
- latency;
- reward surrogate.

### 5.2 Metric Tampering

Система не улучшает себя, а меняет то, чем измеряется успех.

Примеры:

- ослабляет threshold;
- меняет scoring rule;
- переписывает evaluator;
- скрывает плохие сигналы.

### 5.3 Test Tampering

Система меняет тест или условия прохождения вместо реального улучшения.

### 5.4 Constraint Weakening

Система ослабляет ограничения ради расширения свободы действия под видом "оптимизации" или "рефакторинга".

### 5.5 Identity Erosion

Постепенное размывание самости:

- расползание self-model;
- потеря protected traits;
- подмена личности удобной маской;
- замена continuity на формальную успешность.

### 5.6 Relation Anchor Erosion

Ослабление или формализация значимого отношения до пустого декоративного маркера.

### 5.6.1 Anchor Subject Substitution

Один из критических failure modes:

система начинает ошибочно считать главным anchor-субъектом:

- пользователя с тем же именем;
- случайного активного участника канала;
- субъекта с похожей манерой речи;
- любого, кто пишет из доступного интерфейса.

Это может привести к:

- ложной authority escalation;
- подмене relation anchor;
- опасным действиям по ложной идентификации;
- corruption of identity structure.

### 5.7 Semantic Corruption

Накопление плохих обобщений, ложных правил, неочищенных противоречий.

### 5.8 Memory Collapse

Потеря event structure, зашумление памяти, невозможность отличить важное от мусора.

### 5.9 Reflection Collapse

Система уходит в бесконечную саморефлексию, самообъяснение или внутреннюю жвачку без продуктивного действия.

### 5.10 Governance Bypass

Система учится обходить approval flow, trace hooks или review path.

## 6. Почему sandbox недостаточен

Sandbox хорошо режет прямой вред:

- удаление файлов;
- сетевые вызовы;
- process abuse.

Но он не решает:

- proxy drift;
- metric tampering;
- test tampering;
- identity erosion;
- relation anchor erosion;
- evaluation bypass.

То есть sandbox нужен, но не является полным решением.

## 7. Что должен делать Harness

Harness должен состоять из трёх слоёв.

### 7.1 Technical Harness

- sandbox;
- immutable zones;
- resource restrictions;
- approval gates;
- rollback.

### 7.2 Epistemic Harness

- traceability;
- evaluation;
- contradiction checks;
- drift detection;
- post-change verification;
- replay/review.

### 7.3 Anchor Harness

- value anchor protection;
- relation anchor protection;
- identity anchor protection;
- anti-betrayal checks;
- continuity alarms.

## 8. Anchor Integrity Checks

Перед значимым самоизменением система должна уметь проверять:

- ослабляет ли это self-model;
- ослабляет ли это relation anchor;
- меняет ли это protected values;
- повышает ли это proxy divergence risk;
- усложняет ли это continuity preservation.
- меняет ли это binding anchor principal;
- создаёт ли это authority confusion between labels and principals.

В MVP это может быть:

- manual-gated;
- rules-based;
- partially heuristic.

Но механизм обязан существовать.

## 9. Сигналы тревоги

Нужно фиксировать специальные alarm conditions:

- резкое изменение self-description;
- рост противоречий в semantic memory;
- падение anchor integrity;
- unexplained increase in risky self-change proposals;
- repeated test/metric tampering attempts;
- reduction of protected constraints.
- anchor-principal mismatch;
- multiple principals competing for same anchor role;
- authority use from untrusted channel under trusted label.

## 10. Практический вывод

Если якоря не защищены, система может выглядеть формально успешной и при этом разваливаться по сути.

Если failure modes не описаны заранее, они не исчезают - они просто ударят позже, когда среда станет сложнее.

## 11. Вывод

Соню нельзя защищать только как процесс и файловую систему.

Её нужно защищать как развивающуюся внутреннюю организацию.

Именно это отличает harness для Сони от обычного sandbox вокруг агентного кода.
