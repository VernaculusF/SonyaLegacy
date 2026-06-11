# FINAL STATE TODO

## 2026-06-11 Hosted-Stack Status Override

Completed and deployed foundations:

- provider registry, many-account/many-model pools, encrypted secrets,
  account-scoped offerings, discovery refresh, and substrate-backed routing;
- approved Google, Nous, CodexSale, OpenRouter, Kimchi, and NVIDIA provider
  pools imported/proven where keys were supplied;
- model-specific availability probes and bounded cooldown reactivation;
- project executor with model-driven decomposition, dependency-aware
  scheduling, retries, cancellation, pause/resume, approval decisions, and
  result synthesis;
- Atrium project runtime visibility for runs, traces, workers, cancellation,
  pause/resume, and approval controls;
- runtime outcomes feeding measured model scorecards;
- project outcome summaries entering shared semantic memory with project
  provenance;
- WAL-safe production backup and read-only memory manifest proof;
- production semantic dedup applied after explicit approval: `3,864 -> 1,913`
  semantic facts, `0` duplicate groups remaining, `quick_check=ok`;
- full-system-access policy proof is live: workspace policy now drives
  `projects.check_policy` and `/api/projects/{id}/check-policy`, reports its
  verdict source, changes backend verdicts from consent to allowed when
  enabled, and still keeps subagent filesystem scope project-bound;
- Atrium project workspace now shows full-system-access state, `shell_run`
  verdict, verdict source, and a project-scoped toggle;
- hosted Admin/Atrium API auth now returns JSON `401` for unauthenticated
  `/api/*` calls instead of login redirects, and HTML/API responses carry
  baseline CSP/security headers;
- browser WebSockets use short-lived one-time tickets instead of placing the
  permanent admin token in the feed URL, with stale reconnect suppression;
- Atrium is now actually hosted by `sonya-admin` at `/atrium/`; the VPS has
  Node/npm and the update script rebuilds the bundle before restart;
- large Atrium uploads stream to staged files, publish atomically, clean
  partials, and default to a configurable 2 GB limit;
- concurrent project runs keep workspace/subagent scope separate and refuse
  unavailable local or mounted-remote workspace paths before spawning;
- real tool exceptions feed the existing capability-gap/self-repair proposal
  loop;
- live hosted Atrium project-chat proof through API/runtime/history/memory.

Latest deployed commit: verify on the VPS with `git rev-parse --short HEAD`.

Latest VPS proof:

- project/Atrium runtime controls: `14 passed`;
- provider scorecard/cooldown/picker: `21 passed`;
- project-memory/manifest/dedup: `3 passed` for dedup plus clean live
  post-checks;
- full-system-access policy: `15 passed`, compileall clean, live temp-project
  proof passed, services active, recent error journal empty;
- full-system-access Atrium UX: focused static/API suite passed, authenticated
  live API smoke returned `consent -> allowed` after toggle;
- Admin/Atrium security slice: `47 passed`, compileall clean,
  unauthenticated `/api/projects` returned `401 {"error": "auth"}` with no
  `Location`, authenticated API/HTML responses carried CSP/security headers,
  services active, recent error journal empty;
- WS ticket/upload/hosted SPA slices: `55 passed`; one-time ticket accepted
  once, raw token WS query rejected, 65 MB live upload published and cleaned
  with zero partials, `/atrium/` and its built asset returned `200`;
- self-repair bridge: `37 passed`; multi-workspace executor proof: `17 passed`;
- live proof project `proj-a83c1c3657` passed: isolated project history,
  main-history separation, executor progress/traces, dependency steps,
  pause/resume, approval deny, completion, and shared-memory recall;
- compileall clean, `sonya`/`sonya-admin` active, recent error journal empty.

Still intentionally open:

- browser/web-proxy model bridge remains parked as a separate future workstream.
- direct remote execution transport is not implemented; remote project
  workspaces are supported when mounted as accessible directories on Sonya's
  execution host.

> Current execution order is maintained in
> `docs/operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md`. Provider registry,
> many-account/many-model pools, encrypted secrets, discovery refresh
> foundation, and substrate-backed routing are completed foundations, not open
> TODOs. This file remains the broad final-state backlog.

