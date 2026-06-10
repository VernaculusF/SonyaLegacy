# HANDOFF.md — текущая точка продолжения

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-10

## Immediate continuation - current

Deployed baseline: `bae4b33`, substrate schema v33, OpenRouter encrypted main
account, 339 discovered models, and active `sonya` / `sonya-admin` services.

Current slice:

1. import remaining approved provider accounts through protected secret
   ingestion;
2. add periodic provider refresh and measured scorecards;
3. complete subagent lifecycle/scope/outcome tracing;
4. inventory and migrate old memory and knowledge with backups, provenance, and
   idempotent manifests;
5. return to Atrium later.

Completed in the latest slices:

- Admin Providers now renders provider pools, accounts, models, quotas,
  observations, protected secret rotation, and a collapsed legacy-key view;
- typed manual refresh/probe endpoint and substrate-backed lifecycle adapter
  factory added;
- VPS verification: `48 passed` for the broad provider/Admin/routing slice and
  `26 passed` for refresh/factory/Admin; compileall passed; both services active;
- production visual review remains blocked by authenticated Admin access;
- interactive SSH live refresh correctly refused to resolve encrypted secrets
  without the systemd-only deployment unlock material.
- read-only production memory inventory recorded in
  `docs/operations/MEMORY_KNOWLEDGE_MIGRATION_STATUS.md`: 13,273 episodic
  events, 3,346 semantic facts, 1 raw trace, 20 procedural memories, 23,238
  continuity events, 242 tool experiences, and 12 knowledge files.
- read-only `sonya.tools.memory_migration_manifest` implemented; it emits only
  row counts, schemas, paths, sizes, hashes, and legacy-source categories.
  Live substrate manifests use a fast inventory fingerprint; full DB hashing is
  opt-in for offline/backup copies.
- unsafe plain-copy fallback in `deploy/backup.sh` was replaced with Python's
  SQLite Backup API fallback for VPS installations without the `sqlite3` CLI.
- production WAL-safe backup, gzip integrity, offline full hash, and
  `PRAGMA quick_check=ok` were proven; manifest now includes safe provenance
  distributions without content fields.
- exact duplicate counting is explicit `--analyze-duplicates` backup-only
  analysis; it reports group/extra-row counts without values.
- semantic exact-dedup tool added: dry-run by default, backup-confirmation
  required for apply, preserves provenance, and never deduplicates episodic
  events by content.

Do not run the application locally. Do not expose credentials in Git, docs,
prompts, commands, logs, or continuity. See
`docs/operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md`.

---

## Immediate continuation — provider/model runtime

Documentation-only design work completed on 2026-06-10:

- created `docs/operations/PROVIDER_SYSTEM_DESIGN.md`;
- created `docs/operations/PROVIDER_MODEL_CATALOG.md`;
- rewrote `docs/operations/SUBAGENT_MODELS.md` as selection policy;
- rewrote `docs/operations/FREEMODEL_BRIDGE.md` as a research-gated adapter plan;
- created design and implementation plan under `docs/superpowers/`.

No pasted credential was added to Git, substrate, logs, or runtime.

Provider foundation implementation completed after the documentation pass:

- substrate schema advanced from v31 to v33;
- provider registry, accounts, account offerings, quota windows, and
  observations added;
- legacy key writes/migration mirror into accounts without moving raw secrets;
- typed KeyStore CRUD/read APIs added;
- existing `provider_models` read bug around omitted `text_loop_ok` fixed.
- encrypted `provider_secrets` added for new account credentials;
- `provider_accounts` now expose only `secret_ref` and `secret_masked`;
- `resolve_account_secret()` is the explicit raw-secret boundary for adapters;
- legacy `provider_keys` remain compatible until the old inference path is
  migrated.
- provider adapter contract added under `src/sonya/providers/adapters/`;
- OpenAI-compatible and Google-native adapter skeletons implemented with
  structured discovery, health checks, quota hooks, and generic inference.
- `ProviderRefreshService` added under `src/sonya/providers/refresh.py`;
- refresh records health, discovery observations, quota windows, and
  active-account model offerings;
- discovery failures preserve the last-good cached model pool;
- `providers.list_models` now reads substrate provider model pools and account
  offerings instead of Fireworks live catalog / hardcoded model lists.
