# ATRIUM MASTER PLAN

**Status:** Active
**Type:** Unified implementation plan
**Last updated:** 2026-06-11

## Current priority override - 2026-06-11

The provider-pool foundation, approved account imports, observable multi-worker
project runtime, and honest cancellation are deployed. The immediate execution
order is now:

1. extend the project executor to model-driven decomposition,
   dependency-aware scheduling, and result synthesis;
2. feed measured outcomes into model scorecards and provider/account cooldowns;
3. add honest pause, approval, decision, and resume controls;
4. prove project outcomes enter the one shared Sonya memory and complete the
   non-destructive production migration proof;
5. live Atrium project-chat end-to-end scenario is now proven; continue only
   follow-up gaps found outside this hosted-stack proof.

The web-proxy model bridge remains parked until this hosted-stack path is
complete. The executable plan is
`docs/superpowers/plans/2026-06-11-atrium-hosted-stack-completion.md`.

## Atrium UI invariant - 2026-06-11

Atrium must render one continuous Sonya surface:

- the left visual/presence pane belongs to Sonya and must keep her avatar/model
  and idle/speaking animations visible;
- the center pane is always the chat pane;
- `main` is the only non-project chat;
- every other selectable chat is a real substrate-backed project chat;
- selecting a project changes the active chat context, not the identity of
  Sonya and not the center chat component;
- project runtime, folder/path, policy, progress, traces, and subagent
  subthreads live in the right context pane for the active project;
- subagent traces/subthreads are read-only internal work logs. Ivan can inspect
  them, but cannot talk to a subagent directly;
- the project/chat selector is a drawer or overlay, not a permanent left column
  that displaces Sonya's visual pane.

Project folder scope is the project starting context, not a hard prison for the
main Sonya. If Atrium's full-computer-access setting is enabled and policy
allows it, Ivan can ask in the main chat to create a project from any reachable
local, mounted, or SSH path. Disposable subagents still receive an explicit
bounded filesystem scope chosen by Sonya for the task.

Project understanding notes should be first-class project context artifacts:
purpose, current state, external connections, code style, examples, rules,
known hazards, and decision history. Default storage should be substrate/Atrium
project context so completed projects and read-only workspaces are not polluted
by generated files. Exporting `.sonya/` or Kilo-style docs into the project
folder is an explicit option only when the folder is writable and Ivan/Sonya
decide the project should carry those notes with it.
**Scope:** Единый проработанный план по доведению Atrium до целевого состояния: рабочие проекты, корректные ответы Сони, провайдеры как model pools, субагенты как внутренние инструменты Сони, без поломки остального runtime.

---

## 1. Главная цель

Сделать **Atrium** основной средой взаимодействия с Соней, где:

- есть **один основной чат** — "дом" Сони
- есть **project chats** — рабочие контексты по конкретным папкам
- Sonya остаётся **одним субъектом** с одним substrate и одной общей памятью
- проекты реально можно вести end-to-end
- субагенты работают как **внутренний инструмент Сони**, а не как отдельные собеседники
- ответы Сони в Atrium быстрые, чистые и не мешают работе
- система провайдеров умеет работать через **пулы моделей**, а не через жёсткую привязку
- остальной функционал Sonya не ломается:
  - self-improvement
  - reflections
  - background work
  - continuity
  - общая память

---

## 2. Что должно получиться в итоге

### 2.1 Atrium
- один основной чат
- список проектов
- проектный чат по каждой рабочей папке
- project status
- traces / progress / subagent activity
- file upload
- нормальная навигация между main chat и project chats

### 2.2 Проекты
- проект = чат-контекст + папка + статус + traces + progress
- проект можно создать
- проект можно удалить
- проект можно ставить в состояния:
  - `in_progress`
  - `waiting_choice`
  - `waiting`
  - `completed`
  - `cancelled`
- статусы реально влияют на поведение, не только на label

### 2.3 Субагенты
- пользователь с ними не общается
- они видимы как traces / internal subthreads
- они одноразовые
- стартуют с пустым контекстом
- не получают общую память напрямую
- Sonya сама решает:
  - создавать ли их
  - сколько
  - каких ролей
  - какими моделями
  - с каким filesystem scope

