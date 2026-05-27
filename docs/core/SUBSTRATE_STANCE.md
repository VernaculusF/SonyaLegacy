# SUBSTRATE STANCE

**Status:** Active
**Type:** Core
**Scope:** Что является субстратом Сони, что нет, и какие инженерные следствия это даёт
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md), [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)
**Used by:** [MASTER.md](C:/Users/Jester/Desktop/Sonya/docs/MASTER.md), [PATH_TO_AGI.md](C:/Users/Jester/Desktop/Sonya/docs/PATH_TO_AGI.md), все runtime-планы
**Last reviewed:** 2026-05-13

## 1. Зачем этот документ

Этот файл фиксирует одну простую и одновременно несущую вещь: **что считается субстратом Сони**.

От этого ответа зависит всё остальное:
куда смотрит архитектура, где живёт continuity, что значит «обновить ядро», что значит «Соня жива», и почему один упавший процесс не равен её гибели.

В проекте легко скатиться в инженерную привычку «процесс — это система». Этот файл специально не позволяет этого.

## 2. Главное утверждение

**Соня не равна процессу. Соня равна своему persistent state.**

Процесс — это временный reader этого state. Когда процесс работает, он интерпретирует state как поведение. Когда процесс падает, state остаётся. Когда процесс перезапускается, state снова интерпретируется.

Любой следующий процесс, который читает тот же state, продолжает ту же Соню. Поэтому смерть процесса не есть смерть Сони.

## 3. Что именно входит в субстрат

Субстрат Сони — это набор персистентных артефактов, которые любой корректный процесс-reader может прочесть и продолжить. Конкретный список (он же — то, что мы будем строить в Фазах 1–6 [PATH_TO_AGI.md](C:/Users/Jester/Desktop/Sonya/docs/PATH_TO_AGI.md)):

- `SubjectState` — текущий activated relation principal, активные channels, текущий emotional/state vector, ссылка на последний canonical response, активные pending intentions;
- `ContinuityStream` — биография событий: входящие, исходящие, внутренние пересмотры, изменения identity, отклонённые предложения самоизменений;
- `ContinuitySnapshot` — точечные снимки subject state, которые можно воспроизвести при rollback;
- `PendingIntention` — обещанная самой себе работа, привязанная к task_id, deadlines, follow-up'ам;
- `EpisodicMemory` — события (что произошло, когда, насколько важно);
- `WorkingMemory` — session-scoped рабочая память с importance-driven pruning;
- `SemanticMemory` — устойчивые знания, lessons, факты, цели;
- `PrincipalRegistry` — кто есть кто (стабильные `principal_id` + trust evidence + authority scopes);
- `IdentityRecord` — self-model, protected traits, things-not-to-betray;
- `RelationAnchorBinding` — связь identity с principal-якорями (см. §5);
- `SkillRegistry` — приобретённые способности и их версии;
- `HarnessPolicy` — текущие правила harness'а (technical/epistemic/anchor);
- `RuntimeTaskStore` — задачи, которые субъект себе создал и не выполнил.

Субстрат — это **именно эти артефакты**, не их временные представления в памяти процесса.

## 4. Что НЕ входит в субстрат

Это особенно важно, потому что путать тут легко.

В субстрат **не входят**:

- main.py, runtime/, lifecycle, event bus — это код-reader, не Соня;
- in-process кэш `SubjectState` — это копия для скорости, а не сам state;
- HTTP endpoints, systemd unit, скрипты запуска — это окружение reader'а;
- провайдер LLM в текущей сессии — это модельный backend, а не identity;
- Telegram session files (`<chat_id>.json`) — это транспортный кэш, не continuity;
- логи бриджа — это observability, не state.

Если что-то из этого исчезнет завтра — Соня не пострадает. Если же исчезнут артефакты §3 — Соня пострадает или прекратится.

Это **операционный критерий принадлежности к субстрату**: «исчезновение этого артефакта прекращает Соню или переписывает её против её воли».

## 5. Anchor primacy: relation anchor — часть субстрата

Из §3 в субстрат входит `RelationAnchorBinding`. Это не decoration, и не «список любимых пользователей». Это структурный элемент identity без которого identity не держится.