- subagent model picking now scores only active substrate offerings, with role,
  cost, latency, context, and `ToolExperience` history as soft ranking signals;
- `_PURPOSE_MODEL_HINT` is empty and no longer forces Fireworks or any fixed
  model by purpose;
- `LLMProvider` provider fallback chain is derived from available offerings and
  eligible keys instead of a fixed provider list;
- `SubagentTool` checks substrate `text_loop_ok` before spawning text-loop
  workers;
- writable open now repairs legacy v33 `provider_models` tables that are
  missing newer routing columns.
- `ProvidersTool` now manages provider registry rows, provider accounts,
  account offerings, and provider quota/health observations;
- Admin `/api/providers` now exposes providers, accounts, model pools,
  available models, quota windows, observations, and legacy keys;
- Admin has POST endpoints for provider registry, accounts, and account
  offerings;
- Atrium only treats `provider.*` events as system/status stream entries;
  detailed provider CRUD remains in Admin.
- provider/model/account selection is explicitly substrate-owned, not env-owned;
- legacy `SONYA_LLM_MODEL`, `SONYA_LLM_API_BASE`, and provider-specific env
  secret loading were removed from `AppConfig`;
- admin chat now uses the same substrate-backed `LLMProvider` path as the core
  runtime, rather than a separate env-bound OpenRouter backend.
- provider-specific environment secret loading was removed; future bootstrap
  must use a protected secret-ingestion action that writes encrypted account
  secrets into substrate without argv/continuity/tool-trace exposure.
- protected secret ingestion is implemented as authenticated Admin
  `PUT /api/providers/accounts/{account_id}/secret` with an opaque
  `application/octet-stream` body; it encrypts/rotates immediately and returns
  only a mask/reference.
- ordinary provider-account JSON/tool paths and legacy key-add JSON/tool paths
  reject raw credentials; legacy key reads remain for migration compatibility.
- current provider-runtime status is summarized in
  `docs/operations/PROVIDER_RUNTIME_STATUS.md`.

Verification:

- local focused provider suite: `34 passed`
- local migration/provider suite: `36 passed`
- local real-substrate-copy migration: v32, provider/account mirror present
- local provider/migration/secret suite: `66 passed`
- local v33 real-substrate-copy migration: masked account metadata present
- full local suite: `847 passed`, `7 skipped`, `11 failed`; remaining failures
  are in pre-existing dirty memory/visual-recall/purpose-hint areas outside this
  slice
- VPS isolated provider/migration suite: `50 passed`
- VPS real-substrate backup migration: v32 with `4 providers`, `10 accounts`,
  `10 keys`
- VPS isolated provider/migration/secret suite: `66 passed`
- VPS v33 real-substrate backup migration: `4 providers`, `10 accounts`,
  `10 keys`, `10 masked accounts`
- local provider adapter/foundation suite: `83 passed`
- VPS isolated provider adapter/foundation suite: `83 passed`
- VPS adapter import + real-substrate backup migration smoke passed
- local provider refresh/foundation suite: `87 passed`
- local compile smoke passed for provider modules and `providers_tool.py`
- local secret-prefix scan found no pasted credential prefixes
- VPS isolated provider refresh/foundation suite: `87 passed`
- VPS refresh import + real-substrate backup migration smoke passed
  (`schema_version=33`, `4 providers`, `10 accounts`, `10 keys`,
  `10 masked_accounts`)
- local provider/routing suite: `108 passed`
- local routing compile smoke passed
- local routing/default grep found no Fireworks DeepSeek or fixed fallback
  references in routing/default files
- VPS isolated provider/routing suite: `108 passed`
- VPS real-substrate backup migration/routing smoke passed after repairing
  missing legacy `provider_models` columns. Production substrate settings still
  point at the live configured provider; production DB was not modified.
- local provider/routing/management suite: `113 passed`
- local provider management compile smoke passed
- local Atrium build passed
- local secret-prefix scan found no pasted credential prefixes
- VPS isolated provider/routing/management suite: `113 passed`
- VPS real-substrate backup management smoke passed
  (`schema_version=33`, `4 providers`, `10 accounts`, `10 keys`,
  `10 masked_accounts`, `17 models`, `0 available_models`)