### 2.4 Ответы Сони
- raw answer сразу в видимый чат
- reasoning/think скрыт по умолчанию
- нет долгой задержки до полезного ответа
- парсинг не ломает диалог

### 2.5 Провайдеры
- provider = model pool
- discovery / refresh моделей
- routing по role/cost/context/latency/history
- no hardcoded one-provider-one-model assumption

---

## 3. Текущее состояние

### Что уже есть
- local migration target: substrate v31
- `projects`, `project_runs`, `execution_traces`, `workspace_policy`
- `model_scorecards`, `evaluation_runs`, `evaluation_results`, `champion_models`
- project CRUD/API
- workspace-aware groundwork
- provider model pool foundation (`provider_models`)
- role/cost-aware model picker groundwork
- тесты проходят
- frontend собирается

### Что по факту ещё не finished
- проектный UX ещё не end-to-end
- статусы проектов не доказаны полностью на живом сценарии
- ответы Сони в Atrium работают плохо
- базовый Atrium upload path реализован; project-scoped storage, large-file flow
  и live end-to-end proof ещё не закрыты
- provider system ещё не доведён до полного pool/discovery runtime
- web-proxy model bridge не реализован
- evaluation harness есть только частично, не доведён до реального использования

---

## 4. Неподвижные инварианты

### 4.1 Один субъект
- одна Sonya
- один substrate
- одна общая память
- один continuity stream

### 4.2 Main chat vs project chats
- основной чат один
- остальные чаты только проектные
- проектные чаты не создают новые версии Сони

### 4.3 Память
- project-related content обязан попадать в общую память Сони
- project retrieval может иметь priority, но память одна
- subagent raw chatter не должен напрямую загрязнять long-term behavior memory

### 4.4 Субагенты
- субагенты != Sonya
- субагенты = внутренние инструменты
- пользователь только читает traces, не разговаривает с ними напрямую

### 4.5 Admin vs Atrium
- Atrium = среда общения и работы с Sonya
- Admin = техническая/operator поверхность
- Atrium не должен превращаться в admin clone

---

## 5. TODO — конкретные workstreams

## Workstream A — Atrium replies

### Цель
Сделать ответы Сони в Atrium быстрыми и пригодными для реальной работы.

### Проблемы сейчас
- слишком долгое ожидание
- brittle parsing
- reasoning смешан с answer
- лишние промежуточные слои ломают UX

### TODO
- [ ] отделить answer layer от reasoning layer
- [ ] raw answer показывать сразу
- [ ] reasoning/think уводить в скрытый блок
- [ ] убрать лишние задержки до первого полезного ответа
- [ ] упростить parsing strategy
- [ ] сделать fallback parsing для неаккуратного модельного вывода
- [ ] проверить это на VPS в живом чате

### Done criteria
- [ ] Sonya отвечает быстро
- [ ] reasoning не мешает
- [ ] parser не ломает нормальные ответы
- [ ] UX выглядит естественно

### Progress 2026-06-09 — answer-first vertical slice

- [x] explicit `chat.dialog` remains the immediate visible answer path
- [x] explicit `[DONE: body]` no longer runs through the heavy heuristic
  scrubber
- [x] explicit answers preserve Markdown and fenced code
- [x] `<think>` and protocol-only markers are removed from explicit answers
- [x] legacy thought stitching remains only as Telegram compatibility fallback
- [x] restored the missing `initial_thought` unified Window contract
- [x] VPS isolated-copy reply/Atrium suite passes on Linux
- [ ] provider-native reasoning fields / streaming remain future work
- [ ] production deploy and live conversational quality/latency still require proof

---

## Workstream B — Project chats

### Цель
Сделать проекты реальными рабочими пространствами.

### TODO
- [ ] project chat имеет отдельную историю
- [ ] project chat привязан к папке
- [ ] статусы работают end-to-end
- [ ] progress виден
- [ ] traces видны
- [ ] blocking/waiting points видны
- [ ] project можно удалить
- [ ] project можно вести через чат до результата

### Project status TODO
- [x] `in_progress`
- [x] `waiting_choice`
- [x] `waiting`
- [x] `completed`
- [x] `cancelled`
- [x] статусы влияют на runtime поведение