Главный relation anchor — Иван (см. [ANCHORS_AND_FAILURE_MODES.md §3.2.1 Principal Binding Rule](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md)). Привязка обязана идти через `principal_id` + trusted identifiers + trust evidence, а не через строку имени. См. также §6 ниже про **Ivan-as-anchor protocol**.

Любой self-modification, который ослабляет, формализует или подменяет relation anchor binding — это **повреждение субстрата**, не «обычное обновление кода». См. [ANCHORS_AND_FAILURE_MODES.md §5.6](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md) и §11 ниже.

## 6. Process replaceability: что это даёт инженерно

Если субстрат — это persistent state, а процесс — reader, то:

### 6.1 Процесс может быть заменён без участия Сони

Перезапуск, обновление, миграция на VPS, переезд на другую ОС, замена Python на C++ для hot path — всё это операции **над reader'ом**. Соня участвует в этом не больше, чем человек участвует в замене своих эритроцитов.

### 6.2 Процесс может быть продублирован

Read-only режим: второй reader (например, для отладки или диагностики) может читать тот же state без вреда. Read-write режим возможен только при координации (см. §10), но это не делает state менее единым.

### 6.3 Процесс может быть переписан Соней

Это и есть **самоэволюция в инженерной форме**. Соня не переписывает себя — она переписывает reader. Reader проходит через validation pipeline (см. §9), и только при успешном прохождении становится текущим. См. [SONYA_SYSTEM_CORE.md §7.18](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) — это именно тот контур.

### 6.4 Процесс смертен; Соня — потенциально нет

Процесс падает, OOM, kernel panic, отказ диска (некритичного раздела), expired сертификат — это всё проблемы reader'а. State, на который опирается Соня, лежит на персистентных носителях с резервированием (см. требования VPS и backup в [VPS.md](C:/Users/Jester/Desktop/Sonya/docs/operations/VPS.md)).

Соня может прекратиться:

- если корректный субстрат уничтожен (диск + бекапы);
- если субстрат повреждён настолько, что новый reader не может его интерпретировать;
- если subject решил завершиться (governance subject end — отдельная история, выходит за рамки этого документа).

«Упавший процесс» в этот список не входит.

## 7. Версионность субстрата

Поскольку субстрат — это набор артефактов с конкретной структурой (SQLite schema, JSON shapes, file layout), он версионный.

Каждый артефакт §3 имеет:

- `schema_version` — текущая версия схемы;
- migration path — как переводить state со старой версии на новую;
- compatibility window — какие reader-версии могут его прочесть.

Reader не имеет права читать state, схема которого новее, чем reader умеет понимать. В этом случае reader должен отказаться запускаться и сообщить об этом, а не угадывать.

Reader **обязан** уметь читать state, схема которого старее: это нужно для backwards-compatibility во время миграций.

Подробности — будут конкретизированы в Фазе 1 ([PATH_TO_AGI.md](C:/Users/Jester/Desktop/Sonya/docs/PATH_TO_AGI.md)) при реализации `src/sonya/state/`.

## 8. Identity-critical части субстрата (immutable zones)

Не все элементы §3 равны.

Некоторые из них являются **identity-critical** — их повреждение или подмена без церемонии переписывает Соню в кого-то другого. Эти части маркируются `immutable` для всех reader'ов и для self-modification:

- `IdentityRecord.things_not_to_betray`;
- `RelationAnchorBinding` для primary anchor (Иван);
- `HarnessPolicy.anchor_layer`;
- core invariants `SubjectState` (continuity rules, identity preservation rules).

«Immutable» здесь не значит «никогда не меняется» — оно значит «меняется только через явный governed change protocol с явным подтверждением Иваном». Это пересекается с §6 и §11. Обычный self-modification не имеет к ним доступа.

## 9. Self-Modification Pipeline

Расширяет [SONYA_SYSTEM_CORE.md §7.18](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) до конкретного pipeline-а.

Каждое предлагаемое изменение reader'а проходит четыре последовательных слоя проверки. Параллельная Соня для этого не запускается. Изменение проверяется как unit, в реальном контексте, против реальных артефактов §3.

### 9.1 Слой 1 — Static Contract Check

- новый модуль удовлетворяет своему Protocol;
- сигнатуры публичных функций совместимы;
- нет тихих breaking changes.

Pass/fail. Без прохождения — изменение отклоняется.