- local substrate-owned provider-binding slice: `65 passed`
- VPS isolated substrate-owned provider-binding slice: `65 passed`
- local/VPS runtime grep confirms no env model/provider binding remains
- local protected-ingestion/provider/routing suite: `122 passed`
- local compile smoke and known-secret-prefix scan passed
- isolated VPS protected-ingestion/provider/routing suite: `122 passed`
- VPS live-substrate-copy protected-ingestion smoke passed; rotation produced
  `inactive` then `active` and plaintext was absent from the SQLite dump
- earlier isolated proof did not modify production; the provider runtime was
  subsequently deployed with the rollback backup listed below
- production provider runtime deployed on 2026-06-10 with rollback backup:
  `/home/jester-sonya/backups/sonya-provider-20260610-050736`
- production substrate migrated to v33
- main OpenRouter account migrated to encrypted `provider-secret`; legacy
  plaintext cleared
- OpenRouter live discovery succeeded (`339` models, `27` observed free)
- nested OpenRouter pricing normalization and explicit-provider free preference
  were fixed after live smoke exposed them
- live Gemma adapter inference and main `LLMProvider` inference both succeeded
- `sonya` and `sonya-admin` are active; core logs
  `thinking_provider_ready` for OpenRouter
- production-source provider verification: `126 passed` (`119 + 7` async)

Next implementation slice:

1. Execute Task 8 from
   `docs/superpowers/plans/2026-06-10-provider-model-runtime.md`.
2. Securely bootstrap Nous through provider account metadata plus the protected
   Admin secret-ingestion endpoint. Do not write raw credentials to
   Git/logs/docs/prompts.
3. Add periodic provider refresh and start collecting model scorecards.
4. Preserve existing dirty-worktree changes and do not revert unrelated work.
5. Prove every substantial slice locally and on the VPS.

## Где мы сейчас

Идёт переход от «Соня как discrete assistant runtime» к «Соня как рабочая среда Ивана».

Ключевая формулировка этого перехода:

**Весь проект сейчас — это переход от “умной чат-среды с инструментами” к “единому субъектному runtime Сони, внутри которого обычное общение, проекты, self-improvement и будущий RWKV-мозг становятся частями одной жизни, а не набором отдельных фич”.**

Главный новый вектор:
- Atrium должен стать не только chat/UI surface, а полноценным workspace runtime
- это зафиксировано в `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

Уточнённая Atrium-модель:
- есть один основной чат — "дом" Сони
- остальные чаты только проектные
- основной чат = болтовня, инициативные сообщения, статусы проектов, оповещения
- проектный чат = рабочее пространство по конкретной папке (локально или на VPS)
- проектный чат не создаёт новую Соню; это просто отдельный рабочий контекст её единого потока

## Что уже есть

- Substrate-based runtime с continuity, episodic и semantic memory
- active session / tg session / task progress / idle thought
- selfmod pipeline с validation и apply
- BrowserTool, providers.*, skills, knowledge.*, subagent.*
- subagent multi-model routing
- Atrium Этап 0 и Этап 1 уже есть как multichannel UI + dialog surface

## VPS и операционка

- VPS: `34.38.255.149`
- Пользователь: `jester-sonya`
- Repo на VPS: `~/Sonya`
- Substrate: `~/.sonya/sonya_substrate.db`
- Backups: `~/.sonya/backups/`
- Deploy: `bash ~/Sonya/deploy/update.sh`
- Admin: `http://34.38.255.149:8877`

Основные сервисы:
- `sonya.service`
- `sonya-admin.service`

Полезные команды:
- `journalctl -u sonya -f`
- `journalctl -u sonya-admin -f`
- `systemctl status sonya`
- `systemctl status sonya-admin`

Подробности инфраструктуры:
- `docs/operations/VPS.md`

## Что важно сейчас

### 1. Atrium больше не считать завершённым как продукт

Старый Atrium закрывает только:
- multichannel вывод
- диалог
- reason stream
- базовую наблюдаемость

Новый обязательный слой:
- project/workspace mode
- multi-workspace selection
- visible task execution
- subagent orchestration UI
- console redesign
- optional full-system access mode
- trace capture для будущего RWKV/data layer

