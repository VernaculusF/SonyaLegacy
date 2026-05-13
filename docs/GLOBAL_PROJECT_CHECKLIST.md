# ГЛОБАЛЬНЫЙ ЧЕКЛИСТ ПРОЕКТА

**Status:** Active
**Type:** Core
**Scope:** Полная карта состояния проекта Sonya: что уже реально построено, что собрано частично, а что пока только в плане
**Depends on:** [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
**Used by:** roadmap review, архитектурный аудит, implementation review, milestone review, drift control
**Last reviewed:** 2026-05-08

## Как читать этот файл

Это не sprint todo.

Это жёсткая карта реальности проекта.

Обозначения:

- ✅ реально существует и работает на нужном сейчас уровне
- 🟡 существует частично, в emergency-форме или как промежуточный слой
- ⬜ ещё не построено

Если что-то существует только в документации, это не ✅.

---

## 1. Governance и документация

- ✅ Корневой проектный смысл зафиксирован в [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
- ✅ Позиция по субъектности зафиксирована в [SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md)
- ✅ Есть корневая карта документации
- ✅ Есть внешний onboarding-док для замены Codex внешней моделью
- ✅ Есть правила документационной системы
- ✅ Есть живой глобальный чеклист
- 🟡 Доки поддерживаются после крупных архитектурных изменений, но дисциплина ещё не автоматизирована
- ⬜ Drift review встроен в регулярный operational цикл
- ⬜ Все исторические work-доки размечены как active/stale/archive
- ⬜ Для каждого большого кодового изменения есть обязательный doc-review gate

## 2. Фаза 0: анализ референсов

- ✅ Есть общий reference-анализ
- ✅ Есть анализ OpenClaw
- ✅ Есть анализ Hermes
- ✅ Есть анализ OmniAgent
- ✅ Reference phase встроена в [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md) как обязательная ранняя стадия
- 🟡 Новые implementation slices иногда ещё делаются быстрее, чем референс-проверка успевает обновиться
- ⬜ Каждый новый subsystem-план явно отвечает, что он берёт из OpenClaw
- ⬜ Каждый новый subsystem-план явно отвечает, что он берёт из Hermes
- ⬜ Каждый новый subsystem-план явно отвечает, какие shortcut-идеи из OmniAgent он отвергает
- ⬜ Фаза анализа полностью превращена в реальный pre-implementation gate

## 3. Репозиторий и package layout

- ✅ У Sonya есть отдельный репозиторий
- ✅ `docs/` отделён от кодовых пакетов
- ✅ `docs/work/` используется как рабочая кухня, а не как системная истина
- ✅ `packages/tg-bridge` существует как выделенный пакет
- ✅ Появился отдельный reusable слой `src/sonya_runtime`
- ✅ Появился `src/sonya_shared`
- 🟡 Полноценный `src/sonya/` как итоговое ядро ещё не построен
- 🟡 Packaging strategy уже осмысленная, но не финализирована
- ⬜ Release strategy для будущего `sonya-core` зафиксирована
- ⬜ Repo-level runtime boundaries автоматизированно проверяются

## 4. Emergency host и совместимость с OpenClaw

- ✅ `.openclaw` сейчас используется как живой host
- ✅ Telegram bridge вынесен из `.openclaw` в репозиторий Sonya
- ✅ Bridge использует OpenClaw config, workspace anchors и memory bootstrap
- ✅ Post-response hook OpenClaw продолжает работать
- ✅ Отдельная task DB отделена от `memory.db`
- 🟡 OpenClaw всё ещё несёт заметный operational debt
- 🟡 Совместимость строится через adapter-слой, но финальная decoupling ещё впереди
- ⬜ Критические OpenClaw-only assumptions полностью каталогизированы
- ⬜ Можно отключить OpenClaw host без потери основного runtime-ядра
- ⬜ Sonya может жить на VPS как самостоятельный runtime без OpenClaw

## 5. Runtime shell

- ⬜ Полный `sonya-core` runtime shell существует
- 🟡 Есть первый reusable runtime slice в `src/sonya_runtime`
- 🟡 Есть отдельный task worker entrypoint
- 🟡 Есть runtime storage paths abstraction
- ⬜ Есть общий runtime event bus
- ⬜ Есть lifecycle manager уровня ядра
- ⬜ Есть scheduler уровня ядра
- ⬜ Есть runtime bootstrap вне `tg-bridge`
- ⬜ Есть общая health/status модель уровня Sonya
- ⬜ Есть restart-safe runtime shell без emergency-костылей

## 6. Subject core и continuity

- ✅ Проблема subject core зафиксирована как базовая архитектура
- ✅ Проблема continuity stream зафиксирована как базовая архитектура
- ✅ Canonical response уже выделен как обязательный объект в архитектуре
- 🟡 В коде появился минимальный `canonical_response` dataclass
- 🟡 Task lifecycle уже привязан к continuity на уровне архитектурных правил
- ⬜ Есть реальный `subject_state` в коде
- ⬜ Есть реальный `continuity_event` stream в коде
- ⬜ Есть `continuity_snapshot`
- ⬜ Pending intentions реализованы как runtime state
- ⬜ Cross-channel continuity persistence реально работает

## 7. Identity, anchors, principals

- ✅ Identity и anchors описаны как отдельный несущий контур
- ✅ Проблема principal resolution зафиксирована в доках
- 🟡 Telegram пока использует транспортные ID и allowlist как частичную operational truth
- ⬜ Есть principal registry в коде
- ⬜ Есть human label vs principal ID separation в коде
- ⬜ Есть trusted identity evidence model
- ⬜ Есть authority scopes на principal-уровне
- ⬜ Есть relation-anchor binding rules в runtime
- ⬜ Есть cross-channel principal linking
- ⬜ Есть audit trail для principal решений

## 8. Memory core

- ✅ Memory architecture зафиксирована в доках
- 🟡 Working memory реально читается в bridge bootstrap
- 🟡 Значимые ответы снова попадают в `events`
- 🟡 Memory update path живее, чем был, но всё ещё не полный
- 🟡 `facts` и `lessons` не автоматизированы безопасно
- ⬜ Есть полноценный memory core вне OpenClaw hooks
- ⬜ Есть clean episodic API уровня Sonya runtime
- ⬜ Есть clean semantic API уровня Sonya runtime
- ⬜ Есть consolidation pipeline под контролем Sonya runtime
- ⬜ Есть evaluation для memory fidelity

## 9. Provider и model layer

- ✅ Основная text/vision model и image model разведены
- ✅ Официальный OpenRouter path работает
- ✅ Retry/timeout path для bridge усилен
- ✅ Vision и image generation реально operational
- 🟡 Provider abstraction пока всё ещё живёт вокруг `tg-bridge`
- ⬜ Есть общий provider layer вне bridge package
- ⬜ Есть capability matrix для моделей
- ⬜ Есть policy выбора модели на уровне runtime
- ⬜ Есть унифицированный eval path по моделям
- ⬜ Есть provider-independent runtime contract

## 10. Telegram channel

- ✅ Bridge extracted into repo
- ✅ Живой Telegram polling и outbound path работают
- ✅ Text, vision и image generation operational
- ✅ Session storage operational
- ✅ Raw updates logging operational
- ✅ Post-response hook wiring operational
- ✅ `tg-bridge` больше не единственный путь к task/action логике
- 🟡 Bridge всё ещё остаётся основным боевым каналом и несёт часть planner logic
- ⬜ Telegram — это просто adapter к общему `sonya-core`, а не полу-мозг
- ⬜ Channel contract полностью обобщён для других поверхностей

## 11. Action contract

- ✅ Есть reusable action models вне `tg-bridge`
- ✅ Доступны `reply`, `generate_image`, `reply_and_generate_image`
- ✅ Добавлены `create_task`, `reply_and_create_task`
- ✅ Добавлены `ask_clarification` и `report_limitation`
- ✅ Anti-fake-agency правила встроены в planner prompt и policy слой
- 🟡 Planner всё ещё вызывается из bridge
- ⬜ Action planner полностью вынесен в общий runtime
- ⬜ Capability registry существует на уровне ядра
- ⬜ Action validation policy существует на уровне ядра
- ⬜ Action eval corpus существует отдельно от bridge tests

## 12. Reusable task runtime

- ✅ Есть reusable task payload schema
- ✅ Есть reusable task record schema
- ✅ Есть отдельный SQLite task store
- ✅ Task store не использует `memory.db`
- ✅ Есть `TaskService`
- ✅ Есть worker entrypoint `python -m sonya_runtime.tasks.worker`
- ✅ Есть bounded safe executor
- ✅ Bridge умеет создавать задачи
- ✅ Bridge умеет отвечать статусом задачи
- ✅ Задачи переживают текущий канал и могут быть запрошены позже
- 🟡 Worker пока ограничен только безопасными аналитическими task kinds
- ⬜ Есть scheduler-coordinated task runtime
- ⬜ Есть principal-aware task policy
- ⬜ Есть mutation-capable tasks с approval gate
- ⬜ Есть отдельный task telemetry/reporting layer

## 13. Anti-fake-agency discipline

- ✅ Модель больше не должна честно заявлять о фоновой работе без task record
- ✅ Planner теперь умеет возвращать task actions
- ✅ Channel не должен симулировать delayed work narrative
- 🟡 Полная дисциплина зависит от того, насколько стабильно planner выбирает task actions в реальном бою
- ⬜ Есть explicit eval set на fake-agency кейсы
- ⬜ Есть hard policy layer вне prompt-only enforcement
- ⬜ Есть regression suite на ложные claims о файловых действиях
- ⬜ Есть regression suite на ложные claims о времени и отложенной работе

## 14. Worker и executor

- ✅ Есть отдельный worker модуль
- ✅ Worker умеет claim -> execute -> done/failed
- ✅ Worker ограничен allowed task kinds
- ✅ Executor не делает произвольные записи в файловую систему
- ✅ Есть безопасные read-oriented handlers
- 🟡 Worker пока не управляется как полноценный сервис на уровне VPS-ready runtime
- ⬜ Есть worker supervision strategy
- ⬜ Есть worker queue metrics
- ⬜ Есть backoff/retry policy по task failures
- ⬜ Есть multi-worker coordination beyond SQLite locking

## 15. Planner и execution boundary

- ✅ Planner boundary теперь шире, чем просто reply/image generation
- ✅ Reply path, image path и task path существуют рядом
- ✅ Planner больше не должен выдавать fake background monologue как норму
- 🟡 Planner всё ещё сидит в `tg-bridge.app`
- ⬜ Общий planner живёт в `sonya-core`
- ⬜ Общий executor живёт вне bridge completely
- ⬜ Channel only renders canonical runtime outcomes
- ⬜ Planner output validation обобщён на весь runtime
- ⬜ Planner and executor telemetry unified

## 16. Sessions и working state

- ✅ Telegram sessions сохраняются
- ✅ Task refs теперь могут попадать в session history
- 🟡 Session model всё ещё bridge-specific
- ⬜ Общая session abstraction существует в runtime
- ⬜ Session summarization policy существует
- ⬜ Session pruning policy существует
- ⬜ Session continuity связывается с `subject_state`
- ⬜ Session-to-memory handoff formalized

## 17. Skills и capability growth

- ✅ Skill architecture задокументирована
- ⬜ Skill registry реализован
- ⬜ Skill loading реализован
- ⬜ Skill trust tiers реализованы
- ⬜ Skill testing contract реализован
- ⬜ Skill evolution runtime реализован
- ⬜ Planner умеет выбирать skill action
- ⬜ Capability graph включает skills как first-class entities

## 18. Harness и governance

- ✅ Harness documented as mandatory layer
- ⬜ Baseline harness implemented in code
- ⬜ Risk classes implemented
- ⬜ Immutable zones implemented
- ⬜ Approval gates implemented
- ⬜ Drift detection implemented
- ⬜ Self-modification gating implemented
- ⬜ Task mutation actions respect harness

## 19. Observability и operations

- ✅ Bridge logs существуют
- ✅ Health-check существует
- ✅ Worker и task runtime уже можно тестировать локально
- 🟡 Автозапуск и диагностика уже рабочие, но operational surface ещё не финальный
- ⬜ Structured logs across runtime
- ⬜ Metrics and counters
- ⬜ Task queue metrics
- ⬜ Planner decision telemetry
- ⬜ Dashboard/report path

## 20. Каналы beyond Telegram

- ✅ Архитектурно зафиксировано, что каналы — это поверхности одного субъекта
- ⬜ Discord channel существует
- ⬜ TTS renderer существует
- ⬜ Voice pipeline использует canonical response, а не отдельную личность
- ⬜ Web/admin surface существует
- ⬜ Channel registry существует
- ⬜ Cross-channel continuity реально operational
- ⬜ Principal linking across channels operational

## 21. Embodiment, simulation, future brain stack

- ✅ Это всё зафиксировано в docs и не потеряно
- ✅ RWKV/stateful future path учтён как отдельный research contour
- ⬜ Brain-state-specific data models реализованы
- ⬜ Stateful backend adapter реализован
- ⬜ Simulation contract реализован
- ⬜ Embodiment contract реализован
- ⬜ Physical body interface существует
- ⬜ Voice/avatar/body stack реально подвязан к одному subject core

## 22. Ближайший архитектурный долг

- 🟡 `tg-bridge` всё ещё держит planner вызов у себя
- 🟡 `subject_state` ещё нет как кода
- 🟡 `continuity_event` ещё нет как кода
- 🟡 Principal layer ещё нет как кода
- 🟡 Memory core ещё живёт через OpenClaw host truth
- 🟡 Worker есть, но ещё не service-grade
- ⬜ Следующий крупный шаг — поднять настоящий `src/sonya/`
- ⬜ После этого вынести planner из bridge в общий runtime
- ⬜ После этого связать task runtime с subject continuity и principal policy

## Финальное правило

Этот файл обязан оставаться честным.

Если в проекте по факту есть docs, `tg-bridge`, частичный reusable runtime и OpenClaw host, то так и должно быть написано.

Смысл этого файла в том, чтобы проект не врал себе про степень своей готовности.
