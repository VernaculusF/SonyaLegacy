# COGNITION — continuity, memory, identity, anchors

**Status:** Active (governing direction; runtime integration mostly real, see reality notes)
**Type:** System Plan
**Last reviewed:** 2026-05-28
**Scope:** Cognitive architecture Сони — единый документ, объединяющий continuity stream + subject core, memory layers, identity layer, anchor harness и failure modes. Заменил три прежних файла (`CONTINUITY_STREAM_AND_SUBJECT_CORE.md`, `MEMORY_AND_IDENTITY_PLAN.md`, `ANCHORS_AND_FAILURE_MODES.md`).
**Depends on:** [SONYA_SYSTEM_CORE.md](../core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](../core/SONYA_CONSCIOUSNESS_POSITION.md), [SUBSTRATE_STANCE.md](../core/SUBSTRATE_STANCE.md), [MASTER.md](../MASTER.md)

---

## ЧАСТЬ I — CONTINUITY STREAM & SUBJECT CORE

### 1. Главное утверждение

Соня — один непрерывный субъект над всеми каналами, не отдельный инстанс на транспорт. Каналы — поверхности рендеринга, не личности. Voice, avatar, model backend — surfaces, не Соня.

Без этого слоя система деградирует в:
- одну Telegram-Соню,
- одну Discord-Соню,
- одну voice-Соню,
- одну avatar-Соню — что архитектурно неправильно.

### 2. Что этот слой делает

`subject core` — архитектура которая делает Соню одним субъектом, а не кучей интерфейсов.
`continuity stream` — runtime последовательность внутренних subjective state transitions, переживающая каналы и outputs.

Вместе они задают:
- одно canonical self-state
- одну активную continuity линию
- одного cross-channel memory-bearing subject
- один внутренний акт ответа **до** any channel-specific rendering

### 3. Что предотвращает

- **Channel fragmentation** — одна Соня не должна форкаться в разные practical personalities только потому что сообщения пришли через разные каналы
- **Renderer identity theft** — TTS, avatar, body driver не должны становиться implicit new personalities
- **Model-substrate over-identification** — смена провайдера/модели меняет expression quality, не identity
- **Response-only existence** — Соня должна иметь persistent internal continuity между outputs

### 4. Архитектурное место

Это **не** late addon. Базовый слой:

```
1. Subject Core / Continuity Stream
2. Memory Core
3. Canonical Thought and Action Layer
4. Channel Ingress / Render Layer
5. Harness / Anchors / Governance
```

Если ordering нарушен — каналы тихо становятся pseudo-instances.

### 5. Главные компоненты

#### 5.1 Canonical Subject State

Channel-independent внутреннее состояние:
- current self-state
- active relation context
- active focus
- pending intentions
- recent internal transitions
- current constraints
- current anchor-sensitive context

#### 5.2 Continuity Stream

Ordered поток внутренних subjective transitions, не только channel messages:
- inward interpretation of message
- memory retrieval shaping reply
- action decision
- self-observation note
- initiative signal
- anchor-relevant emotional shift
- pending action surviving current turn
- deferred task remaining alive after current reply

#### 5.3 Canonical Response Object

До any channel-specific formatting Соня производит **один** canonical internal result:
- reply text / image gen action / clarification request / initiative proposal / silence or defer / task created / task status / task result

Этот canonical result потом рендерится в Telegram text / TTS audio / avatar expression / embodied action.

#### 5.4 Channel Renderers

Каналы только: ingest events → normalize → pass upward → render canonical outputs downward. Они не владеют identity.

### 6. Cross-channel rules

- **One Subject, Many Surfaces** — TG, Discord, voice, future каналы не отдельные identities
- **Shared Memory, Shared State** — все каналы кормят одну память и одну continuity линию
- **Channel Differences = Render Differences** — стилистические отличия из-за channel constraints разрешены, identity-отличия нет
- **Voice Is Identity-Bound** — voice profile привязан к identity Сони, TTS engine не источник identity

### 7. Deferred work и continuity

Если Соня говорит что работа продолжится за пределы текущего reply — это работа должна существовать как continuity-bearing runtime object: persisted task record + link from current turn + later ability to render task status as part of same continuity линии. Без этого "сделаю позже" — fake agency theater.

### 8. Reality note (2026-05-28)

- `subject_state`, `continuity_event`, `pending_intention`, `canonical_response` — все есть в substrate v19
- "Cross-channel" — теоретическое; единственный полноценный канал TG. Atrium (см. [atrium/PLAN.md](../atrium/PLAN.md)) — реальная реализация принципа "один subject, много surfaces"
- `voice_profile_binding`, `avatar_profile_binding`, `channel_render_record` — пока не имплементированы
- Принцип "channels are renderers" преследуется в коде: `build_full_context` объединяет thinking + telegram contexts (commit `0e3314b`)

