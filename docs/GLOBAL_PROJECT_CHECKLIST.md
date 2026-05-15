# ГЛОБАЛЬНЫЙ ЧЕКЛИСТ ПРОЕКТА

**Status:** Active
**Type:** Core
**Scope:** Audit ledger фактического состояния проекта Sonya — что реально есть в коде прямо сейчас
**Depends on:** [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
**Used by:** drift review, архитектурный аудит, milestone review, перед-коммитный sanity check
**Last reviewed:** 2026-05-15

## Что это за файл

Этот файл отвечает на один вопрос: **что фактически существует в коде прямо сейчас**.

Он не отвечает на вопрос «что мы строим и в каком порядке» — это делает [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md).

Он не отвечает на вопрос «почему именно так» — это делают `docs/core/` и `docs/architecture/`.

Это audit ledger. Только ✅/🟡/⬜ и ссылки на настоящие файлы.

### Правила

- ✅ — реально существует в коде и работает на текущем нужном уровне.
- 🟡 — существует частично, в emergency-форме, или только как интерфейс/stub.
- ⬜ — не существует в коде (даже если подробно описано в документации).

Документация без кода — это **не** ✅. Это ⬜ с возможным упоминанием «описан в `doc.md`».

Порядок секций следует архитектурным слоям из [ARCHITECTURE_PLAN.md §4](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md). Если появится новый слой — он добавляется в этот же порядок, не в конец.

---

## 1. Foundation — Governance и документация

- ✅ Проектный смысл зафиксирован: [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
- ✅ Документационная система codified: [DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md) с lifecycle `Active/Draft/Stale/Archived`, doc-review gate, drift cadence
- ✅ Корневая карта документации актуальна: [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md)
- ✅ Roadmap существует как отдельный файл: [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md)
- ✅ Agent-layer: онбординг + operating rules + task runtime contract + failure modes ([docs/agents/](C:/Users/Jester/Desktop/Sonya/docs/agents))
- ✅ Governance-layer: drift review ledger с cadence и правилами ([governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md))
- ✅ Templates для work-доков с обязательным Reference Check ([docs/work/TEMPLATES/](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES))
- ✅ Все исторические work-доки размечены (`Active`/`Stale`/`Archived` с «why»-заметкой)
- 🟡 Drift review cadence работает: правило есть, две записи есть (initial + Phase 1 closure) — регулярность подтверждается после третьей записи на следующем cadence-окне
- ✅ Doc-review gate для кодовых изменений: применён в Phase 1 substrate bootstrap (план через шаблон, Reference Check пройден, checklist+ledger+roadmap синхронизированы при closure)

## 2. Foundation — Phase 0: анализ референсов

- ✅ [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md) с code-level pass
- ✅ [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md) (теория + code-level audit 2026-05-13)
- ✅ [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md) (теория + code-level audit 2026-05-13)
- 🟡 [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md) — code-level невозможен (Hermes-кода нет); роль трактуется как ответственность внутри `sonya_runtime/*`
- ✅ Reference Check встроен как обязательное поле шаблонов и pre-implementation gate ([ARCHITECTURE_PLAN.md §11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md))
- ✅ Полная работоспособность gate подтверждена: substrate bootstrap план (2026-05-13) первым прошёл шаблон без дрейфа

## 3. Repo & package layout

- ✅ Отдельный репозиторий Sonya
- ✅ `docs/` отделён от кода; `docs/work/` — кухня, не истина
- ✅ `packages/tg-bridge` как выделенный пакет
- ✅ `src/sonya_runtime` — reusable runtime slice (action models, task runtime, continuity stubs, storage paths)
- ✅ `src/sonya_shared` — общие примитивы
- ✅ `src/sonya/` как итоговое ядро: state (substrate v1, subject_state, continuity_stream, identity, principals) + runtime (lifecycle, event_bus, write_master, health) + main composition root
- 🟡 Финализированная packaging strategy для будущего `sonya-core` (пока shape работает, итоговое имя/распакетовка — Фаза 6+)
- ✅ Repo-level boundary checks автоматизированы (state ↔ runtime + расширены на providers/harness; см. [tests/sonya/test_layer_boundary.py](C:/Users/Jester/Desktop/Sonya/tests/sonya/test_layer_boundary.py))

## 4. Emergency host — OpenClaw compatibility

- ✅ `.openclaw` работает как живой operational host
- ✅ Telegram bridge вынесен из `.openclaw` в `packages/tg-bridge`
- ✅ Bridge использует OpenClaw config, workspace anchors, memory bootstrap через adapter
- ✅ Post-response hook OpenClaw продолжает работать
- ✅ `tasks.db` отделён от `memory.db`
- 🟡 OpenClaw-only assumptions описаны в [OPENCLAW_ANALYSIS.md code-level audit](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md), но не сведены в единый каталог «что ломается если отключить»
- ⬜ Возможность отключить OpenClaw host без потери runtime-ядра (нет ядра)
- ⬜ Sonya на VPS как самостоятельный runtime

## 5. Runtime shell

- ✅ `src/sonya/` — самостоятельный долгоживущий процесс (`python -m sonya`)
- ✅ Event bus на уровне ядра ([sonya.runtime.events](C:/Users/Jester/Desktop/Sonya/src/sonya/runtime/events.py))
- ✅ Lifecycle manager (startup/shutdown/signals, attached to continuity stream)
- ⬜ Scheduler на уровне ядра (Фаза 6+)
- ✅ Health/status модель (file-ping JSON, [sonya.runtime.health](C:/Users/Jester/Desktop/Sonya/src/sonya/runtime/health.py))
- ✅ Restart-safe shell без emergency-костылей (substrate-first; write-master enforced)
- 🟡 `python -m sonya_runtime.tasks.worker` работает как отдельный процесс воркера (legacy, мигрирует в Фазе 5)
- ✅ Substrate-aware abstraction путей ([sonya.config](C:/Users/Jester/Desktop/Sonya/src/sonya/config.py)); `sonya_runtime.storage.paths` остаётся для legacy-task-worker

## 6. Subject core & continuity

- ✅ Subject core и continuity стрим описаны как базовая архитектура ([CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md))
- ✅ `SubjectState` в коде с emotional_vector и drift_signals ([sonya.state.subject_state](C:/Users/Jester/Desktop/Sonya/src/sonya/state/subject_state.py))
- ✅ `ContinuityStream` с персистентным append-only логом и автоинкрементным `seq` ([sonya.state.continuity_stream](C:/Users/Jester/Desktop/Sonya/src/sonya/state/continuity_stream.py))
- ✅ `ContinuitySnapshot` (snapshot/restore) через `SubjectStateStore`
- ✅ `CanonicalResponse` с 11 response kinds в `sonya.state.canonical_response` (bridge ещё не использует — Phase 7)
- ✅ `PendingIntention` как first-class persistent state ([sonya.state.pending](C:/Users/Jester/Desktop/Sonya/src/sonya/state/pending.py))
- ✅ Internal cognitive process: event-driven coroutine с homeostasis counters ([sonya.subject.internal_loop](C:/Users/Jester/Desktop/Sonya/src/sonya/subject/internal_loop.py))
- ✅ Event bus integration: `continuity.event_added` и `subject.state_changed` ([sonya.subject.bus_wiring](C:/Users/Jester/Desktop/Sonya/src/sonya/subject/bus_wiring.py))
- ⬜ Cross-channel continuity persistence (post-MVP Track H)

## 7. Identity, anchors, principals

- ✅ Identity и anchors описаны как несущий контур ([ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md))
- ✅ Principal vs display-name separation зафиксирована в `SONYA_SYSTEM_CORE.md §5.6`
- ✅ `IdentityRecord` с явным enforcement immutable-зон в коде ([sonya.state.identity](C:/Users/Jester/Desktop/Sonya/src/sonya/state/identity.py))
- ✅ `things_not_to_betray` seed на первом запуске через governed change ([sonya.state.seed](C:/Users/Jester/Desktop/Sonya/src/sonya/state/seed.py))
- ✅ `RelationAnchorBinding` schema + governed-change путь
- ✅ `PrincipalRegistry` (минимальный CRUD) ([sonya.state.principals](C:/Users/Jester/Desktop/Sonya/src/sonya/state/principals.py))
- ✅ Channel-side principal resolver: `resolve_from_channel_input(channel, value)` маппит транспортную пару в trusted_identifier
- 🟡 Telegram-bridge ещё не использует resolver — миграция в Фазе 7 (planner migration)
- ✅ Trusted identity evidence model: schema + resolver + lookup pipeline в коде
- ✅ Authority scopes на principal-уровне: `AuthorityPolicy` с persistent rules ([sonya.harness.authority](C:/Users/Jester/Desktop/Sonya/src/sonya/harness/authority.py))
- ⬜ Cross-channel principal linking (post-MVP Track H)
- ✅ Audit trail: `governed_identity_change` в continuity + `AuditLog` для harness-решений ([sonya.harness.audit](C:/Users/Jester/Desktop/Sonya/src/sonya/harness/audit.py))

## 8. Memory core

- ✅ Архитектура памяти зафиксирована ([MEMORY_AND_IDENTITY_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/MEMORY_AND_IDENTITY_PLAN.md))
- 🟡 Working memory читается через OpenClaw `context_loader.py` в bridge bootstrap
- 🟡 Значимые ответы пишутся в OpenClaw `events` через post-response hook
- 🟡 `facts`/`lessons` в OpenClaw схеме — ручное ведение, не автоматизация
- 🟡 RAG-слой существует в OpenClaw и используется из `context_loader.py`
- ⬜ Sonya-owned memory core (всё выше — OpenClaw)
- ⬜ Clean episodic/semantic/working API внутри `src/sonya/memory`
- ⬜ Consolidation pipeline под контролем Sonya
- ⬜ Policy-object вместо hard-coded strong-markers
- ⬜ Evaluation для memory fidelity

## 9. Provider & model layer

- ✅ `tg_bridge.model_client` работает: text/vision/image gen через OpenRouter
- ✅ Retry/timeout/continuation/dedup hardening для completion loop
- ✅ Text+vision и image-generation модели разведены (через `agents.defaults.model` / `imageModel`)
- ✅ Provider-абстракция вне бриджа: [sonya.providers](C:/Users/Jester/Desktop/Sonya/src/sonya/providers/__init__.py)
- ✅ `src/sonya/providers/` — `ProviderBackend` Protocol, `ProviderRegistry`, `OpenRouterProvider`, `ProviderSecret` (env-only)
- ✅ Capability matrix (per-model input/context/max_tokens/cost/compat) в `Capability` dataclass
- 🟡 Policy выбора модели на уровне runtime: registry есть, planner-level выбор — Фаза 7
- ⬜ Унифицированный eval path для моделей
- ⬜ `StatefulBackend` extension для recurrent моделей (RWKV) — post-MVP Track E (см. [BRAINMODEL_EVOLUTION_PLAN §5.1](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md))
- ⬜ Provider-independent runtime contract

## 10. Action & planner

- ✅ Reusable action models в [sonya_runtime.actions.models](C:/Users/Jester/Desktop/Sonya/src/sonya_runtime/actions/models.py): action types, `RuntimeAction`, `RuntimeTaskPayload`, `parse_runtime_action` с fallback-коерцией
- ✅ `sonya_runtime.actions.policy` — `ANTI_FAKE_AGENCY_RULES` + эвристики task-request / task-status
- ✅ `sonya_runtime.actions.planner_contract` — action-type categories + task-status markers
- ✅ Bridge использует runtime action layer (после реэкспорта в `tg_bridge.actions`)
- ✅ Anti-fake-agency правила встроены в planner prompt через `tg_bridge.prompts.build_action_messages`
- 🟡 Planner (`_plan_text_action_with_fallback`) всё ещё физически в `tg_bridge.app` (миграция — Фаза 7)
- ⬜ Planner в `src/sonya/planning/*` (Фаза 7)
- ⬜ Capability registry на уровне ядра (Фаза 5)
- ⬜ Централизованная action validation policy (Фаза 7)
- ⬜ Eval corpus для planner вне `tg-bridge` тестов
- ⬜ Regression suite на fake-agency кейсы (file action claims, time/delay claims)

## 11. Reusable task runtime

- ✅ `sonya_runtime.tasks.models`: `TaskRecord`, `TaskStatus`, `utc_now_iso`
- ✅ `sonya_runtime.tasks.store`: `TaskStore` Protocol (но `get_recent_tasks_for_principal` только у SQLite-реализации — минорный долг)
- ✅ `sonya_runtime.tasks.sqlite_store`: `SQLiteTaskStore` с CRUD, claim, mark_done/failed/cancelled, per-principal queries
- ✅ `sonya_runtime.tasks.service`: `TaskService` с `create_task_from_action`, `build_task_{created,status,result}_response`
- ✅ `sonya_runtime.tasks.executor`: `TaskExecutor` с пятью безопасными kinds (`workspace_analysis`, `documentation_synthesis`, `lead_workflow_analysis`, `memory_diagnosis`, `file_search_and_summary`)
- ✅ `sonya_runtime.tasks.worker`: CLI entrypoint `python -m sonya_runtime.tasks.worker` с claim → execute → done/failed loop
- ✅ Bridge умеет создавать задачи и отвечать статусом (через `TaskService` в `handle_update`)
- ✅ `tasks.db` живёт отдельно от `memory.db` (через `RuntimePaths.tasks_db_path`)
- ✅ Task refs (`[task_ref:...]`) попадают в session history бриджа
- 🟡 Worker ограничен read-only task kinds; mutation-capable — отдельная волна
- 🟡 Worker не service-grade: нет supervisor, metrics, backoff policy
- ⬜ Scheduler-coordinated task runtime
- ⬜ Principal-aware task policy (сейчас принципал — просто строка)
- ⬜ Mutation-capable tasks с approval gate
- ⬜ Task telemetry/reporting layer
- ⬜ Multi-worker coordination beyond SQLite locking

## 12. Sessions & working state

- ✅ Bridge сохраняет `telegram-bridge-sessions/<chat_id>.json` (truncate to last 20 messages)
- ✅ Task refs попадают в session history
- 🟡 Session-модель bridge-specific (`packages/tg-bridge/src/tg_bridge/sessions.py`)
- ⬜ Общая session abstraction в `src/sonya/*`
- ⬜ Session summarization policy
- ⬜ Session pruning policy (beyond last-20 truncation)
- ⬜ Session-to-subject_state handoff
- ⬜ Session-to-memory handoff formalized

## 13. Skills & capability growth

- ✅ Skill architecture задокументирована ([SKILL_SYSTEM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md))
- ✅ OpenClaw-side skill реальность проанализирована ([OPENCLAW_ANALYSIS.md §7.5](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md))
- ⬜ Skill registry в коде (Фаза 5)
- ⬜ Skill loading (Фаза 5)
- ⬜ Skill trust tiers (Фаза 5)
- ⬜ Skill testing contract (Фаза 5)
- ⬜ Skill evolution runtime — Manual-Gated в Фазе 5; production через self-mod pipeline — post-MVP Track A
- ⬜ Capability gap detection (Фаза 5) — это базовый механизм самоулучшения
- ⬜ Skill Injection User Message — Partial в Фазе 5
- ⬜ Planner умеет выбирать skill action (Фаза 7)
- ⬜ Capability graph включает skills как first-class

## 14. Harness & safety

- ✅ Harness описан как несущий слой (три slice: technical/epistemic/anchor в [ANCHORS_AND_FAILURE_MODES.md §7](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md))
- ✅ Baseline harness в коде: `AuthorityPolicy`, `ApprovalManager`, `AuditLog` в [sonya.harness](C:/Users/Jester/Desktop/Sonya/src/sonya/harness/__init__.py)
- 🟡 Risk classes: scope-based decisions есть (`AuthorityDecision = ALLOW/DENY/REQUIRE_APPROVAL`); реальные классы рисков — пост-MVP Track F
- ✅ Immutable zones: enforced в `IdentityWriter` для `things_not_to_betray` и `identity_critical_traits`; первичный `RelationAnchorBinding` через governed-change
- 🟡 Approval gates: storage и lifecycle API готовы (`ApprovalManager` с PENDING/APPROVED/DENIED), реальный human gate — Фаза 4 (governed change protocol)
- ⬜ Self-modification framework skeleton (4-layer pipeline + anchor integrity check) — Фаза 4 (Manual-Gated по [SYSTEM_CORE §7.18](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md))
- ⬜ Drift detection в runtime (Фаза 6 — anchor drift signals)
- ⬜ Hyper-Harness scheduler shell — Фаза 9 (Stub по [SYSTEM_CORE §7.13](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md))
- ⬜ Task mutation actions respect harness

## 14.1 Self-modification framework

- ✅ 4-слойный pipeline описан в [SUBSTRATE_STANCE §9](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md)
- ✅ Право Сони переписывать non-identity-critical код фиксировано в [SELF_REWRITE_STANCE](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md)
- ⬜ `SelfModificationProposal` first-class object в substrate (Фаза 4)
- ⬜ Layer 1 Static Contract Check (Фаза 4 — stub)
- ⬜ Layer 2 Isolated Behavioral Test (Фаза 4 — stub: subprocess + assert all pass)
- ⬜ Layer 3 Trace Replay (Фаза 4 — stub; реальная работа — post-MVP Track B при наличии N дней данных)
- ⬜ Layer 4 Anchor Integrity Check (Фаза 4 — реальный rules-based по 4 пилонам `things_not_to_betray`)
- ⬜ Governed change protocol (Фаза 4 — wired через `ApprovalManager` + primary anchor)
- ⬜ Watch window + auto-revert (Фаза 4 — stub; реальные signals — Фаза 6)
- ⬜ Real patch application к коду (post-MVP Track B — sandbox + git working copy)

## 14.2 Initiative layer

- ✅ Initiative описан как обязательный контур ([SYSTEM_CORE §7.20](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [CONSCIOUSNESS_POSITION §10.5](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md))
- ⬜ Internal continuous loop coroutine (Фаза 3 — heartbeat)
- ⬜ Drive counters (`boredom_analog`, `curiosity_analog`, etc.) — Фаза 6
- ⬜ `InitiativeSignal` first-class objects — Фаза 6
- ⬜ Outbound action proposals через harness — Фаза 6
- ⬜ Anchor drift signals — Фаза 6
- ⬜ LLM-driven creative initiation — post-MVP Track A/B (требует skill execution + planner)

## 15. Telegram channel

- ✅ Bridge работает: live polling, outbound, text/vision/image-generation
- ✅ Session storage
- ✅ Raw updates JSONL audit (`telegram/raw-updates.jsonl`)
- ✅ Post-response hook wiring через subprocess
- ✅ Bridge использует `sonya_runtime` action/task layer (не invented локально)
- 🟡 Bridge держит planner у себя
- 🟡 Bridge ещё не получает готовый `CanonicalResponse` от ядра — рендерит из ответа LLM напрямую
- ⬜ Telegram как тонкий adapter к общему `sonya-core`
- ⬜ Channel contract обобщён для других поверхностей

## 16. Каналы beyond Telegram

- ✅ Принцип «каналы — это поверхности одного субъекта» зафиксирован ([CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md))
- ⬜ Discord
- ⬜ Web/admin surface
- ⬜ TTS renderer
- ⬜ Voice pipeline через canonical response
- ⬜ Channel registry
- ⬜ Cross-channel continuity operational
- ⬜ Principal linking across channels

## 17. Observability & operations

- ✅ Bridge логи (`telegram-bridge.log`)
- ✅ `health-check.ps1` на OpenClaw-стороне
- ✅ Raw-updates JSONL и structured `append_log_line` в бридже
- 🟡 Локальный запуск через `.vbs`/`.ps1` скрипты работает, но emergency-форма
- ⬜ Structured logs across `src/sonya/*`
- ⬜ Metrics and counters
- ⬜ Task queue metrics
- ⬜ Planner decision telemetry
- ⬜ Dashboard / report path
- ⬜ VPS-ready backup/restore

## 18. Embodiment, simulation, future brain stack

- ✅ Все три контура описаны в [docs/research/](C:/Users/Jester/Desktop/Sonya/docs/research): state tuning, brainmodel evolution, simulation/embodiment
- ✅ RWKV/stateful future path учтён ([BRAINMODEL_EVOLUTION_PLAN §5.1](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md))
- ⬜ Brain-state data models в коде (post-MVP Track E)
- ⬜ `StatefulBackend` Protocol extension (post-MVP Track E)
- ⬜ Simulation contract (Фаза 9 — Research-Shell stub)
- ⬜ Embodiment adapter contract (Фаза 9 — Stub: `EmbodimentEvent`, `VirtualBodyCounter`)
- ⬜ Physical body interface (post-MVP Track D)
- ⬜ Voice/avatar/body stack привязан к одному subject core (post-MVP Track D)

---

## Минорные долги (spillovers из текущих ✅)

Это не отдельная фаза — это точечные undone things внутри уже-работающих слоёв. Жёлтые пункты выше, которые стоит закрыть мимоходом при ближайшем прохождении по соответствующему слою.

- `TaskStore` Protocol в `src/sonya_runtime/tasks/store.py` не объявляет `get_recent_tasks_for_principal`, хотя `TaskService` его вызывает (`# type: ignore[attr-defined]`). Либо добавить в протокол, либо сузить интерфейс, используемый `TaskService`.
- `ContinuityEvent` в `src/sonya_runtime/continuity/events.py` определён, но нигде не потребляется. Либо подключить читателя (Фаза 3), либо пометить как Draft-интерфейс с TODO.
- `TaskExecutor._execute_memory_diagnosis` открывает `memory.db` напрямую и не ловит ошибки. Для v1 read-only это ок, но это sensitivity point при переезде памяти (Фаза 5).
- Bridge launch использует `.vbs`/`.ps1` скрипты — эмерджентное решение, которое должно быть заменено systemd-юнитом в Фазе 6.

## Финальное правило

Этот файл обязан оставаться честным. Он не содержит «скоро будет» и «мы хотим». Только то, что реально в коде прямо сейчас.

Планы на будущее живут в [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md).

Архитектурные решения живут в [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md) и cognition-плане.

Если между этим файлом и реальностью кода возник разрыв — это drift event, и он должен попасть в [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md).
