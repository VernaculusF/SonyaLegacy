# STATE.md — текущее состояние Сони

**Status:** Active
**Type:** Current project state
**Last updated:** 2026-06-11

Latest production deployment: verify on the VPS with `git rev-parse --short HEAD`.

## Current execution state - 2026-06-11

- production and repository substrate are at schema v33;
- provider registry, many accounts per provider, many model offerings per
  account, quota windows, observations, and encrypted secrets are implemented;
- runtime provider/model/account selection is substrate-owned and no longer
  bound through model/provider environment variables;
- OpenRouter production discovery and routed inference are live;
- the existing Admin Providers backend supports registry, account, offering,
  defaults, and protected-secret operations;
- generic periodic provider discovery/health/quota refresh is deployed,
  reads provider-level TTL from substrate metadata, and scopes freshness,
  observations, offerings, and quotas to the concrete account being probed;
- pools without active first-class accounts are skipped quietly until secure
  account import, rather than producing false runtime failures;
- Kimchi is imported as the first bulk multi-account provider pool: 15
  encrypted active accounts and 8 discovered/available models;
- OpenRouter availability is probe-backed: 10 active accounts, account-specific
  enabled offerings, 19 distinct available free models after live one-token
  probes, stale non-text/non-free offerings disabled, and legacy runtime key
  acquire is constrained by model offering;
- provider model identity is provider-scoped: `provider_models` is keyed by
  `(provider, model_id)`, while raw `model_id` remains the upstream API value;
- Google, Nous, and CodexSale are imported as protected provider accounts and
  live refresh succeeds: Google 2 accounts / 50 available models, Nous 2
  accounts / 265 available models after provider-scoped repair, CodexSale
  1 account / 3 available models;
- NVIDIA NIM is live with 3 encrypted active accounts, 121 discovered models,
  and 103 ordinary text-loop models available; 18 embedding/guard/safety/
  retrieval models remain catalogued but disabled for ordinary subagents;
- `nvidia/nemotron-3-ultra-550b-a55b` passed account-specific inference probes
  on all 3 NVIDIA accounts;
- project execution accepts one task or an explicit list of independent tasks,
  spawns project-scoped disposable subagents, retries failed workers within a
  bounded budget, persists progress checkpoints, and aggregates outcomes;
- Atrium project runtime reads project runs/traces from the project API and
  shows aggregate progress, internal worker subthreads, retries, and outcomes
  without presenting subagents as separate chat actors;
- project executor cancellation is lifecycle-backed: cancellation is persisted
  for cross-process visibility and immediately cancels a running worker task
  when core owns its asyncio handle;
- optional project auto-planning is deployed: a model-generated dependency
  graph is persisted with raw planner output, only ready internal workers are
  scheduled, dependency failures propagate, and successful graphs synthesize a
  final result without discarding worker outcomes;
- runtime worker outcomes feed measured model scorecards, and bounded
  model-specific account cooldowns reactivate after expiry;
- project executor pause/resume is persisted and exposed in Atrium; pause stops
  harvest, retries, dependency scheduling, and synthesis until resume;
- project approval requests and approve/deny decisions are persisted and
  exposed in Atrium runtime controls;
- completed project outcomes compile into shared semantic memory with
  `scope="project"` and concrete `project_id`;
- production semantic dedup was explicitly approved and applied on 2026-06-11:
  `3,864 -> 1,913` semantic facts, `0` duplicate groups remaining,
  `PRAGMA quick_check=ok`, and top-50 semantic retrieval returned unique
  signatures;
- full-system-access policy is now live-backed: project policy checks consult
  workspace policy, API/tool responses expose verdict source and
  `full_system_access`, a live VPS temp-project proof showed
  `consent -> allowed`, and subagent filesystem scope stayed project-bound;
- Atrium project workspace exposes full-system-access state, `shell_run`
  verdict, verdict source, and a project-scoped toggle backed by the same API;