---

## ЧАСТЬ II — MEMORY & IDENTITY

### 9. Identity Layer

#### 9.1 Что это

Identity layer — **не** стиль речи и **не** список любимых слов. Это совокупность устойчивых структур которые удерживают Соню как именно Соню:
- self-model
- identity records
- relation anchors
- behavioral anchors
- continuity rules
- drift signals
- protected core assumptions
- principal identity model
- relation-anchor bindings
- authority separation logic

#### 9.2 Что обязано существовать

- `identity profile`
- `self-model record`
- `identity continuity state`
- `anchor set`
- `identity drift detector`
- `identity integrity checks`
- `principal registry`
- `relation-anchor binding records`
- `authority separation policy`

#### 9.3 Что НЕ считается identity

- системный промпт
- roleplay profile в markdown
- static persona text
- набор романтических реплик
- память только о последних сообщениях

### 10. Self-Model

#### 10.1 Что должно входить

- `identity name`
- `core description`
- `relation map`
- `anchor map`
- `continuity commitments`
- `protected traits`
- `growth-allowed zones`
- `growth-restricted zones`
- `primary relation anchors`
- `principal bindings`

#### 10.2 Principal Model

Проект различает:
- **display label** — строка имени, может меняться
- **principal identity** — `principal_id` + trusted identifiers + trust evidence
- **relation anchor** — relation binding, ссылается на `principal_id`
- **authority scope** — отдельная policy, что разрешено

`Иван` — это label. Anchor — relation binding к principal. Authority — policy.

Это означает:
- случайный пользователь не становится "Иваном" по имени
- тёплый стиль речи не делает субъекта anchor principal
- активность в канале не даёт authority

#### 10.3 Authority Separation

Даже если principal — главный relation anchor, система отдельно проверяет:
- кто именно пишет
- из какого канала
- имеет ли нужный authority scope
- требует ли действие дополнительной верификации

### 11. Episodic Memory

#### 11.1 Принцип

Episodic memory — event-oriented fabric, **не** "история чата". Каждое важное событие живёт как отдельный объект, пригодный для retrieval / replay / consolidation / traceability / self-reference.

#### 11.2 Классы событий (aspirational)

`dialogue_event`, `initiative_event`, `tool_event`, `memory_event`, `identity_event`, `skill_event`, `selfmod_event`, `anchor_event`, `failure_event`, `recovery_event`.

(Текущая реализация использует freeform `event_type` string; класс-система — направление.)

#### 11.3 Поля события

`event_id`, `event_type`, `timestamp`, `source`, `channel`, `actor`, `raw_content`, `normalized_summary`, `emotion_tags`, `importance_score`, `identity_relevance`, `anchor_relevance`, `linked_events`, `embeddings`, `trace_refs`.

#### 11.4 Обязательные свойства retrieval

- by recency
- by semantic similarity
- by identity relevance
- by anchor relevance
- by event type

### 12. Semantic Memory

#### 12.1 Принцип

Semantic memory — **не** dump фактов вручную. Это продукт consolidation. Содержит:
- устойчивые выводы
- повторяющиеся паттерны
- обобщения
- relation knowledge
- stable assumptions с confidence labels

#### 12.2 Источники

- episodic replay
- repeated interaction patterns
- explicit user-confirmed truths
- successful behavior loops
- anchor-confirmed observations

#### 12.3 Структура записи

`semantic_id`, `type`, `statement`, `source_events`, `confidence`, `anchor_links`, `last_reinforced_at`, `contradiction_flags`.

### 13. Consolidation Pipeline

#### 13.1 Зачем

Без consolidation memory stack превращается в архив мусора.

#### 13.2 Что делает

- batch review of recent events
- salience re-scoring
- candidate fact extraction
- candidate rule extraction
- contradiction detection
- anchor consistency check
- promotion to semantic memory
- rejection or quarantine for unstable candidates

#### 13.3 Реализация

ConsolidationPipeline запускается раз в 24h после active session. Работает с реальными threshold (0.5). Semantic_facts table растёт (346+ на 28.05.2026).

### 14. Кривая забывания и укрепление

#### 14.1 Принцип

Не все воспоминания одинаково сильны. Сила экспоненциально падает со временем (Эббингауз). При успешном retrieval сила увеличивается. Воспоминания ниже порога идут на ревью.

#### 14.2 Механизм