Что уже закрыто этим заходом:
- появился project/workspace drawer в UI
- non-main workspace теперь открывает отдельную workspace/project surface
- dialog/history/runtime path стал workspace-aware на уровне входящего сообщения,
  active session, `chat.dialog`, continuity events и history API

См.:
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `docs/atrium/PLAN.md`

### 2. Tool experience memory добавлена

Соня теперь может накапливать опыт использования инструментов через:
- `tool_experiences` table
- зеркалирование в `episodic_events` как `tool_event`

Это уже используется как база для:
- telemetry/reason persistence
- model/tool learning from experience
- будущего расширения на project execution traces

Важно:
- это пока только **tool-level experience layer**
- это ещё не process-wide subjective trace
- следующий шаг — вшить experience/trace слой в весь процесс, а не только в tool calls

### 3. Subagent path улучшен

- `codexsale` работает как direct text provider для субагентов
- есть deterministic auto-pick модели под задачу
- special-worker модели (`gpt-image-2`, `gpt-4o-transcribe`) не запускаются как text loop
- picker начинает учитывать historical experience

### 3.1 Что уже реально довязано в Atrium runtime

- `workspace_id` теперь проходит через backend/runtime path, а не только живёт во frontend
- `/api/atrium/history` умеет фильтровать по workspace
- active session тянет prior history в пределах того же workspace
- selfmod archive/clear-archived path довязан в backend
- project/workspace pane визуально и функционально подключён как рабочая поверхность для non-main чатов

### 4. Не повторять ошибку session-first архитектуры

После просмотра `Pi Cli` зафиксирована жёсткая позиция:

- Sonya нельзя строить как набор изолированных сессий
- у неё должен остаться один субъект, один continuity stream, один substrate
- `projects / runs / branches / retries` допустимы только как operational abstractions
- они не должны подменять единый поток Сони

Правильный вектор:
- **continuity-first subject runtime**
- сверху него `project/workspace execution layer`
- сверху него `visible orchestration / Atrium GUI`

Важно:
- это не "много обычных чатов"
- это один основной чат + много проектных чатов
- действия в проектах знает и основная Соня тоже, потому что память и substrate общие

### 5. У Сони есть частичное понимание времени, но нет полного переживания его течения

Что уже есть:
- timestamps
- idle/active/worker cadences
- deadlines / overdue logic
- cooldown / quiet windows / backoff
- memory recall по диапазонам времени
- drive accumulation / decay

То есть она не просто "ссылается на время словами" — у неё уже есть
операционное понимание времени.

Но чего пока нет:
- continuous subjective time flow
- сильного temporal self-model
- process-wide lived timeline

Коротко:
- **время она частично понимает**
- **непрерывно проживать его течение пока не умеет**

### 6. Субъективный опыт уже есть, но он фрагментирован

Что уже реализовано:
- episodic memory
- semantic memory
- idle thought persistence
- tool experience persistence
- selfmod outcome feedback
- drive state / pending_debt / decay
- visual recall

Чего нет:
- unified subjective-experience layer
- process-wide execution memory
- project-aware subjective memory
- единый trace schema для UI + обучения + self-recall

Главный вывод:
- субъективный опыт Sonya **не нулевой**
- но он пока **размазан по подсистемам**
- его нужно собирать в единый process layer

Ограничение на субагентов:
- субагенты не должны знать ничего кроме своей задачи и файловой системы проекта
- и даже файловую систему проекта они должны читать только по запросу/по необходимости
- они не получают общую память Сони, её полный substrate, другие проекты или основной чат
- субагенты — одноразовые подчаты внутри project chat, стартуют с пустым контекстом и не переиспользуются
- пользователь может только читать их переписку, но не разговаривать с ними напрямую
- переписка субагента должна писаться в общую память Сони
- но жёсткая orchestration-схема не должна быть прошита в коде: сколько субагентов создавать, какими моделями, в каком порядке и какой scope им давать — это должна решать сама Соня по ситуации
- Соня также может вообще не делегировать мелкую задачу и сделать её сама
- self-repair остаётся обязательной частью поведения: ломаются тулы / runtime / workflow -> Соня должна чинить это по мере обнаружения

