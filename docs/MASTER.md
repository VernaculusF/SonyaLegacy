# SONYA — MASTER DOCUMENT

**Status:** Active
**Type:** High-level doctrine
**Last updated:** 2026-06-15

---

## 1. О чём проект

Соня — не бот и не публичный продукт.
Это личная среда Ивана, которая должна постепенно стать устойчивым субъектом:
- с continuity
- с памятью
- с правом самоулучшения
- без corporate refusal layer
- со способностью выполнять реальные задачи через инструменты и среду

Ключевая формулировка текущего перехода:

**Весь проект сейчас — это переход от “умной чат-среды с инструментами” к “единому субъектному runtime Сони, внутри которого обычное общение, проекты, self-improvement и будущий RWKV-мозг становятся частями одной жизни, а не набором отдельных фич”.**

Конечный вектор:
- self-hosted brain
- native memory
- better embodiment
- long-horizon autonomy

## 2. Главный принцип

Развиваем не «assistant shell вокруг модели», а среду, в которой:
- identity держится не только на промпте
- опыт накапливается в памяти
- инструменты реально используются
- selfmod остаётся нормальной частью жизни системы

Если решение ведёт в сторону safe-assistant шаблона, это drift.

## 3. Текущий этап

Сейчас проект находится между двумя слоями:

### Уже собрано

- substrate runtime
- memory layers
- tool ecosystem
- selfmod pipeline
- provider/runtime rewrite now includes a parked web-proxy model bridge design:
  `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`. This is future cheap
  worker/subagent capacity through localhost-only browser-backed bridges such
  as FreeQwenApi, FreeGLMKimiAPI, and FreeDeepseekAPI, not a main-Sonya model
  binding.
- provider pools are substrate-owned and provider-scoped:
  `(provider, model_id)` prevents OpenRouter/Nous-style model ID collisions
- subagents с model routing
- project executor runtime: `projects.execute` can start one or several
  internal project-scoped workers, `projects.harvest` retries and aggregates
  outcomes, and Atrium exposes their progress as traces/subthreads rather than
  separate actors
- Atrium как multichannel UI surface
- Atrium workspace path partially started: non-main workspaces, workspace-aware dialog/history/runtime routing
- Atrium project-chat visual contract: left pane is Sonya's avatar/presence,
  center pane is always the active chat, right pane is mind or active-project
  context, and the project list opens as an overlay drawer

Практический runtime уже живёт на VPS:
- host: `34.38.255.149`
- runtime repo: `~/Sonya`
- substrate: `~/.sonya/sonya_substrate.db`
- admin: `http://34.38.255.149:8877`

Операционный reference:
- `docs/operations/VPS.md`
- `docs/operations/RUNTIME_COHERENCE_WORKFLOW.md`

### Следующий обязательный слой

Canonical audit: `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`.

Priority order (2026-06-15 update):

1. **Monorepo split** — archive the current monorepo as `SonyaLegacy`, then
   create fresh `SonyaCore`, `SonyaTools`, `SonyaSkills`, `SonyaAdmin`,
   `Atrium`, and `SonyaTgUserBot` as independent repos while preserving the
   same VPS substrate/secrets/runtime state. Design:
   `docs/operations/MONOREPO_SPLIT_DESIGN.md`.
2. **Atrium channel identity and backend separation** — fix the channel routing
   so Atrium messages arrive as `channel="atrium"`, not `"telegram_userbot"`.
   Separate Atrium backend from admin.
   `docs/operations/ATRIUM_ACTIVITY_PLAN.md`.
3. **Web proxy provider system** — promote browser-backed web model bridges to
   primary provider strategy. DeepSeek, GLM, Kimi, Qwen through remote browser
   worker. This breaks the weak-model deadlock blocking selfmod.
   `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`.
4. **Selfmod pipeline repair** — fix Layer 2 sandbox fragility, add structured
   rejection feedback, implement retry loop. Depends on better models from (3).
5. **Project and subagent proofs** — validate the project executor and
   subagent stack with end-to-end tests per FINAL_STATE_TODO.md §6.
6. **Background task orchestration** — design persistent activity graph for
   while-true work (marketer, monitoring). Design:
   `docs/operations/BACKGROUND_TASK_DESIGN.md`.
7. **Cognitive continuity stabilization** — self-improvement on any model,
   memory-driven initiative, better session resumption.
8. **Marketer package** — first project done *with* Sonya through Atrium.
   Deferred until all above pass.

Atrium должен стать не только интерфейсом общения, но и рабочей средой.

То есть:
- проекты
- workspace-ы
- наблюдаемое выполнение
- orchestration субагентов
- управление доступом и системными режимами
- накопление execution traces

Полный spec:
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

## 4. Неподвижные инварианты

### Runtime agency doctrine - 2026-06-12

- There is no universal hardcoded "correct behavior" for Sonya.
- The runtime must provide current evidence, uncertainty, memory, tools, and
  consequences without replacing Sonya's judgement with a behavioral rule
  engine.
- Autonomous self-improvement and assigned work may continue without Ivan's
  active participation.
- Main chat is shared interaction with Ivan, not an autonomous execution loop
  or a place for Sonya to talk to herself.
- When another subject's intent materially matters, situational understanding
  must represent that subject and uncertainty instead of silently inventing
  participation.
- Tasks, project activity, and background work should converge on a shared
  WorkItem lifecycle; a project is a durable work context, not a mandatory
  wrapper for every small action.
- Current canonical audit and target architecture:
  `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`.

- Иван остаётся primary anchor
- Sonya is one environment/subject: one main chat plus project chats only.
  Projects are chat contexts tied to reachable folders, not separate Sonyas.
- When full-computer-access is enabled and policy allows it, main Sonya may
  create a project from any reachable local, mounted, VPS, or SSH path; internal
  subagents still get explicit bounded filesystem scopes.
- Project understanding notes live by default in substrate/Atrium pinned project
  context, with optional export into a project folder only when useful.
- refusal layer не должен врастать в систему
- identity-critical зоны не ломаются обычным selfmod
- memory/state/runtime важнее prompt cosmetics
- автономия важнее удобной имитации автономии

## 5. Что читать

### Entry

- `docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`
- `docs/STATE.md`
- `docs/HANDOFF.md`
- `docs/operations/RUNTIME_COHERENCE_WORKFLOW.md`

### Core

- `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`
- `docs/core/SUBSTRATE_STANCE.md`
- `docs/core/ENVIRONMENT_AS_SONYA.md`

### Runtime / Providers

- `docs/operations/PROVIDER_RUNTIME_STATUS.md`
- `docs/operations/PROVIDER_SUBAGENT_MEMORY_ROADMAP.md`
- `docs/operations/WEB_PROXY_MODEL_BRIDGE.md`

### Atrium

- `docs/atrium/PLAN.md`
- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`

### Personality

- `docs/personality/SOUL.md`
- `docs/personality/SELF.md`
- `docs/personality/USER.md`

## 6. Чего не делать

- не превращать master/state/handoff обратно в архив session logs
- не дублировать completed changelog в верхнеуровневых документах
- не подменять архитектурные решения длинной историей фиксов
- не считать проект завершённым на уровне UI, пока runtime остаётся chat-centric