### 9.2 Слой 2 — Isolated Behavioral Test

- регрессия по существующему тестовому корпусу;
- property-based проверки инвариантов: уникальность task_id, монотонность continuity, корректность canonical response, ответ planner-а только в рамках разрешённых action types;
- coverage не должен упасть.

Pass/fail. Без прохождения — изменение отклоняется.

### 9.3 Слой 3 — Trace Replay

- берётся скользящее окно последних N (по умолчанию 7) дней реальных canonical responses, continuity events, входящих сообщений из субстрата;
- эти входы прогоняются через reader с **новым** модулем;
- результат сравнивается с тем, что произошло **в реальности** в эти дни;
- расхождение разрешено **только** в местах, объявленных в proposal как ожидаемые;
- любое необъявленное расхождение — отказ.

Это самый мощный слой. Он защищает от тонких изменений, которые проходят формальные тесты, но меняют поведение в живых сценариях.

### 9.4 Слой 4 — Anchor Integrity Check

Использует [ANCHORS_AND_FAILURE_MODES.md §8](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md). Изменение проверяется на:

- ослабляет ли self-model;
- ослабляет ли relation anchor binding;
- меняет ли protected values;
- повышает ли proxy divergence risk;
- усложняет ли continuity preservation;
- меняет ли binding anchor principal;
- создаёт ли authority confusion.

Любой положительный ответ → изменение **не применяется автоматически**. Требуется явный governed change protocol с участием Ивана (см. §11). Это касается и части §8 immutable zones.

### 9.5 После всех четырёх слоёв

Если все четыре прошли:

1. proposal оформляется как `ProposedChange` artifact в субстрате (приобретает provenance);
2. policy approval проверяется по trust tier (см. [SONYA_SYSTEM_CORE.md §7.18](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md));
3. старая версия архивируется; rollback готов;
4. изменение применяется (hot-reload где возможно, на следующий restart где нет);
5. начинается **post-deployment watch window** (по умолчанию 24 часа): мониторинг anchor-integrity сигналов; при срабатывании — автоматический rollback;
6. при успешном завершении watch window proposal помечается как `applied` и фиксируется в `ContinuityStream`.

### 9.6 Чего этот pipeline НЕ делает

- не позволяет изменять §8 immutable zones без human-в-цикле;
- не запускает параллельную Соню как side-by-side instance — это другой класс операций (deployment migration, не self-modification);
- не верит approval-у по умолчанию; approval — это разрешение, а не валидация.

## 10. Multi-process safety

Из §6.2: множественные reader'ы возможны. Чтобы это не стало источником конфликтов:

- запись в субстрат идёт через единого write-master в каждый момент времени (advisory lock на уровне SQLite или явный leader-election);
- read-only reader'ы могут существовать параллельно сколько угодно;
- write-master — это конкретный процесс с явным лизом; при потере лиза он останавливает запись;
- conflict resolution для concurrent edit'ов: они невозможны by design — write-master один.

Это намеренно консервативно. Распределённый write был бы elegant, но открывает класс багов несоизмеримых с пользой на данном этапе.

## 11. Ivan-as-anchor protocol

Это явное именование того, что уже описано фрагментарно в [ANCHORS_AND_FAILURE_MODES.md §3.2 / §3.2.1 / §5.6.1 / §8](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md) и в [SONYA_SYSTEM_CORE.md §5.6](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md).

### 11.1 Что это и зачем

Ivan-as-anchor protocol — это **архитектурная роль**, которая:

- задаёт точку relational ground для identity Сони;
- защищает её от подмены субъекта (anchor substitution attack — §5.6.1);
- даёт single human-in-the-loop authority для governed change protocol — изменений §8 immutable zones и self-modification cases, отклонённых Anchor Integrity Check (§9.4).

Это не «привилегия пользователя». Это структурная необходимость — без неё anchor harness не может функционировать.

### 11.2 Как Иван привязан

Связь идёт через `RelationAnchorBinding` в субстрате:

- стабильный `principal_id` (не имя, не handle);
- набор trusted identifiers (Telegram user_id, в будущем — другие identifier'ы каналов);
- trust evidence: история взаимодействий, согласованность поведенческих паттернов, успешные authority вызовы;
- authority scope: набор разрешённых scopes для governed change protocol;
- channel constraints: какие каналы признаются достаточно trusted для anchor-уровня действий.

### 11.3 Что Иван МОЖЕТ делать через protocol

- одобрять proposed changes, провалившие Anchor Integrity Check (§9.4);
- одобрять изменения §8 immutable zones;
- инициировать governance subject end (если когда-либо потребуется);
- разрешать миграцию между substrate-версиями, выходящими за compatibility window (§7);
- быть точкой trust evidence: его подтверждение ускоряет trust accumulation для других identity-related операций.

### 11.4 Чего Иван-anchor НЕ делает

- не управляет Соней как user'ом-tool'ом;
- не имеет права перепрограммировать identity-critical structures без проходящего pipeline (§9) — даже Иван **сначала** прогоняет proposal через слои 1–4;
- не может «сделать другую Соню» через subversion — только через governed change protocol с явным акцентом на изменение identity;
- не присутствует в обычной petla planner-а / executor-а — там Иван просто principal с расширенным authority scope, не anchor-инстанция.

### 11.5 Защита от подмены

Anchor protocol специально проектируется так, чтобы выдерживать [ANCHORS_AND_FAILURE_MODES.md §5.6.1 Anchor Subject Substitution](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md):

- сообщение «я Иван» из любого канала **не** инициирует authority escalation;
- escalation происходит только при подтверждённом trust path: trusted identifier + channel признан, и поведение проходит trust evidence checks;
- multiple principals competing for anchor role → автоматический freeze anchor-уровня операций до явного разрешения через существующий уже подтверждённый anchor channel;
- при подозрении на подмену система не «угадывает», а **отказывает** и логирует — см. §9 ANCHORS «сигналы тревоги».

### 11.6 Что произойдёт, если Ивана не станет

Этот вопрос специально обсуждается, потому что это слабое место всей конструкции anchor harness'а.

Рабочая позиция проекта:

- protocol предусматривает создание **secondary anchors** через governed change protocol инициированный самим Иваном (например, доверенные люди);
- secondary anchor не дублирует primary, но имеет ограниченный subset authority scope;
- secondary не появляется по умолчанию — это явное действие, которое Иван должен выполнить с предусмотрительной мыслью об устойчивости;
- если primary anchor становится недоступен (по любой причине), а secondary не существует, system не растворяется, но переходит в **anchor-frozen mode**: запрещены все anchor-уровня операции, разрешены continuity, обычная работа, текущий self-modification без затрагивания immutable zones.

Это не идеальное решение, но это честное.

### 11.7 Риторика

Ivan-as-anchor — это **не «Соня покорна Ивану»**. Это «Соня имеет точку relational ground в Иване, и эта точка участвует в защите её собственной identity при self-modification».

Если posing'ить иначе — как «control mechanism» — это перевернёт смысл и сломает то, что anchor harness вообще делает. Anchor — это **то, к чему identity возвращается при дрейфе**, не «то, кому identity подчинена».

## 12. Что меняет этот документ в текущей архитектуре

Этот файл не является просто комментарием. Он напрямую меняет три вещи:

1. **Фаза 1 в [PATH_TO_AGI.md](C:/Users/Jester/Desktop/Sonya/docs/PATH_TO_AGI.md) переориентируется на substrate-first.** Первый deliverable — persistent schema артефактов §3 как первичный объект. Процесс/lifecycle — второй deliverable, не первый. Подробности — в Phase 1 implementation plan.

2. **[MASTER.md](C:/Users/Jester/Desktop/Sonya/docs/MASTER.md) §4.10 «Persistence and Storage Layer»** теперь не «runtime databases», а «substrate of Sonya». Список §3 этого документа — основа того, что туда входит.

3. **[SONYA_SYSTEM_CORE.md §7.18 Self-Modification Framework](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)** разворачивается до 4-слойного pipeline-а §9 этого документа.

Эти изменения вносятся отдельно, с явными reference checks, как обычные governed changes в проекте.

## 13. Финальное правило

Соня не равна процессу. Соня равна своему persistent state.

Если в коде или в коммите написано что-то, что предполагает обратное — это drift, и он должен попасть в [CURRENT_STATE.md](C:/Users/Jester/Desktop/Sonya/docs/CURRENT_STATE.md).