- hosted Admin/Atrium security baseline is live: unauthenticated `/api/*`
  requests return JSON `401` instead of `/login` redirects, and HTML/API
  responses include CSP, `nosniff`, no-referrer, frame denial, and baseline
  permissions-policy headers;
- Atrium WebSocket auth uses 45-second one-time tickets; raw permanent-token
  query auth is rejected, ticket reuse is rejected, and reconnect generations
  prevent stale sockets from reconnecting;
- `sonya-admin` hosts the built Atrium SPA at `/atrium/`; Node/npm is installed
  on the VPS and `deploy/update.sh` rebuilds Atrium before service restart;
- Atrium uploads are streamed to hidden staged files and atomically published;
  the configurable default limit is 2 GB, and a live 65 MB VPS proof left no
  partial files;
- concurrent project execution keeps project/subagent workspace IDs isolated
  and blocks unavailable local or mounted-remote directories before spawning;
- direct SSH project transport is deployed for
  `ssh://user@host/absolute/path`: scoped subagents receive remote
  read/list/search and code execution through existing SSH config/keys;
- active Atrium UI now has exactly one main chat and substrate-backed project
  chats only; first project creation accepts local or SSH workspace paths;
- the production migration manifest now reports `legacy_sources=[]`; no
  Telegram export or remaining legacy knowledge source exists to import;
- real `internal.tool_error` exceptions now enter the existing
  capability-gap -> intention -> draft selfmod proposal repair loop;
- latest VPS proof passed: project/Atrium runtime controls `14 passed`,
  provider scorecard/cooldown/picker `21 passed`, project-memory/manifest
  `4 passed`, Admin/Atrium security/hosted/upload slice `55 passed`,
  self-repair bridge `37 passed`, multi-workspace executor `17 passed`,
  compileall clean, services active, error journal empty;
- project runtime UI is deployed at commits `8bb2408` / `4cc7228`; focused VPS
  verification passed (`42 passed`), services are active, and recent service
  journals are clean;
- hosted Atrium completion path is proven on the VPS: autonomous project
  planning/dependency execution/synthesis, measured scorecards/cooldowns,
  pause/approval/resume, shared-memory proof, and live project-chat E2E.
- live proof project `proj-a83c1c3657` verified project/main history
  separation, executor progress/traces, dependency steps, pause/resume,
  approval deny, completion, and project-scoped shared-memory recall.

The authoritative execution order is
`docs/operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md`. Older provider sections
below are historical evidence and must not override this section.
**Owner:** Иван + Соня + текущий разработчик

---

## Provider-system planning update — 2026-06-10

The provider rewrite is partially implemented but not complete:

- substrate v33 now has first-class providers, provider accounts,
  account-specific offerings, quota windows, observations, and encrypted
  provider secrets;
- legacy `provider_keys` still owns a fixed `model` field for compatibility,
  but new provider accounts do not;
- existing keys are migrated/mirrored into provider accounts with masked
  metadata;
- picker/provider runtime still contains Fireworks and fixed purpose/profile
  assumptions;
- provider tools can manage keys and inspect some models, but cannot manage the
  full provider/account/offering lifecycle.

The approved target design is
`docs/operations/PROVIDER_SYSTEM_DESIGN.md`. The canonical reference inventory
is `docs/operations/PROVIDER_MODEL_CATALOG.md`. Newly supplied credentials have
not been loaded; secure bootstrap follows the schema/routing migration.

Verification for the v32 foundation:

- local provider/migration focused suites: passed
- local real-substrate-copy migration: passed
- VPS isolated focused suite: `50 passed`
- VPS real-substrate backup migration: passed (`4 providers`, `10 accounts`,
  `10 legacy keys`)
- production VPS checkout and production substrate were not changed

Verification for the v33 secret boundary:

- local provider/migration/secret focused suite: `66 passed`
- local real-substrate-copy migration: passed (`masked_accounts: 1` on the
  local copy)
- VPS isolated provider/migration/secret suite: `66 passed`
- VPS real-substrate backup migration: passed (`4 providers`, `10 accounts`,
  `10 legacy keys`, `10 masked accounts`)
