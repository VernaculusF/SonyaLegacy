# ГЛОБАЛЬНЫЙ ЧЕКЛИСТ ПРОЕКТА

**Status:** Active
**Type:** Core
**Scope:** Audit ledger фактического состояния проекта Sonya — что реально есть в коде прямо сейчас
**Depends on:** [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
**Used by:** drift review, архитектурный аудит, milestone review, перед-коммитный sanity check
**Last reviewed:** 2026-05-13

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
- 🟡 Drift review cadence работает: правило есть, первая запись есть — регулярность подтверждается после второй записи
- 🟡 Doc-review gate для кодовых изменений: правило codified — реальное исполнение на PR ещё впереди

## 2. Foundation — Phase 0: анализ референсов

- ✅ [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md) с code-level pass
- ✅ [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md) (теория + code-level audit 2026-05-13)
- ✅ [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md) (теория + code-level audit 2026-05-13)
- 🟡 [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md) — code-level невозможен (Hermes-кода нет); роль трактуется как ответственность внутри `sonya_runtime/*`
- ✅ Reference Check встроен как обязательное поле шаблонов и pre-implementation gate ([ARCHITECTURE_PLAN.md §11](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md))
- 🟡 Полная работоспособность gate подтверждается после первого живого plan через шаблон

## 3. Repo & package layout

- ✅ Отдельный репозиторий Sonya
- ✅ `docs/` отделён от кода; `docs/work/` — кухня, не истина
- ✅ `packages/tg-bridge` как выделенный пакет
- ✅ `src/sonya_runtime` — reusable runtime slice (action models, task runtime, continuity stubs, storage paths)
- ✅ `src/sonya_shared` — общие примитивы
- ⬜ `src/sonya/` как итоговое ядро
- ⬜ Финализированная packaging strategy для будущего `sonya-core`
- ⬜ Repo-level boundary checks автоматизированы

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

- ⬜ `src/sonya/` — самостоятельный долгоживущий процесс
- ⬜ Event bus на уровне ядра
- ⬜ Lifecycle manager (startup/shutdown/signals)
- ⬜ Scheduler на уровне ядра
- ⬜ Health/status модель
- ⬜ Restart-safe shell без emergency-костылей
- 🟡 `python -m sonya_runtime.tasks.worker` работает как отдельный процесс воркера
- 🟡 `sonya_runtime.storage.paths` — начальная абстракция путей

## 6. Subject core & continuity

- ✅ Subject core и continuity стрим описаны как базовая архитектура ([CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md))
- 🟡 `CanonicalResponse` как минимальный dataclass в [sonya_runtime/continuity/canonical_response.py](C:/Users/Jester/Desktop/Sonya/src/sonya_runtime/continuity/canonical_response.py) — используется только `TaskService`
- 🟡 `ContinuityEvent` как stub в [sonya_runtime/continuity/events.py](C:/Users/Jester/Desktop/Sonya/src/sonya_runtime/continuity/events.py) — без читателя
- ⬜ `SubjectState` в коде
- ⬜ `ContinuityStream` с персистентностью
- ⬜ `ContinuitySnapshot` (snapshot/restore)
- ⬜ `PendingIntention` как runtime state
- ⬜ Cross-channel continuity persistence

## 7. Identity, anchors, principals

- ✅ Identity и anchors описаны как несущий контур ([ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md))
- ✅ Principal vs display-name separation зафиксирована в `SONYA_SYSTEM_CORE.md §5.6`
- 🟡 Telegram использует транспортный `from_id` + allowlist как частичную operational identity
- ⬜ `Principal` / `PrincipalRegistry` в коде
- ⬜ Trusted identity evidence model
- ⬜ Authority scopes на principal-уровне
- ⬜ Relation-anchor binding rules в runtime
- ⬜ Cross-channel principal linking
- ⬜ Audit trail для principal решений

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
- 🟡 Provider-слой живёт только внутри `packages/tg-bridge/src/tg_bridge/model_client.py`
- ⬜ `src/sonya/providers/` — provider abstraction вне бриджа
- ⬜ Capability matrix (per-model input/context/max_tokens/cost/compat)
- ⬜ Policy выбора модели на уровне runtime
- ⬜ Унифицированный eval path для моделей
- ⬜ Provider-independent runtime contract

## 10. Action & planner

- ✅ Reusable action models в [sonya_runtime.actions.models](C:/Users/Jester/Desktop/Sonya/src/sonya_runtime/actions/models.py): action types, `RuntimeAction`, `RuntimeTaskPayload`, `parse_runtime_action` с fallback-коерцией
- ✅ `sonya_runtime.actions.policy` — `ANTI_FAKE_AGENCY_RULES` + эвристики task-request / task-status
- ✅ `sonya_runtime.actions.planner_contract` — action-type categories + task-status markers
- ✅ Bridge использует runtime action layer (после реэкспорта в `tg_bridge.actions`)
- ✅ Anti-fake-agency правила встроены в planner prompt через `tg_bridge.prompts.build_action_messages`
- 🟡 Planner (`_plan_text_action_with_fallback`) всё ещё физически в `tg_bridge.app`
- ⬜ Planner в `src/sonya/planning/*`
- ⬜ Capability registry на уровне ядра
- ⬜ Централизованная action validation policy
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
- ⬜ Skill registry в коде
- ⬜ Skill loading
- ⬜ Skill trust tiers
- ⬜ Skill testing contract
- ⬜ Skill evolution runtime
- ⬜ Planner умеет выбирать skill action
- ⬜ Capability graph включает skills как first-class

## 14. Harness & safety

- ✅ Harness описан как несущий слой (три slice: technical/epistemic/anchor в [ANCHORS_AND_FAILURE_MODES.md §7](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md))
- ⬜ Baseline harness в коде
- ⬜ Risk classes
- ⬜ Immutable zones
- ⬜ Approval gates (за пределами читаемого `exec-approvals.json` в OpenClaw)
- ⬜ Drift detection в runtime
- ⬜ Self-modification gating
- ⬜ Task mutation actions respect harness

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
- ✅ RWKV/stateful future path учтён
- ⬜ Brain-state data models в коде
- ⬜ Stateful backend adapter
- ⬜ Simulation contract
- ⬜ Embodiment contract
- ⬜ Physical body interface
- ⬜ Voice/avatar/body stack привязан к одному subject core

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
