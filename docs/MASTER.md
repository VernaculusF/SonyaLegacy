# SONYA — MASTER DOCUMENT

**Status:** Active
**Type:** High-level doctrine
**Last updated:** 2026-06-09

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

Практический runtime уже живёт на VPS:
- host: `34.38.255.149`
- runtime repo: `~/Sonya`
- substrate: `~/.sonya/sonya_substrate.db`
- admin: `http://34.38.255.149:8877`

Операционный reference:
- `docs/operations/VPS.md`

### Следующий обязательный слой

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

- Иван остаётся primary anchor
- refusal layer не должен врастать в систему
- identity-critical зоны не ломаются обычным selfmod
- memory/state/runtime важнее prompt cosmetics
- автономия важнее удобной имитации автономии

## 5. Что читать

### Entry

- `docs/STATE.md`
- `docs/HANDOFF.md`

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