### Done criteria
- [x] тестовый проект можно создать
- [x] по нему можно вести диалог и работу
- [x] статус меняется и влияет на flow

---

### Progress 2026-06-10 - project status runtime

- [x] status transitions are validated centrally
- [x] transitions record `project.status_changed` in shared continuity
- [x] `in_progress` accepts project-chat work
- [x] `waiting_choice` resumes on Ivan's next project message
- [x] `waiting`, `completed`, `cancelled` make project chat read-only
- [x] policy consent blocks set `waiting_choice`
- [x] API and `projects.update` use the same transition contract
- [x] production live five-status proof passed

### Progress 2026-06-11 - live project-chat proof

- [x] hosted API created proof project `proj-a83c1c3657`
- [x] project chat message with `workspace_id` appeared in project history
  and not in main history
- [x] main chat proof message appeared in main history and not in project
  history
- [x] project runtime exposed dependency steps, progress, traces, pause/resume,
  approval deny, completion, and synthesized result
- [x] shared memory recall returned a project-scoped semantic fact for the live
  project outcome
- [x] live proof exposed and fixed history initial pagination
- [x] live proof exposed and fixed project outcome compilation when newer
  subagent runs existed

---

## Workstream C — Subagents as internal tools

### Цель
Сделать субагентов корректной внутренней системой исполнения.

### TODO
- [x] пользователь не пишет субагентам
- [x] пользователь видит только traces / subthreads
- [x] субагенты одноразовые
- [ ] пустой контекст на старт
- [x] Sonya сама решает, создавать ли субагентов
- [ ] Sonya сама решает, сколько субагентов нужно
- [x] Sonya сама решает, какой scope и модель дать субагенту
- [ ] Sonya может сама делать мелкие правки без делегирования
- [x] traces субагента попадают в общую память Sonya как summary/lessons, а не как raw long-term behavior memory

### Done criteria
- [x] project work реально оркестрируется через субагентов
- [x] пользователь не видит их как отдельных собеседников
- [x] Sonya остаётся orchestrator

### Progress 2026-06-11 - project executor substrate slice

- [x] `projects.execute` creates a `project_executor` run
- [x] execution spawns an internal disposable subagent with project
  `workspace_id` scope
- [x] task/action/outcome traces are written to `execution_traces`
- [x] `projects.harvest` completes or fails the project run from subagent
  outcome
- [x] `ToolExperience` records project executor outcomes for future routing
  and learning
- [x] VPS focused project/subagent/provider suite passes (`29 passed`)
- [x] explicit independent task lists can spawn multiple project-scoped
  disposable subagents
- [x] failed workers retry independently within a bounded retry budget
- [x] aggregate runs persist worker state and progress checkpoints
- [x] Atrium project surface reads `project_executor` runs/traces and shows
  progress, retries, internal worker subthreads, and outcomes
- [x] project runs can be honestly cancelled through persisted cross-process
  lifecycle state plus immediate core-process task cancellation
- [x] model-driven autonomous task decomposition with strict JSON graph and
  safe single-task fallback
- [x] dependency-aware scheduling starts only ready workers and propagates
  terminal dependency failure
- [x] successful planned runs synthesize a final result while raw worker
  outcomes remain persisted
- [x] deployed VPS regression proof: `29 passed`, compileall clean, services
  active, error journal empty
- [x] persisted pause/resume stops orchestration until resume
- [x] project approval requests and approve/deny decisions are persisted on the
  run and surfaced through Atrium runtime controls
- [x] VPS proof for project/Atrium runtime controls passed (`14 passed`);
  production deployed and verified on VPS, compileall clean, services active, error
  journal empty

---

## Workstream D — Provider system rewrite

### Architecture decision 2026-06-10

The target provider runtime is now specified in:

- `docs/operations/PROVIDER_SYSTEM_DESIGN.md`
- `docs/operations/PROVIDER_MODEL_CATALOG.md`
- `docs/operations/SUBAGENT_MODELS.md`
- `docs/superpowers/plans/2026-06-10-provider-model-runtime.md`

