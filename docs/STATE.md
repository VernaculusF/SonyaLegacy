# STATE.md — текущее состояние Сони

**Status:** Active
**Type:** Current project state
**Last updated:** 2026-06-06
**Owner:** Иван + Соня + текущий разработчик

---

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
- `docs/core/RUNTIME_LESSONS_FROM_PI.md`
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
- главный текущий разрыв не в отсутствии UI вообще, а в том, что Atrium ещё не стал project/workspace runtime

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

- project entities ещё не введены
- project execution trace schema ещё не спроектирована
- full-system-access mode ещё не реализован
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

- нужен явный CSP
- нужно убрать или сильно ограничить `shell:default`
- чувствительные операции нужно переносить из JS в Rust IPC handlers
- часть WS/security discipline ещё требует дожатия

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
- substrate-level `project` / `project_run` / `workspace_binding`
- real multi-workspace mode вместо single-active workspace
- execution timeline/traces как first-class слой
- real backend policy for full-system access
- закрытие Atrium security gaps (CSP / capabilities / IPC)

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
1. `docs/STATE.md`
2. `docs/HANDOFF.md`
3. `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
4. `docs/atrium/PLAN.md`
5. `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`

## 7. Что считается регрессией

- Соня снова сводится к chat-assistant behaviour
- Atrium считается законченным только из-за наличия dialog UI
- tool usage knowledge уходит обратно в prompt hacks вместо experiential memory
- subagents остаются скрытым black box без наблюдаемого project runtime
- security fixes Atrium игнорируются ради скорости