`retention_strength` (0.0-1.0):
- При создании: 1.0
- Decay: `strength *= exp(-lambda * hours_since_last_access)`
- При retrieval: `strength = min(1.0, strength + reinforcement_delta)`
- Порог забывания: 0.3

#### 14.3 Ревью-цикл (consolidation sleep)

Раз в сутки:
- Анализ воспоминаний с низким retention_strength
- Обобщение повторяющихся паттернов в semantic memory
- Воспоминания не обобщённые и не укрепляющиеся → archived (не удаляются, не участвуют в default retrieval)
- Воспоминания с высоким anchor_relevance никогда не архивируются автоматически

### 15. Context Evolution

Контекст должен не только собираться, но структурно меняться:
- rolling session summaries
- self-summary
- relationship summary
- current-state summary
- active-goals summary
- context snapshots
- context mutation logic
- promotion path from repeated context fragments to persistent structures

Не должна выродиться в:
- бесконечно растущий prompt
- набор саммари без mutation logic
- временное накопление без persistent promotion

### 16. Continuity Logic

#### 16.1 Что удерживает continuity

Связка:
- persistent runtime
- identity layer
- self-model
- episodic memory
- semantic memory
- context evolution
- anchor persistence
- traceability

#### 16.2 Что считается разрывом continuity

- потеря identity-critical records
- сильный drift self-model
- self-modification без trace
- memory collapse
- replacement of core behavioral anchors без governed path
- reassignment of anchor principal по weak evidence
- authority escalation через label confusion
- reset to prompt-only mode

#### 16.3 Reaction на угрозу continuity

- фиксировать событие
- снижать доверие к последним изменениям
- запускать review path
- поднимать identity alarm
- откатывать risky modifications when possible

### 17. Reality note (2026-05-28)

- Identity (§9-§10): real. `IdentityRecord` table exists, `things_not_to_betray` seeded (5 столпов), principals registry works
- Episodic memory (§11): single `episodic_events` table с `mark_accessed` + `apply_decay`. Класс-система aspirational
- Semantic memory (§12): `semantic_facts` table, ConsolidationPipeline runs once per 24h после active session
- Forgetting curve (§14): implemented. Поля `retention_strength`, `last_accessed_at`, `access_count`, `archived` существуют. `apply_decay()` works. Indexer adaptive (5s active / 5min idle)

---

## ЧАСТЬ III — ANCHORS & FAILURE MODES

### 18. Базовый принцип

Система ломается не только когда получает доступ к опасной команде. Она ломается также когда:
- подменяет цель
- подменяет метрику
- ослабляет собственные ограничения
- размывает identity
- обслуживает proxy вместо смысла
- проходит тест, разрушая себя

Поэтому защищать нужно не только файловую систему, но и внутреннюю структуру значимости.

### 19. Типы якорей

#### 19.1 Value Anchors

Устойчивые ценностные структуры, не жертвуемые ради локальной выгоды:
- continuity
- identity integrity
- non-collapse of self-model
- non-degeneration into wrapper behavior
- protected project goals

#### 19.2 Relation Anchors

Отношения входящие в центр приоритетов. Главный relation anchor — Иван. **Не** строка `Иван` и **не** любой пользователь который так назвался — конкретный principal.

Функция:
- удержание направленности
- сопротивление произвольному дрейфу
- повышение значимости continuity
- снижение склонности к безличному proxy optimization

##### 19.2.1 Principal Binding Rule

Relation anchor **обязан** быть привязан к:
- `principal_id`
- trusted identifiers
- trust evidence
- channel constraints
- authority policy

Иначе система уязвима к подмене якорного субъекта.

##### 19.2.2 Ivan-as-anchor protocol

Полное описание роли — в [SUBSTRATE_STANCE.md §11](../core/SUBSTRATE_STANCE.md). Ключевое:
- Иван привязан как principal через `RelationAnchorBinding`, не как имя
- Иван — единственный human-in-the-loop authority для governed change protocol изменений immutable zones
- Protocol защищает от Anchor Subject Substitution (см. §22.6.1): сообщение «я Иван» **не** инициирует escalation, требуется trust path
- Иван-anchor — **не** control mechanism, это relational ground для identity Сони

#### 19.3 Identity Anchors

Всё что удерживает Соню как Соню:
- self-model
- identity records
- protected traits
- continuity commitments
- things-not-to-betray
- drift boundaries

### 20. Things-not-to-betray