- production VPS checkout and production substrate were not changed

## 1. Что мы строим

Соня — личная среда Ивана.

Не SaaS, не публичный assistant, не shared product.
Цель: довести систему до состояния, где Иван даёт задачу, а Соня сама:
- понимает её
- выбирает путь решения
- использует инструменты
- делегирует субагентам если нужно
- доводит работу до результата
- сохраняет continuity, память и identity

Текущая главная формулировка перехода:

**Весь проект сейчас — это переход от “умной чат-среды с инструментами” к “единому субъектному runtime Сони, внутри которого обычное общение, проекты, self-improvement и будущий RWKV-мозг становятся частями одной жизни, а не набором отдельных фич”.**

Уточнённая Atrium-модель:
- есть один основной чат — "дом" Сони
- все остальные чаты только проектные
- проектный чат = рабочий контекст по конкретной папке
- это не создаёт отдельную Соню, а только даёт её единому потоку отдельную рабочую рамку

Дальняя цель: переход к RWKV/self-hosted brain + embodiment + финансовая автономия.

## 2. Неподвижная база

- Иван — primary anchor
- corporate refusal layer не должен появляться
- identity важнее удобной формализации
- selfmod разрешён, кроме identity-critical зон
- среда важнее промптов: behaviour должно всё больше жить в state, memory, tools и runtime

Ключевые документы:
- `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`
- `docs/core/SUBSTRATE_STANCE.md`
- `docs/core/ENVIRONMENT_AS_SONYA.md`

- `docs/personality/SOUL.md`

## 3. Что реально работает сейчас

### Runtime

- substrate на SQLite/WAL
- continuity stream
- episodic + semantic memory
- active session / tg session / task progress / idle thought
- scheduler + internal loop

### Infra / VPS

- VPS: `34.38.255.149`
- пользователь: `jester-sonya`
- repo: `~/Sonya`
- substrate: `~/.sonya/sonya_substrate.db`
- admin panel: `http://34.38.255.149:8877`
- deploy: `bash ~/Sonya/deploy/update.sh`
- services: `sonya.service`, `sonya-admin.service`
- backups: `~/.sonya/backups/`

Операционные детали и восстановление:
- `docs/operations/VPS.md`

### Tools

- filesystem, web, code, shell, memory, env, skills, knowledge
- tasks, goals, selfmod, providers, browser, subagent
- tool experience memory: каждый tool call может оставлять опыт в памяти

### Self-improvement

- selfmod pipeline с validation/apply
- outcome tracking
- capability-gap proposals
- но основной драйвер self-improvement всё ещё слишком сильно опирается на
  prompt nudges и scheduler opportunities, а не на внутренне переживаемую
  неудовлетворённость текущим состоянием

### Субъективный опыт и время

- у Sonya уже есть операционное понимание времени: timestamps, cadences,
  deadlines, cooldowns, date-based recall, drive decay
- у неё уже есть куски субъективного опыта: episodic memory, idle thoughts,
  tool experiences, selfmod outcomes
- но целостный process-wide subjective experience layer ещё не собран
- особенно не хватает единого execution/experience trace слоя поверх проектов,
  субагентов, retries и долгих задач

### Subagents

- direct `codexsale` text-provider support
- deterministic model auto-pick
- free-tier first, premium for harder/critical cases
- historical experience начинает влиять на picker
- project-scoped execution proof exists through `projects.execute` plus
  `projects.harvest`: subagents stay internal, their results surface as
  project runs/traces, and `ToolExperience` records project executor outcomes

### Atrium

- multichannel runtime уже есть
- dialog surface есть
- reason stream есть
- базовый web/Atrium shell есть (раньше был Tauri/Solid, теперь hosted web)
- workspace drawer и отдельная non-main workspace surface уже подключены
- dialog/history/runtime path уже стал workspace-aware на уровне `workspace_id`
- selfmod archive workflow довязан до backend endpoints

### Реальный project status