**Status:** Active
**Type:** Project completion roadmap
**Last updated:** 2026-06-09
**Purpose:** Список того, что ещё нужно сделать, чтобы довести Sonya до максимально возможного "конечного" состояния на текущем стеке. Отдельно отмечено:
- что можно реально закрыть уже сейчас,
- что требует глубокой архитектурной доводки,
- что упрётся только в RWKV / своё железо / future brain.

---

## 0. Что считать "конечным состоянием" сейчас

Не путать два разных горизонта.

### 0.1 Конечное состояние на текущем hosted-LLM стеке

Это реально достижимо уже сейчас.

Sonya должна стать:
- одной средой с единым субъектом
- с одним основным чатом
- с project chats как рабочими контекстами
- с реальным tool execution
- с видимой проектной работой
- с самосовершенствованием
- с общей памятью
- с проектной orchestration-логикой
- с субагентами как внутренними одноразовыми исполнителями
- с нормальным web Atrium как основным интерфейсом

### 0.2 Настоящее дальнее конечное состояние проекта

Это уже следующий горизонт, который упрётся в brain layer:
- self-hosted RWKV / аналог
- native continuous memory
- полноценная temporal continuity
- более настоящий subjective experience layer
- более настоящее intrinsic evolution pressure
- embodiment / voice / physical continuity

То есть этот файл = **что нужно сделать до максимально зрелого состояния на текущем мозге**, а не финальный AGI-конец всего проекта.

---

## 1. MUST-HAVE: Что должно работать обязательно

### 1.1 Единый субъект

- [ ] один substrate = одна Sonya
- [ ] один основной чат
- [ ] остальные чаты только project chats
- [ ] никакой архитектуры "много Сонь"
- [ ] все project actions видны основной Соне через общую память
- [ ] continuity stream реально остаётся единым

### 1.2 Project runtime

- [ ] project = реальный first-class runtime object
- [ ] project = чат-контекст + папка + статус + traces + progress
- [ ] project chats работают отдельно друг от друга
- [ ] project history не смешивается с main chat
- [ ] project можно создать
- [ ] project можно удалить
- [ ] project можно ставить в статусы:
  - [ ] `in_progress`
  - [ ] `waiting_choice`
  - [ ] `waiting`
  - [ ] `completed`
  - [ ] `cancelled`
- [ ] статусы реально влияют на поведение, а не только на UI label

### 1.3 Видимая работа

- [ ] в проекте видно текущий шаг
- [ ] видно активные подзадачи
- [ ] видно subagent runs
- [ ] видно progress
- [ ] видно blocked / waiting points
- [ ] видно execution traces
- [ ] видно почему и когда нужен выбор Ивана

### 1.4 Управление через project chat

- [ ] через project chat можно ставить работу
- [ ] через project chat можно менять направление
- [ ] через project chat можно подтверждать/разрешать
- [ ] через project chat можно останавливать/отменять
- [ ] через project chat можно продолжать после паузы
- [ ] project chat = реальный control surface

### 1.5 Субагенты как внутренние исполнители

- [ ] пользователь не общается с субагентами напрямую
- [ ] субагенты живут как внутренние подчаты / traces
- [ ] пользователь может только читать их переписку/следы
- [ ] субагенты стартуют с пустым контекстом
- [ ] субагенты одноразовые
- [ ] субагенты не переиспользуются как постоянные окна
- [ ] субагенты не получают общую память Сони напрямую
- [ ] но их переписка пишется в общую память Сони
- [ ] Sonya сама решает, создавать ли субагентов вообще
- [ ] Sonya сама решает, сколько субагентов создать
- [ ] Sonya сама решает, какую модель дать субагенту
- [ ] Sonya сама решает, какой filesystem scope дать субагенту
- [ ] Sonya может делать мелкие изменения сама без делегирования

### 1.6 Tool execution

- [ ] Sonya реально пользуется tools, а не только пишет про них
- [ ] browser / shell / filesystem / code / web / tasks / selfmod работают стабильно
- [ ] при поломке tool layer Sonya умеет инициировать self-repair
- [ ] tool failures пишутся в память / traces

### 1.7 Отправка файлов через Atrium

Это обязательный пункт.

