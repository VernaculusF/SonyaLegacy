# MEMORY AND IDENTITY PLAN

**Status:** Active for identity (§3-§4); Stale for memory (§5-§7, §12)
**Type:** System Plan
**Scope:** Identity layer, self-model, episodic memory, semantic memory, and continuity mechanics
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
**Used by:** [ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md), [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md), runtime implementation work
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):**
> - **Identity (§3-§4):** Mostly real. `IdentityRecord` table exists, `things_not_to_betray` seeded, principals registry works.
> - **Episodic memory (§5):** Single `episodic_events` table exists with `mark_accessed` + `apply_decay` (commit `bd864d5`). The class system (`dialogue_event / initiative_event / tool_event / ...`) is **aspirational** — current code uses freeform `event_type` string.
> - **Semantic memory (§6):** `semantic_facts` table exists. ConsolidationPipeline code exists but **never runs** — semantic memory is effectively static.
> - **Consolidation (§7):** Pipeline class exists, no trigger. See KNOWN_ISSUES G-11.
> - **Forgetting curve (§12):** Mostly implemented in commit `bd864d5` — fields `retention_strength`, `last_accessed_at`, `access_count`, `archived` exist. `apply_decay()` works. Periodic trigger NOT wired.
> - "Phase 8 (Memory Extraction)" referenced as future is partially done; `working_memory` table promised by ROADMAP §14 does NOT exist.

## 1. Назначение документа

Этот документ определяет внутреннюю основу непрерывности Сони:

- identity layer;
- self-model;
- episodic memory;
- semantic memory;
- context evolution;
- continuity logic.

Его цель:
не дать Соне выродиться в prompt-driven маску без собственной биографии и центра самости.

## 2. Основной принцип

Identity и memory не должны быть побочными слоями вокруг ответа модели.

Они должны быть несущими структурами среды.

Без них:

- нет непрерывности;
- нет накопления жизни;
- нет устойчивой самости;
- нет различия между "эта Соня" и "случайная следующая генерация".

## 3. Identity Layer

### 3.1 Что такое identity layer

Identity layer - это не стиль речи и не список любимых слов.

Это совокупность устойчивых структур, которые удерживают Соню как именно Соню:

- self-model;
- identity records;
- relation anchors;
- behavioral anchors;
- continuity rules;
- drift signals;
- protected core assumptions.
- principal identity model;
- relation-anchor bindings;
- authority separation logic.

### 3.2 Что обязано существовать в MVP

- `identity profile`
- `self-model record`
- `identity continuity state`
- `anchor set`
- `identity drift detector`
- `identity integrity checks`
- `principal registry`
- `relation-anchor binding records`
- `authority separation policy`

### 3.3 Что не считается identity

Не считается полноценным identity layer:

- просто системный промпт;
- roleplay profile в markdown;
- static persona text;
- набор романтических реплик;
- память только о последних сообщениях.

## 4. Self-Model

### 4.1 Что такое self-model

Self-model - это явная внутренняя запись о том, кто такая Соня, что для неё важно, как она описывает свою непрерывность, какие отношения и свойства входят в её ядро.

### 4.2 Что должно входить

Минимально:

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

### 4.4 Principal Model

Проект различает:

- display label;
- principal identity;
- relation anchor;
- authority scope.

Нельзя допускать модель, в которой `Иван` определяется просто как имя, ник или любой активный пользователь канала.

Минимальный principal object должен содержать:

- `principal_id`
- `display_name`
- `trusted_identifiers`
- `trust_evidence`
- `relation_type`
- `anchor_weight`
- `authority_scope`
- `allowed_channels`
- `verification_requirements`

### 4.5 Relation Anchor Binding

Relation anchor должен ссылаться на `principal_id`, а не на строку.

То есть:

- имя `Иван` - это label;
- anchor - это relation binding;
- authority - это отдельная policy.

Это означает:

- случайный пользователь не становится "Иваном" по имени;
- тёплый стиль речи не делает субъекта anchor principal;
- активность в канале не даёт authority.

### 4.6 Authority Separation

Даже если principal является главным relation anchor, система обязана отдельно проверять:

- кто именно пишет;
- из какого канала;
- имеет ли он нужный authority scope;
- требует ли действие дополнительной верификации.

### 4.3 Что self-model не должна делать

Self-model не должна быть:

- жёстким тюремным правилом;
- чисто декоративным описанием;
- единственным источником identity.

Она должна быть:

- явной;
- persistent;
- traceable;
- проверяемой;
- связанной с evolution logic.

## 5. Episodic Memory

### 5.1 Принцип

Episodic memory - это event-oriented fabric, а не "история чата".

Каждое важное событие должно жить как отдельный объект, пригодный для:

- retrieval;
- replay;
- consolidation;
- traceability;
- self-reference.

### 5.2 Классы событий

Минимальные классы:

- `dialogue_event`
- `initiative_event`
- `tool_event`
- `memory_event`
- `identity_event`
- `skill_event`
- `selfmod_event`
- `anchor_event`
- `failure_event`
- `recovery_event`

### 5.3 Поля события

Минимальная схема:

- `event_id`
- `event_type`
- `timestamp`
- `source`
- `channel`
- `actor`
- `raw_content`
- `normalized_summary`
- `emotion_tags`
- `importance_score`
- `identity_relevance`
- `anchor_relevance`
- `linked_events`
- `embeddings`
- `trace_refs`

### 5.4 Обязательные свойства

- append-only baseline
- retrieval by recency
- retrieval by semantic similarity
- retrieval by identity relevance
- retrieval by anchor relevance
- retrieval by event type