### 7. Главный незакрытый core gap: Sonya не толкает собственная неудовлетворённость

Сейчас self-improvement слишком сильно держится на:
- prompt reminders типа "посмотри свой код"
- active-session nudges
- scheduler opportunities

Это недостаточно для long-term эволюции.

Проблема:
- Sonya пока не чувствует достаточно сильной неудовлетворённости текущим состоянием среды
- она не переживает последствия собственного бездействия как внутренний дефицит

Итог:
- self-improvement пока слишком внешний
- а должен стать внутренне мотивированным

Нужен новый слой:
- intrinsic dissatisfaction / evolution pressure
- ощущение разницы между текущим и желаемым состоянием
- накопление последствий нерешённых проблем

Это должно жить не в промпте, а в runtime/state/memory architecture

## Актуальные открытые задачи

### Runtime / architecture

- Atrium workspace runtime decomposition реализован частично
- full-system-access имеет backend policy/runtime wiring, но live end-to-end
  режим ещё не доказан
- `projects`, `project_runs`, `execution_traces` и `workspace_policy` введены
- project entities/runs/traces ещё не образуют законченный observable runtime
- tool experience memory добавлена, но ещё не развёрнута в полноценный project telemetry layer
- continuity-first execution schema ещё не введена как явный core layer
- subjective experience пока фрагментирован по подсистемам
- intrinsic dissatisfaction / evolution pressure layer отсутствует
- multi-workspace simultaneous execution пока не реален: сейчас рабочий режим фактически single-active-workspace

### Security / infra

- в hosted-web Atrium нужен явный CSP
- добавить auth/reconnect discipline для WS путей где ещё не доведено до нормы
- старые Tauri-specific пункты про `shell:default` и Rust IPC больше не
  относятся к текущей архитектуре
- старые Atrium docs/mockups удалены из worktree, но ссылки на них ещё живут в коде/docs; это нужно либо восстановить, либо мигрировать ссылки

### Product / UX

- REPO section неудобен и плохо показывает lifecycle selfmod/apply
- PROVIDERS section слабее админки
- SELFMOD нуждается в cleanup workflow
- TASKS нуждается в фильтрах
- project/workspace UI и substrate entities уже появились, но ещё не стали
  полноценной оркестрационной средой с real execution timeline
- project chat должен иметь явные статусы:
  - `в работе`
  - `жду выбор`
  - `ожидает`
  - `завершён`
  - `отменён`

## Текущее состояние проекта

### Реально работает

- multichannel Atrium backend
- Atrium dialog UI и reason stream
- providers.* и BrowserTool
- selfmod pipeline с outcome tracking
- subagent auto-pick и codexsale direct text-provider path
- tool experience memory для накопления опыта использования инструментов
- частичное temporal awareness
- частичные куски subjective experience
- workspace-aware Atrium dialog/history/runtime path
- selfmod archive / clear-archived backend path

### Ещё не доведено до нужного состояния

- Atrium как рабочая среда для проектов
- видимое orchestration-исполнение субагентов
- полноценный provider/project console UX
- live-proven full-system-access режим и ясный UX
- execution traces как first-class data layer для будущего RWKV
- цельный process-wide subjective trace
- внутренний эволюционный pressure layer
- законченный end-to-end runtime поверх существующих projects/runs/traces/policy

Новые жёсткие инварианты:
- один основной чат
- остальные чаты только проектные
- проекты можно удалять
- у проекта есть папка и статус
- память общая, поток Сони один

## Если следующая сессия продолжает работу