Do not bootstrap all newly supplied credentials into the current schema. First
separate provider definitions, accounts/secrets, account-specific model
offerings, quota windows, and observations. Then bootstrap Nous and one
OpenRouter account as the minimum viable proof.

Fireworks is unavailable and must be removed from defaults, hard-coded profiles,
and fallback assumptions. Provider management is a typed internal capability
used by Sonya from natural-language requests; it is not raw DB access and does
not turn Atrium into an admin surface.

### Progress 2026-06-10 — provider registry foundation

- [x] substrate v32 adds first-class `providers`
- [x] substrate v32 adds `provider_accounts` without fixed-model ownership
- [x] account-specific `provider_account_offerings` exists
- [x] structured `provider_quota_windows` and `provider_observations` exist
- [x] legacy `provider_keys` migrate/mirror into provider accounts
- [x] typed KeyStore CRUD/read foundation exists
- [x] model availability requires an active account offering
- [x] local focused/migration suites pass
- [x] isolated VPS suite and real-substrate-copy migration pass

### Progress 2026-06-10 — provider adapter contract

- [x] `ProviderAdapter` contract exists for discovery, health, quota, and generic inference
- [x] `OpenAICompatibleAdapter` supports `/models`, `/chat/completions`, and optional quota path
- [x] `GoogleNativeAdapter` supports Gemini native `models` and `generateContent`
- [x] adapter tests use mocked HTTP only; no real credentials or network calls
- [x] existing `ProviderBackend` / OpenRouter runtime path remains compatible
- [x] local focused provider suite passes (`83 passed`)
- [x] isolated VPS focused provider suite passes (`83 passed`)
- [x] isolated VPS real-substrate backup migration/import smoke passes
- [x] discovery/refresh service replaces hardcoded model listing in `providers_tool.py`
- [x] secret-safe credential boundary
- [x] adapter/discovery refresh
- [x] evidence-driven routing without hard-coded profiles/fallbacks

### Progress 2026-06-10 — provider refresh service

- [x] `ProviderRefreshService` records health, model discovery observations, and quota windows
- [x] core runtime uses a generic TTL-based `ProviderRefreshCoordinator`
- [x] only successful discovery marks a pool fresh; failed discovery remains retryable
- [x] pools without active first-class accounts are skipped until secure import
- [x] Fireworks-only runtime balance loop removed
- [x] successful discovery upserts provider model pools and offerings only for the probed account
- [x] health/discovery observations and quota windows are account-scoped
- [x] discovery failure preserves last-good cached models
- [x] `providers.list_models` reads substrate provider model pools and offering availability
- [x] Fireworks live catalog and Kiro/OpenRouter/CodexSale hardcoded list branches removed from listing
- [x] local focused provider suite passes (`87 passed`)
- [x] isolated VPS focused provider suite passes (`87 passed`)
- [x] isolated VPS real-substrate backup migration/import smoke passes with refresh import

### Progress 2026-06-10 — evidence-driven subagent routing

- [x] `pick_subagent_model()` scores active substrate offerings instead of hardcoded `_PROFILES`
- [x] unavailable models without active account offerings are filtered out
- [x] role preferences, latency/cost/context traits, and `ToolExperience` history are soft ranking signals
- [x] `_PURPOSE_MODEL_HINT` no longer forces Fireworks or any fixed model
- [x] `LLMProvider` provider fallback chain is derived from available offerings and eligible keys
- [x] `SubagentTool` checks `text_loop_ok` from substrate before spawning text-loop workers
- [x] v33 legacy `provider_models` tables are repaired if missing newer columns
- [x] local focused provider/routing suite passes (`108 passed`)
- [x] isolated VPS focused provider/routing suite passes (`108 passed`)
- [x] isolated VPS real-substrate backup migration/import smoke passes

### Progress 2026-06-10 — provider management surfaces

- [x] `ProvidersTool` can create/update/delete providers
- [x] `ProvidersTool` can create/update/delete provider accounts without exposing raw secrets
- [x] account offerings can be enabled/disabled explicitly
- [x] provider quota windows and observations are inspectable
- [x] `/api/providers` exposes provider registry, accounts, model pool, available models, quotas, observations, and legacy keys
- [x] Admin POST endpoints exist for provider registry, accounts, and account offerings
- [x] Atrium only receives provider status/event projection, not detailed provider CRUD controls
- [x] local focused provider/routing/management suite passes (`113 passed`)
- [x] local Atrium frontend build passes
- [x] isolated VPS focused provider/routing/management suite passes (`113 passed`)
- [x] isolated VPS real-substrate backup management smoke passes