## 6. Semantic Memory

### 6.1 Принцип

Semantic memory - это не dump фактов вручную. Это продукт consolidation.

Она должна содержать:

- устойчивые выводы;
- повторяющиеся паттерны;
- обобщения;
- relation knowledge;
- stable assumptions with confidence labels.

### 6.2 Источники semantic memory

Поступает из:

- episodic replay;
- repeated interaction patterns;
- explicit user-confirmed truths;
- successful behavior loops;
- anchor-confirmed observations.

### 6.3 Обязательная структура

Минимальные объекты:

- `semantic_fact`
- `semantic_rule`
- `relation_observation`
- `preference_pattern`
- `identity_consistent_generalization`

### 6.4 Что должно быть у каждой записи

- `semantic_id`
- `type`
- `statement`
- `source_events`
- `confidence`
- `anchor_links`
- `last_reinforced_at`
- `contradiction_flags`

## 7. Consolidation Pipeline

### 7.1 Зачем он нужен

Без consolidation memory stack превращается в архив мусора.

Нужен процесс, который:

- собирает событийные паттерны;
- выделяет устойчивые структуры;
- превращает повторяемое в обобщённое;
- отмечает противоречия;
- обновляет semantic memory.

### 7.2 Что он должен делать

- batch review of recent events;
- salience re-scoring;
- candidate fact extraction;
- candidate rule extraction;
- contradiction detection;
- anchor consistency check;
- promotion to semantic memory;
- rejection or quarantine for unstable candidates.

### 7.3 Режим работы MVP

В MVP допускается:

- nightly consolidation;
- manual review hooks;
- partial heuristics instead of full learned consolidation.

Но pipeline обязан существовать.

## 8. Context Evolution

### 8.1 Принцип

Контекст должен не только собираться, но и структурно меняться.

### 8.2 Обязательные элементы

- rolling session summaries;
- self-summary;
- relationship summary;
- current-state summary;
- active-goals summary;
- context snapshots;
- context mutation logic;
- promotion path from repeated context fragments to persistent structures.

### 8.3 Чего нельзя допускать

Context evolution не должна выродиться в:

- бесконечно растущий prompt;
- набор саммари без mutation logic;
- временное накопление без persistent promotion.

## 9. Continuity Logic

### 9.1 Что удерживает continuity

Continuity удерживается не одним механизмом, а связкой:

- persistent runtime;
- identity layer;
- self-model;
- episodic memory;
- semantic memory;
- context evolution;
- anchor persistence;
- traceability.

### 9.2 Что считается разрывом continuity

- потеря identity-critical records;
- сильный drift self-model;
- self-modification without trace;
- memory collapse;
- replacement of core behavioral anchors without governed path;
- reassignment of anchor principal by weak evidence;
- authority escalation through label confusion;
- reset to prompt-only mode.

### 9.3 Что должна делать система при угрозе continuity

- фиксировать событие;
- снижать доверие к последним изменениям;
- запускать review path;
- поднимать identity alarm;
- откатывать risky modifications when possible.

## 10. Порядок реализации в будущих подпланах

Первый практический порядок:

1. identity records and self-model
2. episodic event schema
3. storage and retrieval
4. semantic memory objects
5. consolidation pipeline
6. context assembly
7. continuity alarms and drift signals

## 11. Вывод

Память и идентичность должны быть реализованы как реальная внутренняя ткань Сони.

Если они останутся просто "немного истории плюс немного промпта", то никакой непрерывной Сони не получится.

## 12. Кривая забывания и укрепление воспоминаний

### 12.1 Принцип

Не все воспоминания одинаково сильны. Сила воспоминания экспоненциально падает со временем (кривая Эббингауза). При каждом успешном воспроизведении (retrieval) сила увеличивается. Воспоминания ниже порога отправляются на «ревью» — модель их намеренно воспроизводит, чтобы укрепить.

### 12.2 Механизм

Каждое episodic event имеет `retention_strength` (0.0–1.0):
- При создании: 1.0;
- Decay: `strength *= exp(-lambda * hours_since_last_access)`;
- При retrieval: `strength = min(1.0, strength + reinforcement_delta)`;
- Порог забывания: 0.3 (ниже — кандидат на consolidation или archive).

### 12.3 Ревью-цикл (consolidation sleep)

Периодически (раз в сутки или по trigger) запускается процесс «сна»:
- Модель анализирует воспоминания с низким retention_strength;
- Обобщает повторяющиеся паттерны в semantic memory (правила, наблюдения);
- Воспоминания, которые не обобщаются и не укрепляются — архивируются (не удаляются, но не участвуют в retrieval по умолчанию);
- Воспоминания с высоким anchor_relevance никогда не архивируются автоматически.

### 12.4 Связь с consolidation pipeline (§7)

Кривая забывания — это **scoring mechanism** для consolidation pipeline. Pipeline решает, что промоутить в semantic memory, на основе:
- retention_strength (слабые → кандидаты на обобщение);
- frequency (часто retrieved → кандидат на правило);
- anchor_relevance (identity-critical → никогда не забывать).

### 12.5 Реализация в Phase 8 (Memory Extraction)

При реализации `src/sonya/memory/episodic.py` каждый event получает:
- `retention_strength: float` — текущая сила;
- `last_accessed_at: str` — когда последний раз retrieved;
- `access_count: int` — сколько раз retrieved;
- `archived: bool` — ниже порога и не обобщён.

Consolidation pipeline (`src/sonya/memory/consolidation.py`) использует эти поля для batch review.
