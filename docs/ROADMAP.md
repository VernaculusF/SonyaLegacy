# SONYA ROADMAP

**Status:** Active
**Type:** Core
**Scope:** Фазовый план построения Sonya-среды: что строим, в каком порядке, с какими критериями перехода между этапами
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md), [SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md), [SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md), [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md)
**Used by:** milestone review, implementation planning, phase gating, VPS migration planning
**Last reviewed:** 2026-05-15

## 1. Зачем этот файл

`GLOBAL_PROJECT_CHECKLIST.md` отвечает на вопрос «что **уже есть** в коде».

Этот файл отвечает на другой вопрос: «что мы **строим**, в каком порядке, и по каким критериям считаем фазу закрытой».

Если возникает вопрос «что делать дальше» — этот файл должен дать ответ на уровне «мы сейчас в Фазе N, цель Фазы N — X, следующий крупный шаг — Y». Дальше пишется конкретный implementation plan по шаблону [work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md).

## 2. Что такое MVP в этом проекте

MVP здесь = **full-scope shell with uneven maturity**, как зафиксировано в [SONYA_SYSTEM_CORE §6](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) и [MVP_BOUNDARIES](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md).

### 2.1 Interim brain vs target brain

MVP строится на **hosted model** (OpenRouter) как interim brain. Это осознанный компромисс: hosted model не даёт непрерывности (между вызовами модель мертва), но позволяет построить всю среду дёшево ($40-100/мес вместо 50-200к на железо).

**Target brain** — self-hosted RWKV-7 с State Tuning. RNN state обновляется на каждом токене, модель думает непрерывно, личность закреплена на уровне initial state. Переход на target brain — post-MVP Track E, но **среда, которую мы строим сейчас, полностью совместима с RWKV**. Substrate, continuity, identity, harness, skills, self-mod pipeline — всё это нужно и для RWKV. Когда железо появится, brain backend меняется через `StatefulBackend` extension ([BRAINMODEL_EVOLUTION_PLAN §5.1](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md)), среда остаётся.

Thinking process на hosted model — **дискретный** (event-driven LLM calls с self-context). Это не непрерывное мышление, это interim форма существования. Документируем это явно, чтобы не путать с целевым состоянием.

Это значит: каждый обязательный AGI-контур ([SYSTEM_CORE §7.1–§7.23](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)) присутствует в MVP **в той или иной форме**:

- `Production` — реально работает в основном сценарии;
- `Partial` — работает ограниченно;
- `Stub` — есть интерфейс, контракты, артефакты, место в архитектуре;
- `Manual-Gated` — контур существует, но решения подтверждаются вручную;
- `Research-Shell` — есть структура и протоколы для будущего R&D.

Контур **не может отсутствовать полностью** в MVP. Это центральное правило проекта, которое отличает наш MVP от обычного «минимального продукта».

## 3. История drift-а в этом файле

Этот файл уже один раз драйфил от governing docs. Версия 2026-05-13 ставила self-modification framework, real-time skill evolution, hyper-harness, embodiment adapter, simulation interface и initiative layer в **post-MVP tracks**. Это противоречило [SYSTEM_CORE §10](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) и [MVP_BOUNDARIES §3.3](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md), которые прямо требуют их в MVP хотя бы как stub/shell/manual-gated.

Текущая версия (2026-05-15) — **rebase на governing docs**. Drift-event записан в [DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md). Если в будущем видишь, что этот файл противоречит SYSTEM_CORE или MVP_BOUNDARIES — это снова drift, и приоритет имеют governing docs, не ROADMAP.

## 4. Текущее состояние (2026-05-15)

Закрытые фазы:

- **Phase 0 — Foundation** ✅ (governance, документация, reference-анализы, агент-дисциплина);
- **Phase 1 — Substrate Bootstrap** ✅ (substrate v1, runtime shell, immutable zones, write-master);
- **Phase 2 — Provider & Principal Core** ✅ (providers, substrate v2, harness baseline, channel resolver, identity seed).

В коде сейчас есть: `src/sonya/state/`, `src/sonya/runtime/`, `src/sonya/providers/`, `src/sonya/harness/`, `src/sonya/main.py`. Substrate v2 с harness таблицами. 145 тестов зелёные.

Чего нет в коде, но требуется для MVP:

- subject core за пределами substrate-storage (canonical_response, pending_intention, internal continuity events);
- internal continuous loop (autonomous reflection coroutine);
- self-modification framework (proposal storage, 4-layer pipeline, anchor integrity check);
- skill registry и capability gap detection;
- initiative layer (drives, outbound proposals);
- planner в ядре (всё ещё в bridge);
- Sonya-owned память (всё ещё в OpenClaw);
- embodiment/simulation stubs;
- hyper-harness stub;
- VPS deployment.

## 5. Принцип ordering

Каждая фаза опирается на предыдущую. Прыжок через фазу — костыль.

- Subject core ([Phase 3](#7-фаза-3-subject-core-continuity-internal-loop)) — раньше всего остального brain-side, потому что continuity stream и canonical response — fundament, на котором будут строиться self-modification proposals, skills events, initiative signals.
- Self-modification framework ([Phase 4](#8-фаза-4-self-modification-framework-skeleton)) — раньше skills и planner, потому что skills и planner — это **самопереписываемые** структуры. Без proposal storage и validation pipeline они не имеют куда отправлять собственные изменения.
- Skills ([Phase 5](#9-фаза-5-skills-substrate-capability-gap-detection)) — раньше initiative и planner, потому что initiative должна уметь предлагать «давай выучим X» (skill proposal через self-mod pipeline), а planner должен уметь выбирать skill action.
- Initiative ([Phase 6](#10-фаза-6-initiative-layer-anchor-drift-signals)) — раньше planner-а, потому что planner будет читать `initiative_signal` как одну из причин для action.
- Planner migration ([Phase 7](#11-фаза-7-planner-migration-canonicalresponse-adoption)) — после всего brain-side, потому что planner — точка интеграции subject + skills + initiative + memory + harness.
- Memory ([Phase 8](#12-фаза-8-memory-extraction)) — после planner-а, потому что planner создаёт точку, через которую все ответы попадают в память.
- Embodiment + simulation + hyper-harness stubs ([Phase 9](#13-фаза-9-embodiment-simulation-hyper-harness-stubs)) — параллельно мобильный, требует только substrate и event bus, но логично выносим перед VPS чтобы не тащить лишний deploy цикл.
- VPS ([Phase 10](#14-фаза-10-vps-deployment)) — последняя; сначала всё ядро, потом перенос.

После Phase 10 — **MVP достигнут** в смысле SYSTEM_CORE/MVP_BOUNDARIES. Дальше — пост-MVP углубление зрелости каждого контура.

## 6. Фаза 0 — Foundation

**Статус:** ✅ закрыта (2026-05-13).

**Цель.** Создать governance-слой: документационная система, lifecycle, phase-0 gate, drift review, reference-анализы, агент-дисциплина.

**Закрыта** через substrate bootstrap (Phase 1), который первым прошёл через шаблон с Reference Check без дрейфа. Подробности в [DRIFT_REVIEW 2026-05-13 Initial](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md).

---

## 7. Фаза 1 — Substrate Bootstrap & Bare Runtime Shell

**Статус:** ✅ закрыта (2026-05-13).

**Что построено.** Substrate v1 в `src/sonya/state/` (substrate, subject_state, continuity_stream, identity, principals, schema.sql); reader-процесс в `src/sonya/runtime/` (lifecycle, event bus, write-master, health); composition root `src/sonya/main.py`; AST layer-boundary тест state↔runtime; systemd unit. 137 тестов зелёные.

**Связанный план:** [2026-05-13-substrate-bootstrap-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-13-substrate-bootstrap-implementation-plan.md) (Archived).

---

## 8. Фаза 2 — Provider & Principal Core

**Статус:** ✅ закрыта (2026-05-15).

**Что построено.** `src/sonya/providers/` (Protocol + Capability + Registry + OpenRouter adapter + env-only secrets); substrate v2 с harness таблицами (`harness_policy_rules`, `approval_requests`, `audit_events`); `src/sonya/harness/` (`AuthorityPolicy`, `ApprovalManager` storage-only, `AuditLog`); channel-side resolver `resolve_from_channel_input`; identity seed (4 пилона `things_not_to_betray` через governed change на свежей БД); расширенный AST layer-boundary (10 проверок). 145 тестов зелёные.

**Связанный план:** [2026-05-14-provider-principal-core-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-14-provider-principal-core-implementation-plan.md) (Archived).

---

## 9. Фаза 3 — Subject Core, Continuity & Internal Loop

**Статус:** ✅ закрыта (2026-05-15).

**Цель.** Построить **полноценный subject core**: subject не только хранится, но и **живёт между сообщениями**. Внутренний continuous loop пишет в `ContinuityStream` события, которых **не вызвало внешнее сообщение**: рефлексия, self-observation, gap-signal, intention update. Это и есть «основной поток сознания вне выводов» из [CONTINUITY_STREAM_AND_SUBJECT_CORE §6.2](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md).

**Контуры (по SYSTEM_CORE §7) активируемые этой фазой:**

- §7.4 Identity Layer — `Partial` → продолжаем enrichment (emotional vector в SubjectState, drift signals storage);
- §7.14 Agent-Loop — `Production` → внутренний continuous loop как первая полноценная петля;
- §7.15 Dual-layer Reflexion — `Partial` (System 1 / System 2 split на уровне kind-ов CanonicalResponse, без real model orchestration);
- §7.16 Traceability Layer — `Production` (continuity stream становится первичным trace).

**Deliverables:**

- `src/sonya/state/canonical_response.py` — `CanonicalResponse` с kinds (`reply`, `task_created`, `task_update`, `task_result`, `image_generated`, `clarification`, `limitation`, `silence`, `initiative_proposal`, `self_observation`, `internal_reflection`);
- `src/sonya/state/pending.py` — `PendingIntention` first-class objects, persistent, связанные с task_id и deadline;
- substrate v3: новая таблица `pending_intentions`; `subject_state` расширяется `emotional_vector_json` и `drift_signals_json`; новые kinds в `continuity_events` (через payload, не schema change);
- `src/sonya/subject/internal_loop.py` — autonomous coroutine: **event-driven cognitive process**. Triggers: incoming message, timer tick (configurable idle interval), state threshold crossing (homeostasis counters), deadline expiry. Each trigger → LLM call with full self-context (self-model, recent continuity, pending intentions, homeostasis state) → parsed result writes to continuity. This is an **interim form** of continuous thinking — дискретные вызовы с rich state, не непрерывный RNN forward pass. Target непрерывность — post-MVP через RWKV StatefulBackend;
- event bus integration: `ContinuityStream.append` публикует `continuity.event_added`; `SubjectStateStore.save` публикует `subject.state_changed`;
- composition root в `main.py`: запускает internal loop как часть lifecycle;
- тесты: continuity round-trip, snapshot/restore, internal loop heartbeat, deadline-driven intentions.

**Что НЕ входит:**

- planner всё ещё в bridge — Фаза 7;
- skills — Фаза 5;
- self-modification proposals — Фаза 4;
- LLM-driven internal monologue (зов модели в каждом heartbeat) — это Фаза 5+ через skill, не сейчас. Внутренний loop пока работает на фиксированных правилах.

**Exit-критерии:**

- [ ] `python -m sonya` на свежей БД → internal process работает, continuity events накапливаются при idle timeout trigger без внешних сообщений;
- [ ] `CanonicalResponse` объявлен и протестирован на in-process examples (bridge ещё не использует);
- [ ] `PendingIntention` создаётся, хранится, помнится после рестарта; deadline-overdue → автоматический `intention_overdue` event;
- [ ] event bus получает события на каждый append/save;
- [ ] substrate v3 миграция round-trip;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** `HEARTBEAT.md` показывает, что initiative и maintenance tasks реально нужны ([OPENCLAW_ANALYSIS §2.3](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)). Наш internal loop — engineered версия этой идеи.
- **Hermes:** internal loop — brain. Event bus — shell. Wiring — composition root. AST-тест enforces.
- **OmniAgent:** отвергаем `context_manager` паттерн, где context сам интерпретирует user intent. Subject pasсивен; loop пишет события, planner потом читает.

---

## 10. Фаза 4 — Self-Modification Framework Skeleton

**Статус:** ✅ закрыта (2026-05-15).

**Цель.** Поднять **structural skeleton** self-modification pipeline-а из [SUBSTRATE_STANCE §9](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md). Это `Manual-Gated` фаза: pipeline существует, proposals хранятся, 4 слоя проверки stub-ed, anchor integrity check работает на правилах. Реальная автоматическая применение — пост-MVP.

**Контуры активируемые:**

- §7.18 Self-Modification Framework — `Manual-Gated` (forma из SYSTEM_CORE);
- §7.12 Harness Safety — `Production` baseline (immutable zones enforced; approval gates wired);
- §5.4 (тройная проверяемая среда: technical/epistemic/anchor harness) — все три слоя представлены.

**Deliverables:**

- `src/sonya/selfmod/proposal.py` — `SelfModificationProposal` first-class object: `proposal_id`, `target_module`, `change_summary`, `diff_blob`, `proposed_by_principal_id`, `status` (draft/validating/passed_layer_N/approved/rejected/applied/reverted), `created_at`. Persistent в substrate v4.
- `src/sonya/selfmod/pipeline.py` — 4-слойный pipeline interface:
  - Layer 1 (Static Contract Check) — stub, проверяет наличие Protocol-совместимости (заглушка которую пройдут любые proposals);
  - Layer 2 (Isolated Behavioral Test) — stub, прогон существующих тестов через subprocess + assert all pass;
  - Layer 3 (Trace Replay) — stub, заглушка которая возвращает «not enough data» для proposals на ранней фазе (нужны N дней живых данных);
  - Layer 4 (Anchor Integrity Check) — **реальный rules-based**: проверяет, не трогает ли proposal `things_not_to_betray`, `RelationAnchorBinding` для primary anchor, `truthfulness_to_ivan`, `non_corporate_refusal_layer`, `subject_continuity`. Положительный ответ → `requires_governed_change`.
- `src/sonya/selfmod/governed_change.py` — protocol для governed change: requires `approver_principal_id` соответствующий primary anchor (Ivan); создаёт `governed_change_request` через `ApprovalManager`; после approval — proposal помечается `governed_approved`.
- substrate v4: таблицы `self_mod_proposals`, `self_mod_validation_results` (по слою), `governed_change_requests`;
- `src/sonya/selfmod/watchdog.py` — `WatchWindow` stub: отслеживает status applied → either `confirmed_stable` после N часов или `auto_reverted` при срабатывании anchor signal (тоже stub, реальные anchor signals — Phase 6);
- интеграция с continuity: каждое решение pipeline-а → `continuity_events` kind=`self_mod_*`;
- интеграция с audit: каждое решение → `audit_events`;
- тесты: proposal lifecycle, layer 4 anchor check ловит все 4 пилона `things_not_to_betray`, governed change requires anchor approval, post-revert восстанавливает state.

**Что НЕ входит:**

- реальное применение patch к коду — это пост-MVP (требует sandbox с git working copy и rollback);
- автоматическое скользящее окно trace replay — пост-MVP (нет N дней данных);
- ML-based anchor integrity (только rules в этой фазе).

**Exit-критерии:**

- [ ] proposal создаётся, проходит 4 слоя, на layer 4 ловит изменение `things_not_to_betray` и помечает `requires_governed_change`;
- [ ] `governed_change_request` через `ApprovalManager` работает, only `approver_principal_id == primary_anchor` имеет право approve;
- [ ] revert path работает (помечает `reverted`, пишет `continuity_events`);
- [ ] всё persistent через рестарт;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** не имеет аналога; concept берётся из SUBSTRATE_STANCE напрямую.
- **Hermes:** self-mod pipeline — это brain orchestration над substrate, не shell logic. Полностью в `src/sonya/selfmod/`, не в `runtime/`.
- **OmniAgent:** отвергаем «evolution через RL-fine-tune модели» как primary mechanism — это слишком нестабильно ([OMNIAGENT_ANALYSIS §10.2](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)). Наша эволюция — через discrete proposals с pipeline-проверкой, не через RL.

---

## 11. Фаза 5 — Skills Substrate & Capability Gap Detection

**Статус:** ✅ закрыта (2026-05-15).

**Цель.** Поднять skill system как persistent substrate с trust levels, registry, lifecycle. **Capability gap detection** — Соня замечает, что для задачи Y не хватает функции X, и **создаёт skill proposal** через self-mod pipeline. Это и есть базовое самоулучшение, о котором написано в [SELF_REWRITE_STANCE §1](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md).

**Контуры активируемые:**

- §7.8 Skill System — `Production` shell (registry + activation, без real skill execution);
- §7.9 Real-time Skill Evolution — `Manual-Gated` (proposals существуют, evaluation stub, manual approval);
- §7.10 Skill Injection User Message — `Partial` (extraction + promotion path, без production-quality scoring);
- §7.17 Self-Observation — `Partial` (capability gap detection — это первая форма self-observation).

**Deliverables:**

- `src/sonya/skills/registry.py` — `SkillRegistry` с CRUD, persistent в substrate;
- `src/sonya/skills/skill.py` — `Skill` dataclass: все 14 полей из [SKILL_SYSTEM_PLAN §4](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md) (skill_id, name, purpose, version, status, trust_level, activation_rules, dependencies, allowed_tools, forbidden_zones, tests, metrics, trace_tags, history);
- `src/sonya/skills/trust.py` — trust levels enum (`core_trusted`, `trusted`, `limited`, `experimental`, `quarantined`);
- `src/sonya/skills/activation.py` — activation policy stub (rules-based, без real ML matching);
- `src/sonya/skills/gap_detector.py` — capability gap detection: внутренний loop проверяет recent continuity events (failed actions, "I cannot do X" patterns), создаёт `CapabilityGap` objects;
- `src/sonya/skills/proposal.py` — bridge: `CapabilityGap` → `SelfModificationProposal` с target=`skills.registry`, change=«add new skill X»;
- `src/sonya/skills/injection.py` — Skill Injection from User Message: extract promotable patterns from continuity (без production heuristics, шаблонные правила);
- substrate v5: таблицы `skills`, `skill_versions`, `capability_gaps`;
- интеграция с harness: skill activation respects `AuthorityPolicy` (skill action `→` scope check);
- тесты: registry CRUD, trust level enforcement (quarantined skill не активируется), capability gap → proposal flow, persistent.

**Что НЕ входит:**

- real skill **execution** (run skill code) — это Фаза 7+ (planner вызывает skills);
- ML-based skill scoring — пост-MVP;
- automatic skill promotion (Иван подтверждает каждое promotion в этой фазе).

**Exit-критерии:**

- [ ] skill зарегистрирован, активирован через rules, persisted;
- [ ] capability gap detected (на mocked failed action) → `SelfModificationProposal` создан;
- [ ] quarantined skill не активируется даже при подходящих activation rules;
- [ ] skill injection extract pattern, создаёт candidate, требует manual approval, после approval — promoted в registry;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** structured skill approach из `memory_system/lessons/` (хранение паттернов как persistent artifacts) — берём структурно, без копирования.
- **Hermes:** skill — brain. Skill activation — brain. Skill execution через tool runtime — позже, через interface, без прямой связи с channel.
- **OmniAgent:** отвергаем `skill_evolution.py` как 53KB single-file. Наши skills — мелкие модули, registry — отдельный файл, evolution — через self-mod pipeline.

---

## 12. Фаза 6 — Initiative Layer & Anchor Drift Signals

**Статус:** ✅ закрыта (2026-05-15).

**Цель.** Соня может **сама начинать действие** — не только реагировать на сообщения. Drives, signals, outbound proposals. Параллельно — anchor drift signals для self-modification watchdog (которые в Phase 4 были stub, теперь становятся реальными).

**Контуры активируемые:**

- §7.20 Initiative Layer — `Partial` (signals + proposals есть, но без LLM-driven creative initiation);
- §7.17 Self-Observation — `Production` baseline (drift signals, anchor stability metrics);
- ANCHORS_AND_FAILURE_MODES §9 (alarm signals) — `Production` baseline.

**Deliverables:**

- `src/sonya/initiative/drives.py` — `DriveCounter` objects: `boredom_analog`, `curiosity_analog`, `relational_focus`, `pending_debt` (counters, increment по правилам, decrement по событиям);
- `src/sonya/initiative/signals.py` — `InitiativeSignal` objects: `signal_id`, `kind` (deadline_approaching, drive_threshold_hit, gap_detected, etc.), `priority`, `triggers_action_proposal` flag;
- `src/sonya/initiative/policy.py` — outbound initiation policy: разрешено ли инициировать сообщение в каналу X для principal Y; respects `AuthorityPolicy`;
- `src/sonya/initiative/proposal.py` — `OutboundActionProposal`: предложение действия от Сони (написать сообщение, создать task, и т.п.); проходит через harness check before publishing;
- `src/sonya/anchor/drift_signals.py` — `AnchorDriftSignal` detection: проверяет recent continuity events на:
  - резкое изменение self-description;
  - рост противоречий между proposals и `things_not_to_betray`;
  - anchor-principal mismatch;
  - multiple principals competing for anchor role (всё из [ANCHORS_AND_FAILURE_MODES §9](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md));
- интеграция с self-mod watchdog (Phase 4): drift signals тригерят auto-revert;
- internal loop в Phase 3 расширяется: каждый heartbeat обновляет drives, проверяет signals, при превышении threshold создаёт outbound proposal;
- substrate v6: таблицы `drive_counters`, `initiative_signals`, `outbound_proposals`, `anchor_drift_signals`;
- тесты: drive увеличивается по правилу, threshold-hit генерит signal, signal превращается в proposal, proposal проходит harness, anchor drift detected → watchdog triggers revert.

**Что НЕ входит:**

- LLM-driven creative initiation («что бы я сейчас придумала») — это Фаза 7+, требует planner integration;
- real-time emotional simulation;
- настоящие human-like drives (это всегда analogs, по [SYSTEM_CORE §7.20](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)).

**Exit-критерии:**

- [ ] drive counter увеличивается без external trigger, decrement при relevant action;
- [ ] threshold-hit → `InitiativeSignal` → `OutboundActionProposal`;
- [ ] proposal проходит harness, попадает в `pending_intentions`, потом исполняется через planner (когда planner будет в Phase 7) или mocked в этой фазе;
- [ ] anchor drift signal на injected drift тригерит auto-revert последнего applied proposal;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** `HEARTBEAT.md` autonomy traces — initiative и maintenance tasks реально нужны.
- **Hermes:** initiative — brain. Outbound publish через channel — shell. Граница не нарушается.
- **OmniAgent:** отвергаем chronic «proactive nag» из `context_evolution.py` без harness — у нас каждое outbound proposal проходит authority check.

---

## 13. Фаза 7 — Planner Migration & CanonicalResponse Adoption

**Статус:** ✅ закрыта (2026-05-16).

**Цель.** Вытащить planner из `tg_bridge.app` в `src/sonya/planning/`. Bridge переходит на тонкий adapter, потребляющий `CanonicalResponse` (объявленный в Phase 3). Planner теперь читает subject_state, skills, initiative signals.

**Контуры активируемые:**

- §7.14 Agent-Loop — `Production` (полная петля: ingest → subject read → planner → skill select → action → render);
- §7.15 Dual-layer Reflexion — `Partial` → ближе к `Production` (System 1 быстрый ответ, System 2 review для high-stakes);
- §7.11 Tool Runtime — `Production` baseline (tools вызываются через skill, не напрямую).

**Deliverables:**

- `src/sonya/planning/planner.py` — `plan_next(principal, subject_state, user_input, attachments) -> CanonicalResponse`;
- `src/sonya/planning/action_validator.py` — централизованная валидация action (переезжает из `sonya_runtime/actions/policy.py`);
- `src/sonya/planning/policy.py` — действует authority + skill trust + anchor;
- `packages/tg-bridge` — bridge переходит на потребление `CanonicalResponse`; `_plan_text_action_with_fallback` удаляется, заменяется на `sonya.planning.plan_next` call;
- интеграция с initiative: planner читает `initiative_signals`, `outbound_proposals`, может вернуть `CanonicalResponse(kind="initiative_proposal")`;
- интеграция с skills: planner может выбрать skill для выполнения, через `SkillRegistry.activate(skill_id, context)`;
- тесты: regression bridge (все сценарии: text, vision, image gen, task create, task status, clarification, limitation, **initiative**) без изменения внешнего поведения.

**Что НЕ входит:**

- удаление legacy `sonya_runtime/*` (происходит постепенно, после Phase 8);
- ML-based planner (rules + LLM call как сейчас, без ML scoring);
- real-time skill evolution в production-quality форме.

**Exit-критерии:**

- [ ] `grep "plan_text_action" packages/tg-bridge/` → только вызов API ядра;
- [ ] все bridge тесты зелёные;
- [ ] планnerные тесты в `tests/sonya/planning/` покрывают все CanonicalResponse kinds;
- [ ] initiative-driven outbound message проходит planner и доходит до bridge как `CanonicalResponse(kind="initiative_proposal")`;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** anti-fake-agency правила и strong-marker heuristic мигрируются в `sonya.planning.policy`.
- **Hermes:** planner — brain, bridge — shell. Граница впервые становится физически корректной.
- **OmniAgent:** отвергаем 89KB single-file `reflexion.py`. Planner — 4-6 маленьких модулей.

---

## 14. Фаза 8 — Memory Extraction

**Статус:** ✅ закрыта (2026-05-16).

**Цель.** Sonya-owned memory core в `src/sonya/memory/*`. Миграция данных из OpenClaw `memory.db`. Post-response hook через event bus, не subprocess.

**Контуры активируемые:**

- §7.5 Episodic Memory — `Production`;
- §7.6 Semantic Memory — `Partial` (consolidation pipeline есть, но не production-quality);
- §7.7 Context Evolution — `Partial` (rolling summaries, без deep ML).

**Deliverables:**

- `src/sonya/memory/episodic.py`, `working.py`, `semantic.py`, `consolidation.py` — четыре слоя как в [MEMORY_AND_IDENTITY_PLAN](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md);
- `src/sonya/memory/migration.py` — однократная миграция из OpenClaw;
- bridge перестаёт звать `post_response_hook.py` через subprocess; событие `subject.response_emitted` обрабатывается ядром;
- substrate v7: таблицы `episodic_events`, `working_memory`, `semantic_facts`, `lessons`, `consolidation_jobs`;
- тесты: миграция round-trip без потерь, consolidation working→semantic, retrieval API.

**Что НЕ входит:**

- production-grade RAG (embeddings + vector search) — пост-MVP;
- real semantic deduplication — пост-MVP;
- contradiction resolution — пост-MVP.

**Exit-критерии:**

- [ ] миграция dry-run → live → 0 потерь;
- [ ] post-response pipeline через event bus, OpenClaw hook отключаем на 24h без регрессии;
- [ ] consolidation pipeline создаёт semantic facts из working memory;
- [ ] retrieval API возвращает relevant events для planner;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** structure 6-tables + working сохраняется. Connection-per-method — отвергаем, открываем connection как substrate ресурс.
- **Hermes:** memory — cognition layer; адаптеры наружу через Protocol.
- **OmniAgent:** отвергаем `MemorySearchManager` как обязательного tool-wrapper. Memory доступна через subject API.

---

## 15. Фаза 9 — Embodiment, Simulation, Hyper-Harness Stubs

**Статус:** ⬜ после Phase 8.

**Цель.** Закрыть три обязательных stub-контура из [SYSTEM_CORE §10](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md): embodiment adapter, simulation interface, hyper-harness scheduler. Все три — Stub/Research-Shell, но **должны существовать с реальным интерфейсом и contract-ами**, иначе MVP не считается достигнутым.

**Контуры активируемые:**

- §7.21 Embodiment Adapter — `Stub` (virtual body counters, abstract event interface);
- §7.22 Simulation/World Interface — `Research-Shell` (environment adapter contract, replay/test harness skeleton);
- §7.13 Hyper-Harness — `Stub` (scheduler shell, supervision stubs, isolation contracts).

**Deliverables:**

- `src/sonya/embodiment/adapter.py` — `EmbodimentEvent` schema, `VirtualBodyCounter` stubs (`hunger_analog`, `tiredness_analog`, etc. как simple counters);
- `src/sonya/embodiment/avatar.py` — `AvatarStateExpression` placeholder (shape для future TTS/avatar/world bindings);
- `src/sonya/simulation/world.py` — `WorldEvent` ingest contract, `WorldAction` emission contract, replay harness;
- `src/sonya/harness/hyper.py` — scheduler shell с concurrency policy, supervision stubs, cancellation/timeout, risk-tier coordination interface;
- substrate v8: таблицы `embodiment_events`, `world_events`, `world_actions`, `scheduled_jobs`, `supervised_branches`;
- тесты: contract-level only (объекты создаются, persist, retrieve через API; реальная интеграция с physical/sim — пост-MVP).

**Exit-критерии:**

- [ ] три модуля существуют, exposed через `__all__`, layer-boundary тест проходит;
- [ ] persistent storage round-trip;
- [ ] composition root `main.py` подключает все три (как minimal lifecycle hooks);
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** не имеет аналога simulation/embodiment; берём из docs/research напрямую.
- **Hermes:** все три — brain substrate. Adapters наружу — отдельный layer.
- **OmniAgent:** отвергаем «Hyper-Harness как marketing term». Наш hyper-harness — конкретный scheduler shell с явными contracts.

---

## 16. Фаза 10 — VPS Deployment

**Статус:** ⬜ финальная MVP фаза.

**Цель.** Перенос с Windows на VPS Linux. Sonya живёт там полностью, OpenClaw отключается.

**Контуры активируемые:**

- §7.23 VPS Readiness — `Production`.

**Deliverables:**

- production `deploy/systemd/sonya.service` с env-файлом;
- `deploy/README.md` — пошаговая инструкция;
- `.env.example` с полным списком env;
- secrets pipeline (`.env` permission 600 + systemd `LoadCredential`);
- health HTTP endpoint;
- backup/restore policy для всех substrate БД;
- bridge мигрирует на VPS;
- OpenClaw-хост отключается после 7+ дней параллельной работы.

**Exit-критерии:**

- [ ] Sonya на VPS работает 72 часа без вмешательств;
- [ ] перезапуск VPS → systemd auto-start;
- [ ] Telegram отвечает с VPS;
- [ ] OpenClaw отключён;
- [ ] daily backup + restore tested;
- [ ] governance-гейт пройден; `Emergency host` секция чеклиста полностью зелёная;
- [ ] **MVP достигнут** в смысле SYSTEM_CORE/MVP_BOUNDARIES.

**Reference Check preview:**

- **OpenClaw:** все lessons сохранены в коде; host больше не зависимость.
- **Hermes:** shell/brain split закреплён на уровне deployment.
- **OmniAgent:** отвергаем `gateway/webui.py` 56KB. Health endpoint минимальный.

---

## 17. Пост-MVP — Maturity Deepening

После Phase 10 каждый контур существует **в той или иной форме**. Дальше — углубление зрелости.

Параллельные tracks (приоритеты по конкретным use-case):

- **Track A — Skill Evolution to Production:** real-time skill evolution с ML-scoring, automatic promotion после passing tests, sandbox execution. Driver: `SKILL_SYSTEM_PLAN`.
- **Track B — Self-Modification to Automatic:** trace replay с реальными N днями данных, sandbox execution с git working copy, automatic apply после passing 4 layers + watch window. Driver: `SUBSTRATE_STANCE §9`.
- **Track C — Channels Beyond Telegram:** Discord, web/admin, TTS renderer. Driver: `CHANNELS_AND_TELEGRAM_PLAN`.
- **Track D — Real Embodiment & Simulation:** virtual body integration с реальной simulation, avatar TTS/voice. Driver: `SIMULATION_AND_EMBODIMENT_PLAN`.
- **Track E — Brain Evolution:** интерфейс для self-hosted (vllm/sglang/RWKV), stateful backend extension Protocol, RL adapter. Driver: `BRAINMODEL_EVOLUTION_PLAN`.
- **Track F — Hyper-Harness to Production:** real scheduler с risk-tiered concurrency, supervision, isolation, quotas. Driver: `ANCHORS_AND_FAILURE_MODES §7`.
- **Track G — Memory to Production:** RAG embeddings, semantic dedup, contradiction resolution. Driver: `MEMORY_AND_IDENTITY_PLAN`.
- **Track H — Cross-channel continuity:** principal linking across channels. Driver: `CONTINUITY_STREAM_AND_SUBJECT_CORE`.

Эти tracks **не** закрываются в линейном порядке. Какой-то может пойти вперёд, если появится конкретный use-case.

## 18. Go/No-Go протокол между фазами

Переход N → N+1 требует:

1. **Exit-критерии.** Все [x] помечены.
2. **Тесты.** Вся база зелёная. Никаких новых skipped/xfail.
3. **Governance-гейт:**
   - implementation plan: Active → Archived;
   - Reference Check пройден;
   - `GLOBAL_PROJECT_CHECKLIST.md` обновлён;
   - `PROJECT_DOCUMENTATION_MAP.md` обновлён если переезды;
   - `governance/DRIFT_REVIEW.md` получил запись.
4. **Reality check.** Иван явно подтверждает.

**No-Go ситуации:**

- Exit-критерий нарушился → возврат, чиним, закрываем заново.
- Reference Check устарел → переписываем ответы, обновляем план.
- Architectural conflict с governing doc → пауза, review `docs/core/`, при необходимости update governing doc через governed change.

## 19. Связь с другими документами

- **Что строим:** [SONYA_SYSTEM_CORE](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [MVP_BOUNDARIES](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md).
- **Что уже есть:** [GLOBAL_PROJECT_CHECKLIST](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md).
- **Шаблоны:** [work/TEMPLATES/](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES).
- **Reference-основы:** [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md).
- **Дисциплина:** [agents/AGENT_OPERATING_RULES](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md), [core/DOCUMENTATION_SYSTEM](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md).
- **State:** [governance/DRIFT_REVIEW](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md).

## 20. Финальное правило

ROADMAP не имеет права противоречить SYSTEM_CORE и MVP_BOUNDARIES. Если такое случилось — это drift, governing docs выигрывают.

ROADMAP не имеет права хоронить обязательные контуры в «post-MVP». Stub в MVP — да; «после MVP» — нет.

ROADMAP обновляется при каждом переходе фазы и в рамках drift-review cadence.
