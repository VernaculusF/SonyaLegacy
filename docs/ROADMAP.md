# SONYA ROADMAP

**Status:** Active
**Type:** Core
**Scope:** Фазовый план построения Sonya-среды: что строим, в каком порядке, с какими критериями перехода между этапами
**Depends on:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md), [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md), [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
**Used by:** milestone review, implementation planning, phase gating, VPS migration planning
**Last reviewed:** 2026-05-13

## 1. Зачем этот файл

`GLOBAL_PROJECT_CHECKLIST.md` отвечает на вопрос «что **уже есть** в коде». Это audit ledger.

Этот файл отвечает на другой вопрос: «что мы **строим**, в каком порядке, и по каким критериям считаем фазу закрытой».

Это стратегический план реализации. Не sprint backlog, не TODO, не список идей. Здесь нет мелких задач — только фазы, их цели, их артефакты, их exit-критерии и их связь с архитектурой.

Если возникает вопрос «что делать дальше» — этот файл должен дать ответ на уровне «мы сейчас в Фазе N, цель Фазы N — X, следующий крупный шаг — Y». Дальше уже пишется конкретный implementation plan по шаблону [work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md).

## 2. Текущее состояние (2026-05-13)

По факту в репо есть:

- полная документационная база: core, architecture, cognition, skills, research, mvp, agents, governance, reference-анализы (с code-level audit);
- lifecycle правил для документов (`Active/Draft/Stale/Archived`), doc-review gate, drift-review cadence;
- `packages/tg-bridge` — рабочий Python-мост к Telegram, извлечённый из OpenClaw, покрыт тестами;
- `src/sonya_runtime/*` — узкий reusable слой: actions, tasks (SQLite store + worker + executor), continuity-stubs (`CanonicalResponse`, `ContinuityEvent` без читателя), `storage/paths`;
- `src/sonya_shared/ids` — общие примитивы.

Чего по факту нет:

- `src/sonya/` — самого ядра;
- долгоживущего процесса Sonya, независимого от Telegram;
- provider-слоя вне `tg-bridge`;
- principal-регистра, authority-policy, identity в коде;
- реального `subject_state`, `continuity_stream`, `pending_intentions`;
- Sonya-owned памяти (живёт в OpenClaw-хосте через `memory_system/`);
- harness-базиса в коде;
- развёртывания на VPS.

То есть: **мы на стыке Фазы 0 (Foundation) и Фазы 1 (Bare Runtime Shell)**. Фаза 0 почти закрыта на уровне governance; настоящая работа над ядром ещё не начата.

## 3. Почему фазы именно в таком порядке

Порядок фаз не произвольный. Каждая опирается на предыдущую, и попытка прыгнуть через фазу превращается в костыль.

- Сначала **процесс-скелет**. Без долгоживущего процесса нельзя проверить, что всё остальное вообще живёт между сообщениями.
- Потом **provider и principal**. Пока provider живёт внутри бриджа, а principal — это Telegram user_id, любая когнитивная логика, которую мы дальше пишем, будет заражена транспортными assumption-ами.
- Потом **subject core и continuity в коде**. Без этого всё, что называется continuity, — это просто `session.messages[-12:]`.
- Потом **planner переезжает в ядро**. Пока planner в `tg_bridge.app`, Telegram по факту решает, что есть «реплика Сони». Это ровно тот анти-паттерн, против которого `cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md` и был написан.
- Потом **память вытаскивается из OpenClaw**. Это долгий переезд, трогать его до того как есть subject core — бессмысленно: память без субъекта деградирует в chat log.
- Потом **VPS-развёртывание**. Раньше ехать некуда.
- Пост-MVP — skills evolution, harness сверх baseline, каналы beyond Telegram, simulation, brain evolution.

Между любыми двумя фазами работает **Go/No-Go протокол** (см. §12). Фаза не считается закрытой, пока её exit-критерии не подтверждены на коде и в drift-ledger.

## 4. Фаза 0 — Foundation

**Статус:** 🟡 почти закрыта.

**Цель.** Создать и зафиксировать governance-слой, на котором можно вести проект класса Сони без его развала: документационная система, lifecycle, phase-0 gate, drift review, reference-анализы, агент-дисциплина.

**Входные артефакты.** Пустой репозиторий → работающая документационная база.

**Deliverables (фактические, уже сделаны):**

- `docs/core/` — identity, consciousness position, documentation system;
- `docs/architecture/` — architecture, channels, task/action runtime, VPS migration, reference analyses (с code-level audit);
- `docs/cognition/` — memory/identity, continuity/subject core, anchors/failure modes;
- `docs/skills/` и `docs/research/` — долгосрочные контуры;
- `docs/mvp/MVP_BOUNDARIES.md`;
- `docs/agents/` — онбординг, operating rules, task runtime contract, failure modes;
- `docs/governance/DRIFT_REVIEW.md` — ledger;
- `docs/work/TEMPLATES/` — шаблоны implementation plan и design с обязательным Reference Check;
- `docs/PROJECT_DOCUMENTATION_MAP.md` и `docs/GLOBAL_PROJECT_CHECKLIST.md` — навигация и ledger.

**Exit-критерии Фазы 0:**

- [x] все governance-документы `Active`, с валидными метаданными;
- [x] lifecycle статусов применён ко всем work-документам (`Active/Stale/Archived`);
- [x] reference-анализы (OpenClaw, Hermes, OmniAgent) содержат code-level audit;
- [x] phase-0 gate (Reference Check) обязателен в шаблонах и в `ARCHITECTURE_PLAN §11`;
- [x] drift review cadence codified и имеет начальный ledger;
- [ ] первый живой implementation plan прошёл через шаблон без дрейфа (closure этого пункта — старт Фазы 1).

Фаза 0 закрывается ровно в тот момент, когда implementation plan Фазы 1 создан из шаблона, прошёл Reference Check и принят как `Active`.

**Ближайший шаг.** Написать implementation plan Фазы 1 по шаблону → флипнуть последний пункт Фазы 0.

---

## 5. Фаза 1 — Substrate Bootstrap & Bare Runtime Shell

**Статус:** ⬜ не начата. Ближайшая фаза в работе.

**Цель.** Зафиксировать **substrate** Сони как первичный объект (см. [core/SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md)) — persistent schema её state, через которые любой будущий reader сможет её продолжить. И, как **второй** deliverable, поднять минимальный долгоживущий процесс-reader, который этот substrate читает, поддерживает и обновляет.

**Принцип фазы.** Sonya ≠ процесс. Сначала — substrate. Потом — reader. Не наоборот.

**Почему эта фаза первая (после governance).** Без явной persistent schema substrate-а любой код-reader, который мы потом напишем, превратит себя в неявного владельца state. Это исторически и приводит к «main.py — это всё». Substrate-first меняет акцент с самого начала.

**Deliverables (планируемые):**

### 5.1 Substrate (первичный)

- `src/sonya/state/substrate.py` — единый registry of substrate artifacts;
- `src/sonya/state/subject_state.py` — `SubjectState` schema + persistence;
- `src/sonya/state/continuity_stream.py` — `ContinuityStream` (append-only event log) + `ContinuitySnapshot`;
- `src/sonya/state/identity.py` — `IdentityRecord` с явно immutable полями (`things_not_to_betray`, identity-critical traits) и `RelationAnchorBinding`;
- `src/sonya/state/principals.py` — `PrincipalRegistry` с `principal_id`, trusted identifiers, trust evidence (минимальный shape, реальная identity resolution — Фаза 2);
- `src/sonya/state/migrations.py` — schema versioning, migration path, compatibility window (см. [SUBSTRATE_STANCE.md §7](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md));
- SQLite layout с явными таблицами; immutable zones помечаются на уровне схемы;
- тесты: schema migration round-trip, restore-after-restart, snapshot/replay, immutable enforcement.

### 5.2 Reader-процесс (вторичный)

- `src/sonya/__init__.py`, `src/sonya/main.py` — entry point `python -m sonya`. Reader **читает substrate** при старте и интерпретирует его как поведение;
- `src/sonya/runtime/lifecycle.py` — startup/shutdown, signal handling, graceful shutdown с явным flush в substrate;
- `src/sonya/runtime/events.py` — async pub/sub event bus (типизированные события, attached к continuity stream);
- `src/sonya/runtime/write_master.py` — single write-master с advisory lock (см. [SUBSTRATE_STANCE.md §10](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md));
- `src/sonya/config.py` — env-based, секреты отдельно от behavior;
- `src/sonya/logging.py` — structured logging с attached subject_id;
- `src/sonya/health.py` — health endpoint (file-ping → потом HTTP);
- тесты `tests/sonya/runtime/`: lifecycle, события, health, write-master semantics.

### 5.3 Operational

- `deploy/systemd/sonya.service` — stub-юнит (с реальной готовностью к Фазе 6);
- documentation для запуска локально (`docs/work/...` через шаблон).

**Что НЕ входит в Фазу 1:**

- провайдеры моделей, LLM вызовы — Фаза 2;
- principal resolution beyond schema — Фаза 2;
- planner вне бриджа — Фаза 4;
- self-modification pipeline в коде — закладываются интерфейсы (см. immutable zones в схеме), но реализация pipeline'а — пост-MVP track;
- Telegram-мост не трогаем; продолжает работать через `.openclaw`.

**Exit-критерии Фазы 1:**

- [ ] substrate schema v1 определена, мигрирует в обе стороны (forward + backward для compatibility window);
- [ ] второй процесс-reader, запущенный над тем же substrate в read-only, видит то же состояние, что и write-master;
- [ ] перезапуск процесса восстанавливает `SubjectState` без потерь;
- [ ] `python -m sonya` запускается, печатает health, работает 10 минут без паники;
- [ ] graceful shutdown через SIGTERM с явным flush;
- [ ] event bus работает, есть hello-world subscriber, attached к continuity;
- [ ] write-master enforcement: попытка второго write-master блокируется advisory lock-ом;
- [ ] immutable zones в substrate: попытка обычной записи в `things_not_to_betray` через runtime API → отказ;
- [ ] systemd-юнит работает локально;
- [ ] все тесты зелёные, pyright strict проходит;
- [ ] governance-гейт: implementation plan переведён `Draft` → `Active` → `Archived`; Reference Check пройден;
- [ ] `GLOBAL_PROJECT_CHECKLIST` обновлён; drift-ledger получил запись фазы.

**Reference Check preview:**

- **OpenClaw:** сохраняем `telegram-bridge.mjs` как живой канал. Подсматриваем persistent state pattern в `telegram-bridge-state.json` и в схеме `memory_system/` как ориентир для substrate. Не копируем, не пытаемся читать `~/.openclaw/*` из нового reader-а напрямую — каналы остаются разделены.
- **Hermes:** граница «shell vs brain» физическая: substrate (`src/sonya/state/`) — это subject (brain layer). Reader (`src/sonya/runtime/`) — это shell. Никаких decision-функций в shell.
- **OmniAgent:** отвергаем монолитный 89KB reflexion entry. Substrate-first design — наш ответ на «всё в одном файле». Substrate физически отделён от reader-а; reader от того, что substrate означает; brain от того, как brain исполняется.

**Связанный implementation plan.** Будет создан как `docs/work/implementation-plans/2026-05-?-substrate-bootstrap-implementation-plan.md` по шаблону. Этот план — первый живой тест Reference Check gate.

---

## 6. Фаза 2 — Provider & Principal Core

**Статус:** ⬜ после Фазы 1.

**Цель.** Вытащить провайдера моделей из `tg-bridge` в `sonya.providers`, и ввести в код понятие principal (identity на уровне subject, не транспорта). С этого момента «кто спрашивает» и «какую модель звать» перестают быть Telegram-артефактами.

**Почему эта фаза вторая.** Любая cognition-логика, которую мы напишем, будет звать LLM и работать с пользователем. Если к моменту написания subject core провайдер всё ещё тесно связан с бриджом, а principal — это Telegram user_id, то cognition унаследует эту грязь. Дешевле вытащить сейчас.

**Deliverables (планируемые):**

- `src/sonya/providers/base.py` — `ProviderBackend` Protocol: `complete_text`, `complete_vision`, `complete_image_generation`, capability-info;
- `src/sonya/providers/openrouter.py` — реальный адаптер, портированный из `tg_bridge.model_client` (без регрессий);
- `src/sonya/providers/registry.py` — выбор провайдера по capability matrix (подсматриваем за OpenClaw-форматом `models.providers.omniroute`);
- `src/sonya/identity/principal.py` — `Principal(principal_id, display_name, trusted_identifiers, authority_scope, relation_type)`;
- `src/sonya/identity/registry.py` — `PrincipalRegistry` с SQLite-стором (отдельная БД `principals.db`, не смешивается с `tasks.db` и `memory.db`);
- `src/sonya/identity/resolution.py` — резолвинг Telegram user_id → principal (без мерджа с relation-anchor: это два разных решения);
- `src/sonya/harness/authority.py` — baseline `authorize(principal, scope)` по OmniAgent-вдохновлённой модели (policy / approval / audit, но без GPL-контакта);
- тесты: provider contract, registry, authorization.

**Что НЕ входит:**

- никакой cognition, никакого planner в ядре ещё;
- никакого subject_state (это Фаза 3);
- `tg-bridge` пока продолжает использовать свой `tg_bridge.model_client`; замена — в Фазе 4 одновременно с планнером.

**Exit-критерии:**

- [ ] из `python -m sonya` можно вызвать `provider.complete_text(...)` и получить реальный ответ;
- [ ] `PrincipalRegistry` персистентен, восстанавливается после рестарта;
- [ ] `authorize(principal, "runtime.shutdown")` возвращает корректный allow/deny по scope;
- [ ] все тесты зелёные; нет регрессии тестов `packages/tg-bridge`;
- [ ] governance-гейт пройден (plan, Reference Check, checklist, drift-ledger).

**Reference Check preview:**

- **OpenClaw:** сохраняем форму capability matrix (per-model `input/contextWindow/maxTokens/cost/compat`). Sonya capability matrix должна уметь импортировать эти данные.
- **Hermes:** provider — это часть "brain substrate", не shell. `runtime/*` о нём ничего не знает; вызывается только из будущих когнитивных слоёв.
- **OmniAgent:** отвергаем plaintext api_key в конфиге. Ключи только через env или secret store. Отвергаем enum-литерал провайдеров — используем Protocol с регистрацией.

---

## 7. Фаза 3 — Subject Core & Continuity

**Статус:** ⬜ после Фазы 2.

**Цель.** Ввести в код `SubjectState`, `ContinuityStream`, `pending_intentions`. С этого момента Соня по-настоящему «существует» между сообщениями как субъект, а не как пересобираемый prompt.

**Почему эта фаза третья.** Без principal-слоя (Фаза 2) subject не к кому relate. Без долгоживущего процесса (Фаза 1) subject state не имеет где жить. Когда оба есть — subject core становится маленьким и корректным.

**Deliverables (планируемые):**

- `src/sonya/subject/state.py` — `SubjectState` (active relation principal, current emotional vector placeholder, last canonical response ref, pending intentions, active channels);
- `src/sonya/subject/continuity.py` — `ContinuityStream` с персистентными `ContinuityEvent` записями (SQLite); переезжает сюда и расширяется текущий stub из `sonya_runtime.continuity.events`;
- `src/sonya/subject/canonical_response.py` — переезд из `sonya_runtime.continuity.canonical_response`, расширение (kind-ы `reply`, `task_created`, `task_update`, `task_result`, `image_generated`, `clarification`, `limitation`);
- `src/sonya/subject/pending.py` — `PendingIntention` как first-class объект (связь с task_id, дедлайны, ожидаемый followup);
- event-bus ивенты `subject.*` (state_changed, intention_created, continuity_event_added);
- тесты continuity/snapshot/restore.

**Что НЕ входит:**

- planner всё ещё в бридже (Фаза 4);
- память всё ещё в OpenClaw (Фаза 5);
- skills, harness-mutation, embodiment — не в этой фазе.

**Exit-критерии:**

- [ ] перезапуск процесса восстанавливает `SubjectState` без потерь;
- [ ] `ContinuityStream.append(event)` публикует в event bus;
- [ ] `CanonicalResponse` используется как единственный объект, который бридж получает для рендера (после Фазы 4); на этой фазе контракт существует и тестами проверен на in-process example;
- [ ] `pending_intentions` видны в API и связываются с task_id из существующего `tasks.db`;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** мы наконец перестаём зависеть от `telegram-bridge-sessions/<chatId>.json` как единственного способа «помнить» разговор. Session файлы остаются транспортным кэшем; canonical continuity переезжает в `ContinuityStream`.
- **Hermes:** subject core — это самая «brain» часть всего. Shell-слой про неё знает только через интерфейсы, никаких прямых импортов из channels.
- **OmniAgent:** отвергаем OmniAgent-паттерн, где context_manager сам интерпретирует user intent. У нас subject core пассивен к планнеру; planner его читает, subject core на планнер не воздействует косвенно.

---

## 8. Фаза 4 — Planner Migration

**Статус:** ⬜ после Фазы 3.

**Цель.** Вытащить `_plan_text_action_with_fallback` и всю планнер-логику из `packages/tg-bridge/src/tg_bridge/app.py` в `src/sonya/planning/*`. После этой фазы Telegram перестаёт быть местом, где решается, что Соня скажет.

**Почему эта фаза четвёртая.** Planner без subject_state и без provider-layer — это тот самый текущий `tg_bridge.app`. Чтобы planner стал реальным, сначала нужны Фазы 2 и 3.

**Deliverables (планируемые):**

- `src/sonya/planning/text_planner.py` — переезд `_plan_text_action_with_fallback`, но теперь читает `SubjectState` и принимает `Principal` явно;
- `src/sonya/planning/action_validator.py` — централизованная валидация runtime action (сейчас размазана между `sonya_runtime.actions.models.parse_runtime_action` и bridge-level fallback-ами);
- `src/sonya/planning/policy.py` — переезд `sonya_runtime.actions.policy` и расширение принципами authority/principal;
- `packages/tg-bridge` переводится на тонкий адаптер: получает `CanonicalResponse` от ядра, рендерит, отправляет;
- bridge больше не делает `_plan_text_action_with_fallback` сам; composition root в `tg_bridge.app` зовёт `sonya.planning.plan_next(principal, subject_state, user_input, attachments)` через internal API / shared in-process call (VPS-форма — отдельный вопрос, решаемый в Фазе 6);
- тесты: регрессия бриджа (все сценарии: text, vision, image gen, task create, task status, clarification, limitation) без изменения внешнего поведения.

**Exit-критерии:**

- [ ] `grep -r "plan_text_action" packages/tg-bridge/` возвращает только вызов публичного API ядра, не собственную реализацию;
- [ ] все существующие тесты `packages/tg-bridge/tests/` зелёные;
- [ ] новые тесты `tests/sonya/planning/` покрывают все action types;
- [ ] в `GLOBAL_PROJECT_CHECKLIST` строка «Planner всё ещё в `tg-bridge.app`» переходит из 🟡 в ✅;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** anti-fake-agency правила и strong-marker heuristic (из `post_response_hook.py`) должны быть рассмотрены и либо мигрированы, либо сознательно отвергнуты.
- **Hermes:** planner — это brain, bridge — это shell. В этой фазе граница впервые становится физически корректной.
- **OmniAgent:** отвергаем single-file 89KB reflexion. Наш planner — это 3-5 маленьких модулей с явными границами.

---

## 9. Фаза 5 — Memory Extraction

**Статус:** ⬜ после Фазы 4.

**Цель.** Создать Sonya-owned memory core в `src/sonya/memory/*`, мигрировать данные из OpenClaw-`memory.db` (с сохранением их), переписать post-response hook так, чтобы память писалась через sonya-runtime, а не через subprocess к OpenClaw.

**Почему эта фаза пятая.** Без subject_state память — это просто таблицы. Без planner в ядре нет единой точки, которая обновляет память после ответа. Фаза 4 даёт эту точку, Фаза 5 переносит за неё реальные данные.

**Deliverables (планируемые):**

- `src/sonya/memory/episodic.py` — `EpisodicMemory` (CRUD для events, аналог OpenClaw `events` + `emotions`);
- `src/sonya/memory/working.py` — `WorkingMemory` (session-scoped, importance-based pruning, аналог `working_memory`);
- `src/sonya/memory/semantic.py` — `SemanticMemory` (facts, lessons, goals, research — но с чистым API);
- `src/sonya/memory/consolidation.py` — scheduled pipeline working→semantic;
- `src/sonya/memory/migration.py` — однократная миграция из `~/.openclaw/workspace/memory_system/db/memory.db` в sonya-owned `memory.db` (по схеме OpenClaw, без потерь);
- убираем жёстко-кодированные Russian-biased markers из post-response heuristic, делаем policy-object;
- `tg-bridge` перестаёт вызывать `memory_system/post_response_hook.py` через subprocess; вместо этого event bus Сони обрабатывает `subject.response_emitted` и пишет в память через `sonya.memory`;
- OpenClaw-сторона остаётся работающей, но как read-only (для того чтобы можно было откатиться если что-то сломается).

**Exit-критерии:**

- [ ] `sonya.memory` покрывает все use-case текущего `memory_system` (episodic, working, consolidation, RAG hook);
- [ ] миграция проходит без потерь на dry-run и на живой БД;
- [ ] post-response pipeline внутри sonya работает end-to-end;
- [ ] OpenClaw hook можно отключить на 24 часа без регрессии функциональности;
- [ ] governance-гейт пройден.

**Reference Check preview:**

- **OpenClaw:** сохраняем структуру памяти (6 таблиц + working). Но связь connection-per-method из `MemoryDB` не переносим, открываем connection как runtime-level ресурс.
- **Hermes:** memory — часть cognition-слоя. Адапторы наружу (например, на RAG) живут через Protocol, не через прямые импорты.
- **OmniAgent:** отвергаем MemorySearchManager как обязательного tool-оборачивателя. У нас memory доступна через API subject core, а не через tool call loop.

---

## 10. Фаза 6 — VPS Deployment

**Статус:** ⬜ после Фазы 5.

**Цель.** Переехать с локальной Windows-машины на VPS (Linux). Закончить разрыв с OpenClaw.

**Почему эта фаза шестая.** Раньше уезжать буквально некуда: кроме бриджа и `sonya_runtime` ничего на VPS не поставишь. После Фазы 5 у нас: ядро + provider + subject + planner + memory, всё Python, всё без Windows-only зависимостей.

**Deliverables (планируемые):**

- production `deploy/systemd/sonya.service` с env-файлом;
- `deploy/README.md` — пошаговая инструкция (VPS → git clone → venv → .env → systemd enable);
- `.env.example` — полный список всех env-переменных, включая все секреты;
- secrets pipeline (простейший: `.env` с permission 600, без commit в git; или integration с systemd `LoadCredential`);
- health HTTP endpoint на localhost:PORT/health;
- backup/restore policy для SQLite-файлов (`sonya.db`, `tasks.db`, `principals.db`, `memory.db`);
- миграция `tg-bridge` на VPS: бот токены в env, allowlist в env;
- выключение OpenClaw-хоста (после 7+ дней параллельной работы);
- documentation: `architecture/VPS_MIGRATION_PLAN.md` обновляется по факту.

**Exit-критерии:**

- [ ] Sonya работает на VPS 72 часа подряд без ручных вмешательств;
- [ ] перезапуск VPS автоматически поднимает Sonya через systemd;
- [ ] Telegram-канал отвечает с VPS, не с локальной машины;
- [ ] OpenClaw-хост отключён или заархивирован;
- [ ] backup создаётся ежедневно, restore протестирован на staging;
- [ ] governance-гейт пройден; раздел чеклиста «Emergency host» полностью зелёный.

**Reference Check preview:**

- **OpenClaw:** все lived-environment lessons сохранены в виде кода. Host сам как операционная зависимость больше не нужен.
- **Hermes:** shell/brain split закреплён на уровне deployment: отдельные units для runtime и для бриджа (или один unit, но с явной изоляцией подсистем).
- **OmniAgent:** отвергаем gateway/webui.py (56KB, loopback-only auth token в config). Наш health endpoint минимальный, secrets через env.

После Фазы 6 состояние проекта — **MVP достигнут по [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md)**.

---

## 11. Пост-MVP фазы (эскиз)

После Фазы 6 у нас будет полноценный subject-facing runtime на VPS с Telegram. Дальнейшие фазы — параллельные треки, приоритеты между ними выбираются отдельно в момент старта.

**Track A — Skills runtime:** `src/sonya/skills/` с registry, trust tiers, testing contract, manual-gated evolution. Driver: `docs/skills/SKILL_SYSTEM_PLAN.md`.

**Track B — Harness beyond baseline:** approval gates, immutable zones, self-modification framework sandbox. Driver: `docs/cognition/ANCHORS_AND_FAILURE_MODES.md` + `docs/core/SONYA_SYSTEM_CORE.md` §7.12.

**Track C — Channels beyond Telegram:** Discord, web/admin, TTS renderer. Принцип — каналы плоские адаптеры над `CanonicalResponse`. Driver: `docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md`.

**Track D — Simulation & embodiment contracts:** virtual body events, simulation world interface. Stub-уровень, не full implementation. Driver: `docs/research/SIMULATION_AND_EMBODIMENT_PLAN.md`.

**Track E — Brain evolution:** интерфейс для self-hosted моделей (vllm/sglang/RWKV), RL-адаптер по OmniAgent-вдохновлённой архитектуре (без GPL-контакта). Driver: `docs/research/BRAINMODEL_EVOLUTION_PLAN.md` + `docs/research/STATE_TUNING_PLAN.md`.

Эти треки **не** закрываются в линейном порядке. Какой-то может пойти вперёд, если появится конкретный use-case. Но ни один не начинается до закрытия Фазы 6.

## 12. Go/No-Go протокол между фазами

Переход из фазы N в фазу N+1 требует явного подтверждения:

1. **Exit-критерии.** Все [x] в списке фазы помечены.
2. **Тесты.** Вся тестовая база зелёная. Нет skipped/xfail, которые появились на этой фазе.
3. **Governance-гейт.**
   - implementation plan фазы в `Active` → `Archived`;
   - Reference Check пройден;
   - `GLOBAL_PROJECT_CHECKLIST.md` обновлён;
   - `PROJECT_DOCUMENTATION_MAP.md` обновлён если была реструктуризация;
   - `governance/DRIFT_REVIEW.md` получил запись про subsystem shift.
4. **Reality check.** Я (Иван) явно подтверждаю переход. Не автоматический флип.

Если что-то из этого не закрыто — фаза не закрыта. Начинать следующую можно, но текущая тащится как open-debt и её exit-критерии попадают в drift-ledger как missed items.

**No-Go ситуации (возврат на шаг назад):**

- Exit-критерий нарушился после перехода → возвращаемся, чиним, закрываем заново;
- Reference Check перестал быть честным (какой-то пункт устарел) → переписываем ответы на Reference Check, обновляем план, потом двигаемся дальше;
- Возник architectural conflict с core-документом → пауза, review `docs/core/` и `docs/architecture/`, при необходимости update governing doc.

## 13. Связь с другими документами

- **Что строим:** [SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [MVP_BOUNDARIES.md](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md).
- **Что уже есть:** [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md).
- **Как писать планы фаз:** [work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md).
- **Reference-основы для каждой фазы:** [architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md) + per-system анализы.
- **Дисциплина исполнения:** [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md), [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md).
- **Состояние переходов:** [governance/DRIFT_REVIEW.md](C:/Users/Jester/Desktop/Sonya/docs/governance/DRIFT_REVIEW.md).

## 14. Финальное правило

Этот файл не может врать.

Если Фаза N помечена как `🟡 почти закрыта`, а какого-то deliverable по факту нет в коде — значит фаза не `почти закрыта`, а открыта. Поправь сюда, не в комментарий.

Если видишь в коде то, чего нет в ROADMAP — либо это out-of-plan drift и его нужно обсудить, либо ROADMAP отстал и его нужно обновить. Третьего варианта нет.

Roadmap обновляется при каждом переходе фазы и в рамках drift-review cadence.