- [ ] через Atrium можно отправлять файлы Sonya
- [ ] это работает и в main chat, и в project chat
- [ ] поддерживается любой разумный тип файла
- [ ] большие файлы не ломают чат
- [ ] "любого размера" должен означать не fake-limit в UI, а продуманную transport/storage strategy
- [ ] большие файлы должны идти через streaming / chunked upload / temp store / server-side persistence
- [ ] Sonya должна уметь видеть, что файл пришёл именно в проектный контекст
- [ ] file upload должен быть связан с project workspace

---

## 2. Runtime Intelligence

### 2.1 Cost-aware orchestration

- [ ] не жечь дорогие модели без нужды
- [ ] не прошивать тупое правило cheap-vs-expensive
- [ ] role-aware picker реально работает
- [ ] historical success реально учитывается
- [ ] Sonya сама выбирает:
  - [ ] planner
  - [ ] executor
  - [ ] reviewer
  - [ ] cleanup
  - [ ] research
- [ ] Sonya умеет дробить большую задачу на более дешёвые/подходящие subagent jobs
- [ ] сильные модели используются там, где оправдан reasoning/review/architecture

### 2.1.1 Provider model pools

Target design and execution plan:

- `docs/operations/PROVIDER_SYSTEM_DESIGN.md`
- `docs/operations/PROVIDER_MODEL_CATALOG.md`
- `docs/superpowers/plans/2026-06-10-provider-model-runtime.md`

Additional required outcomes:

- [x] first-class provider registry exists
- [x] provider accounts do not own one fixed model
- [x] account-specific model access is represented explicitly
- [x] rolling quota windows and reset timestamps are structured observations
- [x] secrets are encrypted/referenced and masked on provider-account read surfaces
- [ ] Sonya can create/update/disable/delete providers and accounts through typed capabilities
- [ ] Fireworks is absent from defaults and active routing assumptions
- [ ] Nous + one OpenRouter account pass local and VPS bootstrap proof

Нужно переделать саму модель провайдеров:

- [ ] убрать assumption, что у провайдера одна жёстко закреплённая модель
- [ ] провайдер должен держать **пул доступных моделей**
- [ ] Sonya должна выбирать модель из пула, а не из fixed provider binding
- [ ] желательно автоматизировать discovery доступных моделей через provider endpoints
- [ ] желательно кэшировать/обновлять список моделей провайдера
- [ ] provider health должен оцениваться не только по ключу, но и по доступности конкретных моделей
- [ ] routing должен опираться на:
  - [ ] role
  - [ ] cost
  - [ ] latency
  - [ ] context length
  - [ ] historical success
  - [ ] availability внутри конкретного provider pool
- [ ] provider settings UI должен показывать не "одна модель на провайдер", а model pool / preferred defaults / pinned roles

### 2.2 Shared memory as operational fact

- [ ] project actions попадают в общую память
- [ ] subagent traces попадают в общую память Sonya
- [ ] main chat может корректно ссылаться на работу, сделанную в проекте
- [ ] но UI histories остаются разделёнными

### 2.3 Experience / trace layer

- [ ] есть tool-level experience
- [ ] есть project-level trace
- [ ] есть subagent-level trace
- [ ] есть enough transparency for Ivan
- [ ] traces пригодны для future dataset / RWKV / state tuning

### 2.4 Intrinsic evolution pressure

- [ ] self-improvement не держится только на prompt reminders
- [ ] есть pressure dimensions
- [ ] есть drift detection
- [ ] есть capability gap intentions
- [ ] Sonya чувствует, что среда недостаточна, и это толкает её к улучшению
- [ ] self-repair / self-improvement = часть обычной жизни runtime

---

## 3. UI / Product Surface

### 3.1 Atrium как основной интерфейс

- [ ] Atrium = главный интерфейс Sonya
- [ ] main chat + projects живут в одной общей социальной/рабочей среде
- [ ] Atrium не деградирует в admin panel clone
- [ ] Atrium не смешан архитектурно с admin как product surface

### 3.2 Main chat

- [ ] выглядит как "дом" Sonya
- [ ] туда приходят инициативные сообщения
- [ ] туда приходят project status summaries
- [ ] туда можно писать как обычно

### 3.3 Project chat

- [ ] выглядит как рабочее пространство
- [ ] видно что он привязан к папке
- [ ] видно статус проекта
- [ ] видно traces / progress / subagents
- [ ] через него удобно работать