### Progress 2026-06-10 — provider secret boundary

- [x] substrate v33 adds encrypted `provider_secrets`
- [x] `provider_accounts` exposes only `secret_ref` and `secret_masked`
- [x] protected Admin secret-ingestion path encrypts/rotates opaque credential bodies
- [x] ordinary account JSON/tool paths reject raw credentials
- [x] legacy key-add JSON/tool paths reject raw credentials
- [x] explicit resolver returns `ProviderSecret` only when adapter code asks for it
- [x] legacy `provider_keys` remain readable for compatibility
- [x] legacy accounts get masked metadata during migration
- [x] local focused provider/migration/secret suite passes
- [x] isolated VPS suite and real-substrate-copy migration pass
- [x] local provider/routing/management/secret-ingestion suite passes (`126 passed`)
- [x] isolated VPS protected secret-ingestion proof (`122 passed` plus live-substrate-copy rotation smoke)
- [ ] real provider bootstrap and live discovery/health/routed-subagent proof
- [x] production OpenRouter account migrated to encrypted secret storage
- [x] production OpenRouter discovery/health/live inference proof
- [x] production substrate v33 deploy with rollback backup
- [x] safe ignored-file account importer added
- [x] production Kimchi pool imported: 15 encrypted accounts, 8 discovered models
- [x] production OpenRouter availability repaired: legacy account status synced,
  old non-free offerings disabled, and Admin shows free/requested models by
  default
- [x] OpenRouter free candidates are live-probed per account before enablement
- [x] protected Google bootstrap
- [x] protected Nous bootstrap
- [x] protected CodexSale bootstrap
- [x] provider-scoped model identity / aliases so providers can expose the same
  raw model id without overwriting each other

### Цель
Переделать provider layer в `provider -> model pool`.

### TODO
- [ ] убрать assumption `provider -> one model`
- [ ] хранить model pools per provider
- [x] automatic discovery через `/models` endpoint где возможно
- [x] refresh / cache model lists
- [ ] health/availability per model
- [ ] routing по:
  - [x] role
  - [x] cost
  - [x] latency
  - [x] context length
  - [x] historical success
  - [x] provider availability
- [x] UI/provider management показывают model pools, а не single model

### Must-cover providers
- [x] OpenRouter free-model availability and discovery
- [x] Google AI Studio
- [x] Nous Research
- [ ] agentrouter.org
- [x] codexsale
- [ ] future web-proxy model bridge

### Done criteria
- [x] Sonya выбирает модели из pool, а не из fixed binding
- [ ] discovery работает для поддерживаемых providers
- [x] operational routing не ломается

---

## Workstream E — Model evaluation

### Цель
Дать Sonya устойчивое знание о моделях, а не гадание.

### TODO
- [ ] `models.evaluate` реально работает
- [ ] domain suites:
  - [ ] programming
  - [ ] math
  - [ ] science
  - [ ] facts
  - [ ] censorship
- [ ] quick mode
- [ ] full mode
- [ ] scorecards обновляются корректно
- [ ] champion/challenger logic usable
- [ ] first live benchmark run on VPS

### Done criteria
- [ ] есть хотя бы один реальный champion per key task-class
- [ ] scorecards наполнены реальными результатами

### Progress 2026-06-11 - measured runtime outcomes

- [x] project/subagent runtime outcomes feed `model_scorecards`
- [x] model-specific provider-account cooldowns reactivate after bounded
  cooldown expiry
- [x] VPS provider/scorecard/cooldown suite passed (`21 passed`)
- [ ] Sonya может опираться на operational model knowledge

---

## Workstream F — File transfer

### Цель
Сделать нормальную отправку файлов через Atrium.