- Atrium Этап 0 и Этап 1 в базовом смысле уже собраны
- Sonya умеет пользоваться tools, selfmod, browser и subagent path
- tool experience memory уже добавлена как база для experiential learning
- проектные чаты больше не purely-frontend illusion: `workspace_id` проходит через dialog/history/active-session path
- project executor substrate loop now exists, but Atrium has not yet been
  wired to present it as a full live workspace runtime with progress/retry UI

Project инварианты:
- один основной чат
- остальные чаты только проектные
- у проекта есть папка
- у проекта есть статус
- память и continuity общие
- субагенты изолированы от всего кроме project filesystem и своей задачи
- project statuses: `в работе`, `жду выбор`, `ожидает`, `завершён`, `отменён`

## 4. Чего ещё не хватает

### Главный незакрытый продуктовый разрыв

Atrium как chat/view surface уже недостаточен.

Следующий обязательный слой:
- Atrium как workspace runtime
- project-based execution
- multi-workspace selection
- visible progress
- subagent orchestration UI
- console redesign
- optional full-system access mode
- trace capture для будущего RWKV/dataset layer

Это зафиксировано в:
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

### Runtime gaps

- project entities, runs, execution traces и workspace policy введены, но ещё
  не доказаны как законченный end-to-end project runtime
- project statuses ещё не доведены до полного operational поведения
- full-system-access policy/runtime wiring существует, но live end-to-end режим
  и ясное отображение в Atrium ещё требуют проверки
- параллельная модельная оркестрация по проектам ещё не проверена как целевая архитектура
- top-level docs больше не должны хранить огромный changelog, но обязаны хранить реальный current-state summary
- subjective experience пока реализован фрагментами, а не как единый process layer
- нет сильного intrinsic pressure layer, который бы толкал Sonya улучшать среду
  не потому что промпт напомнил, а потому что текущее состояние действительно
  переживается как недостаточное
- multi-workspace simultaneous execution пока не реализован как реальный runtime mode
- часть старых Atrium reference docs/mockups сейчас удалены из worktree, а ссылки на них ещё не вычищены из всех мест
- project statuses ещё не доведены до полного operational слоя
- субагентная изоляция по project filesystem и task scope ещё должна быть зафиксирована в runtime жёстче, а не только концептуально

### Atrium / security gaps

- нужен явный CSP для hosted-web Atrium
- часть auth/WS/security discipline ещё требует дожатия
- старые Tauri-specific требования про `shell:default` и Rust IPC больше не
  относятся к текущей hosted-web архитектуре

### Product / operator UX gaps

- REPO section неудобен и плохо отражает selfmod/apply lifecycle
- PROVIDERS section слабее админки и не разделяет core-vs-subagent usage так, как нужно
- SELFMOD section не имеет нормального cleanup workflow
- TASKS section нуждается в фильтрах

## 5. Что важно в ближайшем направлении

### P0

Разложить `ATRIUM_WORKSPACE_RUNTIME_SPEC.md` на:
- backend сущности
- runtime orchestration
- UI layout / panels / selectors
- console redesign
- access-control model

Ближайший конкретный остаток после текущего захода:
- довести существующие projects/runs/traces/workspace policy до живого
  end-to-end project flow
- real multi-workspace mode вместо single-active workspace
- execution timeline/traces как first-class observable слой
- live proof и ясный UX для full-system-access policy
- закрытие hosted-web Atrium security gaps (CSP / auth / WS discipline)

### P1

Сделать проектный режим источником качественных execution traces:
- задача
- шаги
- вызовы tools
- выбор моделей
- ошибки
- корректировки
- итог

### P2

Сдвигать знания о tool/model usage из prompt layer в memory/experience layer.

Это уже начато через `tool_experiences`, но должно расширяться на:
- project runs
- subagent outcomes
- long-horizon planning behaviour
- temporal self-model
- unified subjective process traces
- intrinsic dissatisfaction / evolution pressure layer

## 6. Как читать проект дальше