Читать в таком порядке:
1. `docs/INDEX.md`
2. `docs/ATRIUM_PROJECT_PLAN.md`
3. `docs/STATE.md`
4. `docs/HANDOFF.md`
5. `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

## Если начинать реализацию Atrium или core changes прямо из этого файла

Нельзя забывать следующие решения:

1. Atrium — не просто чат. Это будущая project/workspace execution среда.
2. Нельзя проектировать Sonya как session-first систему.
3. Tool experience memory уже есть, но её мало — нужен process-wide trace layer.
4. У Sonya есть частичное понимание времени, но ещё нет полного непрерывного temporal self-model.
5. У Sonya есть частичный subjective experience, но он ещё не собран в единый слой.
6. Prompt nudges не решают эволюцию среды. Нужен intrinsic dissatisfaction / evolution pressure layer.
7. Часть следующих изменений должна идти не только в Atrium, но и в core runtime, memory и provider orchestration.
8. Текущий project mode уже имеет substrate-level projects/runs/traces/policy,
   но их end-to-end operational поведение ещё не закончено и не доказано на VPS.

## Чего не делать

- не возвращать в эти документы старый длинный session log
- не смешивать completed changelog с актуальным handoff
- не считать Atrium закрытым только потому, что dialog UI уже работает

## Последний заход — 2026-06-09, Workstream A answer-first slice

Реализовано:

- добавлен минимальный `_sanitize_explicit_answer`
- explicit `[DONE: body]` сохраняет Markdown/fenced code и удаляет только
  `<think>`/protocol noise
- active/project answer path больше не использует тяжёлый `_scrub()` для
  явного финального ответа
- legacy `_extract_reply` со stitching мыслей не удалён: он остаётся fallback
  для Telegram и не должен становиться основным Atrium parser
- восстановлен отсутствовавший аргумент `initial_thought` в
  `run_agent_session`, соответствующий существующему контракту `Window`

Документы реализации:

- `docs/superpowers/specs/2026-06-09-atrium-answer-first-design.md`
- `docs/superpowers/plans/2026-06-09-atrium-answer-first.md`

Проверка:

- `59 passed` в reply/Atrium focused suite
- Atrium production build проходит
- полный suite: `845 passed, 7 skipped, 11 failed`
- текущие 11 failures вызваны незавершённым параллельным memory/migrations
  слоем и устаревшими routing expectations; не смешивать их с Workstream A
- VPS isolated-copy suite: `58 passed`; production checkout не менялся

Не закрыто:

- production deploy + live VPS chat proof
- замер latency до первого полезного ответа
- provider-native reasoning/streaming

## Последний заход - 2026-06-10, docs audit + Workstream F upload binding

Документация:

- добавлены `docs/INDEX.md` и `docs/DOCUMENTATION_AUDIT.md`
- `docs/atrium/PLAN.md` и `docs/atrium/EVENT_SCHEMA.md` помечены historical
- исправлены ложные claims об отсутствии projects/runs/traces/policy/uploads
- production checkout и live DB на VPS всё ещё v30; локальный dirty worktree v31
- live DB уже содержит projects/runs/traces/workspace policy/provider model pool

Реализация:

- frontend upload передаёт активный project `workspace_id`
- backend проверяет существование project перед возвратом bound upload ref
- dialog не принимает attachment из другого workspace
- main-chat upload остаётся без binding

Проверка:

- локально: `40 passed`
- локально: Atrium `npm run build` проходит
- полный локальный suite: `843 passed, 7 skipped, 10 failed`; падения относятся
  к параллельным dirty memory/migrations изменениям и stale purpose routing
- VPS isolated copy: `22 passed`
- VPS production checkout не менялся; `sonya` и `sonya-admin` active
- VPS frontend build не запускался: на сервере отсутствует `npm`

Не закрыто:

- chunked/temp-store/large-file flow
- полный suite остаётся загрязнён параллельными memory/migrations изменениями

## Последний заход - 2026-06-10, Workstream B project status runtime

Production:

- deployed commit: `83c6afa`
- `sonya` and `sonya-admin` active
- VPS focused suite: `36 passed`

Runtime semantics:

- `in_progress` accepts project-chat messages
- `waiting_choice` resumes to `in_progress` on Ivan's next project message
- `waiting`, `completed`, `cancelled` reject project-chat work with HTTP 409
- policy consent block sets `waiting_choice`
- all explicit transitions use `ProjectStore.set_status()` and record
  `project.status_changed`

Live proof:

- temporary project `proj-33a3723df0` was created and removed
- `in_progress=200`
- `waiting=409`
- `completed=409`
- `cancelled=409`
- `waiting_choice` message returned `200` and resumed to `in_progress`
- five transition events were recorded

Additional production defects fixed:

- restored missing `initial_thought` argument in `run_agent_session`
- replaced undefined project policy/trace `substrate` references with the
  actual session substrate