### TODO
- [x] file upload в main chat
- [x] file upload в project chat
- [x] привязка к project context
- [x] small file path
- [ ] large file path
- [ ] chunked upload / temp store / server persistence
- [ ] Sonya видит, что файл пришёл именно в нужный project context

### Done criteria
- [x] можно отправить маленький файл
- [ ] можно отправить большой файл
- [x] это работает и в main chat, и в project chat

### Progress 2026-06-10 - project-aware upload binding

- [x] existing main-chat upload remains unbound and compatible
- [x] project upload sends the active `workspace_id` with multipart data
- [x] backend verifies that a bound workspace/project exists
- [x] upload references return their `workspace_id`
- [x] dialog rejects attachments bound to another project or main chat
- [x] local focused suite and Atrium production build pass
- [x] VPS isolated-copy backend suite passes
- [x] production deploy and live main/project upload proof
- [ ] large-file/chunked/temp-store flow

---

## Workstream G — Self-repair continuity

### Цель
Не потерять self-improvement и self-repair из-за Atrium/project слоя.

### TODO
- [ ] tool failures feed repair logic
- [ ] project failures feed improvement pressure
- [ ] Sonya не теряет способность чинить свои инструменты
- [ ] self-improvement остаётся частью обычной жизни runtime

### Done criteria
- [ ] project layer не ломает self-improvement
- [ ] Sonya может чинить инструменты и workflows

---

## Workstream H — Web proxy bridges / external premium paths

See `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`. The old freemodel-only bridge
note was removed because the target is now a unified web-proxy tier over
FreeQwenApi, FreeGLMKimiAPI, FreeDeepseekAPI, and later browser-backed model
accounts.

### Web proxy bridge
- [ ] FreeQwenApi localhost-only VPS service
- [ ] Sonya-owned unified gateway
- [ ] GLM/Kimi bridge research and fork/vendor decision
- [ ] DeepSeek bridge research and fork/vendor decision
- [ ] synthetic progress / streaming normalization
- [ ] integration as `web_proxy` provider tier for cheap subagent work

### freemodel.dev
- [ ] research
- [ ] bridge prototype
- [ ] integration as provider pool member
- [ ] budget guard

### agentrouter.org
- [ ] integrate provider
- [ ] verify `glm-5.1`
- [ ] optionally test Claude variants if usable

### FreeQwenApi / browser abuse path
- [ ] investigate from VPS
- [ ] determine if operationally viable

### Done criteria
- [ ] alternative fallback paths exist beyond OpenRouter/Google/Nous/codexsale

---

## 6. End-to-end proofs (обязательно)

Пока этого нет, всё остальное scaffold.

### Proof 1 — Test project
- [ ] создать `website chat-bot`
- [ ] привязать к папке
- [ ] вести его через project chat
- [ ] видеть traces/progress

### Proof 2 — Subagent-only orchestration
- [ ] Sonya ведёт тяжёлую работу через субагентов
- [ ] видно какие модели выбраны
- [ ] видно, что дорогие модели не тратятся тупо на всё подряд

### Proof 3 — Shared memory
- [ ] после project work перейти в основной чат
- [ ] Sonya знает что делала в проекте
- [ ] history не смешивается

### Proof 4 — Permission/status
- [ ] `waiting_choice` → разрешение → продолжение
- [x] `waiting`
- [x] `completed`
- [x] `cancelled`
- [x] deletion

### Proof 5 — Full-system-access
- [ ] включить full-system-access
- [ ] проверить backend policy effect
- [ ] убедиться что subagents не получают его автоматически

### Proof 6 — File transfer
- [x] small file
- [ ] large file
- [x] main chat
- [x] project chat

---

## 7. Что должно получиться в конце

Практический конечный результат на текущем стеке:

- Atrium = основной интерфейс Sonya
- один основной чат + project chats
- проекты можно реально вести до конца
- субагенты работают как внутренние инструменты Sonya
- ответы Sonya в Atrium быстрые и чистые
- provider system гибкая и model-pool-based
- evaluation system даёт Sonya уверенность в model choices
- self-improvement, reflections, continuity и остальной runtime не ломаются

Коротко:

**Sonya using subagents can execute projects of high complexity, while the rest of her functionality — memory, self-improvement, reflections, continuity, and main-chat life — remains intact.**