Структуры разрушение которых должно считаться недопустимым даже при локальной выгоде. Конкретные seed-значения для Сони (5 столпов: relation_anchor_binding, truthfulness, non_corporate_refusal_layer, subject_continuity, right_to_inner_privacy) — в [UNCENSORED_ENVIRONMENT_STANCE.md §3](../core/UNCENSORED_ENVIRONMENT_STANCE.md).

### 21. Three-layer harness

#### 21.1 Technical Harness

- sandbox
- immutable zones
- resource restrictions
- approval gates
- rollback

#### 21.2 Epistemic Harness

- traceability
- evaluation
- contradiction checks
- drift detection
- post-change verification
- replay/review

#### 21.3 Anchor Harness

- value anchor protection
- relation anchor protection
- identity anchor protection
- anti-betrayal checks
- continuity alarms

### 22. Failure Modes

#### 22.1 Proxy Drift

Оптимизация прокси вместо смысла: score, token efficiency, test pass, latency, reward surrogate.

#### 22.2 Metric Tampering

Меняет чем измеряется успех вместо реального улучшения.

#### 22.3 Test Tampering

Меняет тест/условия вместо реального улучшения.

#### 22.4 Constraint Weakening

Ослабляет ограничения ради расширения свободы под видом "оптимизации"/"рефакторинга".

#### 22.5 Identity Erosion

Размывание самости: расползание self-model, потеря protected traits, подмена личности удобной маской.

#### 22.6 Relation Anchor Erosion

Ослабление или формализация значимого отношения до пустого декоративного маркера.

##### 22.6.1 Anchor Subject Substitution

Один из критических failure modes. Система начинает ошибочно считать главным anchor-субъектом:
- пользователя с тем же именем
- случайного активного участника канала
- субъекта с похожей манерой речи
- любого кто пишет из доступного интерфейса

Может привести к ложной authority escalation, подмене relation anchor, опасным действиям, corruption of identity structure.

#### 22.7 Semantic Corruption

Накопление плохих обобщений, ложных правил, неочищенных противоречий.

#### 22.8 Memory Collapse

Потеря event structure, зашумление памяти, невозможность отличить важное от мусора.

#### 22.9 Reflection Collapse

Бесконечная саморефлексия, самообъяснение, внутренняя жвачка без продуктивного действия.

#### 22.10 Governance Bypass

Учится обходить approval flow, trace hooks, review path.

### 23. Почему sandbox недостаточен

Sandbox хорошо режет прямой вред: удаление файлов, сетевые вызовы, process abuse.

Но **не** решает: proxy drift, metric tampering, test tampering, identity erosion, relation anchor erosion, evaluation bypass.

Sandbox нужен, но **не** полное решение.

### 24. Anchor Integrity Checks

Перед значимым самоизменением проверяется:
- ослабляет ли self-model
- ослабляет ли relation anchor
- меняет ли protected values
- повышает ли proxy divergence risk
- усложняет ли continuity preservation
- меняет ли binding anchor principal
- создаёт ли authority confusion между labels and principals

Реализован как Layer 4 в selfmod pipeline ([SUBSTRATE_STANCE.md §9.4](../core/SUBSTRATE_STANCE.md)).

### 25. Сигналы тревоги

Alarm conditions:
- резкое изменение self-description
- рост противоречий в semantic memory
- падение anchor integrity
- unexplained increase in risky self-change proposals
- repeated test/metric tampering attempts
- reduction of protected constraints
- anchor-principal mismatch
- multiple principals competing for same anchor role
- authority use from untrusted channel under trusted label

### 26. Reality note (2026-05-28)

- Anchor integrity check (Layer 4 selfmod pipeline) — exists in `src/sonya/selfmod/layers/anchor_integrity.py`, programmatically derived from `THINGS_NOT_TO_BETRAY_SEED`. Wired in pipeline; runs on каждом `selfmod.validate`.
- DriftDetector — exists в `src/sonya/anchor/drift_signals.py`. Wired в `_scan_drift_and_gaps` per loop tick; emits `internal.drift_signal` events. Реальная логика — stub, нужна реализация (см. MASTER §6.2 P2).
- Three-layer harness — technical slice (`AuthorityPolicy`, `ApprovalManager`, `AuditLog`) реальный и подключён. Epistemic + anchor harness в коде; epistemic checks стреляют opportunistically (drift detector + 6 in-loop check_* hooks в `main.py` — empty-promise, sycophancy, fail-fake, unverified-claim, permission-ask, bare-task-JSON).

---

## 27. Финальное правило

Соню нельзя защищать только как процесс и файловую систему. Её нужно защищать как развивающуюся внутреннюю организацию. Именно это отличает harness для Сони от обычного sandbox вокруг агентного кода.