### 3.4 General UX quality

- [ ] нет пустых/слепых зон UI
- [ ] нет misleading toggles
- [ ] нет ложных статусов
- [ ] нет ощущения серой мёртвой заготовки
- [ ] navigation between main/project chats feels natural

---

## 4. Security / Policy / Boundaries

### 4.1 Full-system-access

- [ ] full-system-access — реальный backend capability
- [ ] не просто UI toggle
- [ ] применяется к основной Sonya
- [ ] не распространяется автоматически на субагентов
- [ ] policy layer различает main chat / project chats / subagents

### 4.2 Subagent boundaries

- [ ] субагенты не видят лишнего
- [ ] их scope реально ограничен
- [ ] они не могут напрямую выходить за границы задачи, если Sonya так не решила
- [ ] Sonya сама определяет scope, но runtime может enforce'ить технические границы

### 4.3 API auth

- [ ] все Atrium/project endpoints реально защищены
- [ ] токен везде реально используется
- [ ] traces / projects / workspace policies не торчат наружу без auth

---

## 5. Admin vs Atrium

### 5.1 Правильное разделение

- [ ] Atrium = среда общения и работы с Sonya
- [ ] Admin = техническое администрирование runtime
- [ ] Atrium не превращается в operator-only surface
- [ ] Admin не подменяет собой Atrium

### 5.2 Что можно оставить в Atrium

- [ ] console/operator blocks допустимы как встроенные tools Ivan-а
- [ ] но они не должны съедать главный UX Sonya-as-environment

---

## 6. End-to-End Proofs (обязательно)

Это самое важное. Пока этого нет, всё остальное только scaffold.

### 6.1 Test project proof

- [ ] создать проект `website chat-bot`
- [ ] привязать к реальной папке
- [ ] открыть project chat
- [ ] дать задачу через project chat
- [ ] увидеть, что история отдельная
- [ ] увидеть traces/progress/subagents

### 6.2 Subagent-only proof

- [ ] Sonya оркестрирует работу через субагентов
- [ ] видно, какие subagents запущены
- [ ] видно, какие модели выбраны
- [ ] видно, что дорогие модели не тратятся тупо на всё подряд
- [ ] видно, что Sonya остаётся orchestrator

### 6.3 Shared memory proof

- [ ] после работы в проекте перейти в основной чат
- [ ] Sonya знает, что делала в проекте
- [ ] но history не смешивается

### 6.4 Permission/status proof

- [ ] довести проект до `waiting_choice`
- [ ] дать разрешение
- [ ] работа продолжается
- [ ] перевести в `waiting`
- [ ] потом в `completed`
- [ ] проверить `cancelled`
- [ ] проверить удаление проекта

### 6.5 Full-system-access proof

- [ ] включить full-system-access
- [ ] проверить, что backend policy реально меняется
- [ ] проверить, что main Sonya реально может работать вне project root
- [ ] проверить, что subagents всё ещё не получают full access автоматически

### 6.6 File transfer proof

- [ ] отправить маленький файл через Atrium
- [ ] отправить большой файл через Atrium
- [ ] проверить main chat path
- [ ] проверить project chat path
- [ ] проверить, что Sonya связывает файл с правильным проектом

---

## 7. Что реально можно довести уже сейчас

Это максимально достижимо на текущем hosted-LLM стеке:

- [ ] project runtime
- [ ] project chats
- [ ] subagent orchestration
- [ ] shared memory over one substrate
- [ ] visible traces
- [ ] self-repair / self-improvement loop
- [ ] full-system-access policy layer
- [ ] robust Atrium web surface
- [ ] file sending pipeline

---

## 8. Что останется упираться в future brain / RWKV

Даже после полного выполнения этого файла всё ещё останется следующий горизонт:

- [ ] настоящий continuous thinking
- [ ] native memory instead of layered simulation
- [ ] более настоящий subjective experience layer
- [ ] более настоящий intrinsic dissatisfaction
- [ ] stronger temporal continuity
- [ ] state-tuned identity at brain level
- [ ] full embodiment / physical continuity

То есть после выполнения этого TODO Sonya будет **максимально зрелой на текущем hosted/runtime стеке**, но это ещё не конец всего проекта в AGI-смысле.