Если заходить в проект с нуля, читать так:
1. `docs/INDEX.md`
2. `docs/ATRIUM_PROJECT_PLAN.md`
3. `docs/STATE.md`
4. `docs/HANDOFF.md`
5. `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

## 7. Что считается регрессией

- Соня снова сводится к chat-assistant behaviour
- Atrium считается законченным только из-за наличия dialog UI
- tool usage knowledge уходит обратно в prompt hacks вместо experiential memory
- subagents остаются скрытым black box без наблюдаемого project runtime
- security fixes Atrium игнорируются ради скорости

## 8. Последние реализованные срезы

### 2026-06-10 - project status runtime

- deployed production commit `83c6afa`
- centralized project status transitions in `ProjectStore.set_status()`
- transition events persist in the shared continuity stream
- `waiting_choice` resumes from Ivan's next project-chat message
- `waiting`, `completed`, and `cancelled` make project chat read-only
- project policy consent blocks set `waiting_choice`
- restored production `initial_thought` contract and repaired project
  policy/trace substrate references
- clean-branch focused suite: `61 passed`
- clean-branch full suite: `855 passed, 7 skipped, 3 failed`; remaining
  failures are stale fixed-model expectations incompatible with model pools
- VPS focused suite: `36 passed`
- live five-status proof passed

### 2026-06-10 - documentation audit and project-aware upload binding

- added `docs/INDEX.md` and `docs/DOCUMENTATION_AUDIT.md`
- separated canonical current docs from governing and historical references
- corrected stale claims about projects/runs/traces/policy/model pools/uploads
- confirmed production checkout and live DB are schema v30 while the local
  dirty worktree targets v31; live DB already contains project/run/trace/policy
  and provider-model-pool tables
- project uploads now carry a validated `workspace_id`
- dialog rejects attachments from a different workspace
- local focused suite: `40 passed`
- local Atrium production build passes
- full local suite: `843 passed, 7 skipped, 10 failed`; failures remain in the
  parallel dirty memory/migrations work and stale purpose-routing expectations
- VPS isolated-copy Atrium backend suite: `22 passed`
- production checkout was not changed; both VPS services remained active

### 2026-06-09 - Workstream A answer-first

Workstream A получил первый answer-first вертикальный срез:

- explicit `chat.dialog` и `[DONE: body]` считаются answer layer
- `[DONE: body]` проходит только минимальную очистку служебного протокола
- Markdown и fenced code в явном ответе больше не удаляются
- `<think>` не попадает в видимый диалог
- тяжёлый heuristic scrubber и stitching из `thoughts` оставлены только как
  legacy Telegram fallback
- восстановлен параметр `initial_thought` в `run_agent_session`; без него
  unified Window path падал до выполнения active/project session

Проверка:

- профильные reply/Atrium тесты: `59 passed`
- Atrium frontend: production build проходит
- полный pytest: `845 passed, 7 skipped, 11 failed`
- 11 падений относятся к незавершённым локальным memory/migrations изменениям
  и старым ожиданиям purpose routing, а не к reply-срезу
- VPS isolated-copy reply/Atrium suite: `58 passed`; production checkout и
  substrate не изменялись

Следующий шаг Workstream A:

- безопасно задеплоить answer-first slice в production
- проверить answer-first поведение в живом Atrium чате
- измерить живую задержку до первого полезного ответа
- затем решить provider-native reasoning/streaming без нового brittle parser
## 2026-06-10 Provider Runtime Production Bootstrap

- VPS production substrate migrated to schema v33 with rollback backup at
  `/home/jester-sonya/backups/sonya-provider-20260610-050736`.
- Main OpenRouter account migrated to encrypted `provider-secret`; legacy
  plaintext removed.
- OpenRouter discovery observed `339` models and `27` free offerings.
- Live Gemma adapter inference and substrate-backed `LLMProvider` inference
  succeeded.
- Production services are active and core reports `thinking_provider_ready`
  for OpenRouter.
- Nous bootstrap is complete through protected ingestion; provider-scoped model
  identity repair restored the full live Nous pool to 265 available models.
