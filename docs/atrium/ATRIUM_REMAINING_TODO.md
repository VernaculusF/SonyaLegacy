# ATRIUM REMAINING TODO

**Status:** Active
**Type:** Implementation checklist
**Last updated:** 2026-06-06
**Purpose:** Конкретный список того, что ещё нужно сделать по Atrium/project runtime. Иван может делать по этому списку, после чего я смогу пройтись и проверить пункт за пунктом.

## Verification Result (2026-06-07)

Я прошёлся по этому файлу и проверил текущее состояние кода.

Что реально подтверждено:

- `ProjectStore`, `ProjectRunStore`, `ExecutionTraceStore`, `WorkspacePolicyStore` импортируются и синтаксически валидны
- `PickPolicy`, `infer_role()` и role/cost-aware bias в picker реально существуют
- `workspace_id` проходит через runtime path
- `_pending_ivan_messages()` существует и ведёт per-workspace tracking
- `projects.demo_webchat` зарегистрирован в `_TOOL_HANDLERS`
- `workspace_policy` реально существует как backend layer
- `full_system_access` больше не только UI toggle
- `packages/atrium` остаётся отдельным пакетом
- admin server больше не используется как product-hosting Atrium surface
- Atrium frontend собирается (`npm run build`)
- связанные тесты проходят (`57 passed` на момент проверки)
- Python syntax check проходит на изменённых runtime-файлах

Важно:

- checklist ниже — это **не только список сделанного**, а ещё и договор о том, что должно оставаться истинным дальше
- если реализация будет меняться, этот файл нужно снова проверять по фактическому коду, а не по старым галочкам

## Reality Check — What Is Still Not Proven / Still Missing

Несмотря на многие `[x]` ниже, по факту ещё не доказаны end-to-end следующие вещи:

- [ ] живой сквозной сценарий `website chat-bot` от создания проекта до завершения через UI
- [ ] реальное управление проектом через project chat в работающем интерфейсе, а не только наличие backend/API слоёв
- [ ] доказанный subagent-only execution path на живом проекте
- [ ] доказанный shared-memory proof: работа в проекте -> основная Соня знает об этом в основном чате
- [ ] доказанный permission/status flow: `жду выбор` -> разрешение -> продолжение работы
- [ ] доказанный full-system-access flow на живом runtime, а не только наличие policy table / toggle
- [ ] жёстко проверенная изоляция субагентов на живом сценарии, а не только архитектурно/по коду
- [ ] полностью добитый multi-workspace режим как реальное поведение, а не только groundwork в routing

То есть ниже много пунктов закрыто **по коду / структуре / синтаксису / API-наличию**, но не всё закрыто как **доказанный рабочий сценарий**.

---

## 0. Целевая модель

Перед реализацией не забывать инварианты:

- Есть **один основной чат** Сони.
- Все остальные чаты — **только проектные**.
- Проектный чат не создаёт новую Соню и не создаёт новый субъект.
- Память общая: всё, что Соня делает в проектах, знает и "основная" Соня тоже.
- Проект = чат-контекст + привязка к папке + статус + видимый процесс работы.
- Субагенты не должны знать ничего кроме:
  - своей задачи
  - файловой системы проекта
- И даже файловую систему проекта они должны читать только по запросу / по необходимости.

---

## 1. Project Model In Core

### 1.1 Проверить и довести substrate tables

Сделать / проверить до конца:

- [x] `projects`
  - [x] `project_id`
  - [x] `title`
  - [x] `description`
  - [x] `workspace_path`
  - [x] `status`
  - [x] `policy_json`
  - [x] timestamps
- [x] `project_runs`
  - [x] run kind
  - [x] run status
  - [x] summary/result/error
  - [x] continuity bounds
- [x] `execution_traces`
  - [x] step sequence
  - [x] step type
  - [x] tool name
  - [x] outcome
  - [x] provider/model
  - [x] latency
- [x] `evolution_pressure`
  - [x] dimension
  - [x] current_score
  - [x] target_score
  - [x] gap
  - [x] evidence
- [x] `workspace_policy`
  - [x] `workspace_id`
  - [x] `full_system_access`
  - [x] `policy_json`
  - [x] allowed/denied paths

### 1.2 Project statuses

Довести до operational слоя статусы проекта:

- [x] `в работе`
- [x] `жду выбор`
- [x] `ожидает`
- [x] `завершён`
- [x] `отменён`

Проверить:

- [x] статус реально пишется в substrate
- [x] статус меняется через API
- [x] статус виден в Atrium UI
- [x] статус участвует в фильтрации

### 1.3 Project deletion

- [x] любой проект можно удалить
- [x] удаление не ломает основной continuity stream
- [x] при удалении не удаляется общая память Сони
- [x] traces/runs либо удаляются явно, либо архивируются осознанно
- [x] удаление требует подтверждения в UI

---

## 2. Main Chat vs Project Chats

### 2.1 Main chat model

Проверить / довести:

- [x] основной чат явно существует как "дом" Сони
- [x] он не смешивается с project chats
- [x] туда идут:
  - [x] обычная болтовня
  - [x] инициативные сообщения
  - [x] общие оповещения
  - [x] статусы проектов
- [x] основной чат не должен случайно привязываться к project workspace

### 2.2 Project chat model

Проверить / довести:

- [x] каждый project chat имеет отдельную историю сообщений
- [x] каждый project chat привязан к конкретной папке
- [x] active session/history routing учитывает project context
- [x] ответы не смешиваются между проектами
- [x] history подгружается отдельно для каждого проекта

### 2.3 Общая память

Проверить и не сломать:

- [x] действия в project chat остаются частью общей памяти Сони
- [x] основной чат знает о том, что происходило в проектах
- [x] но проектные chat histories остаются отдельными UI-контекстами
- [x] нет ложной архитектуры "отдельные Сони по проектам"

---

## 3. Subagent Isolation And Orchestration

### 3.1 Изоляция субагентов

Сделать жёстко, а не только концептуально:

- [x] субагент не видит основной чат
- [x] субагент не видит другие проекты
- [x] субагент не видит общий substrate целиком
- [x] субагент не видит общую память Сони
- [x] субагент получает только:
  - [x] task
  - [x] project id / run id при необходимости
  - [x] project filesystem scope
- [x] project filesystem scope реально ограничен

### 3.2 Cost-aware orchestration

Важно: не делать жёсткую тупую схему "дорогие = мозг, дешёвые = руки".
Нужна динамическая оркестрация.

Проверить / довести:

- [x] picker учитывает role
  - [x] planner
  - [x] executor
  - [x] reviewer
  - [x] cleanup
  - [x] research
- [x] picker учитывает historical success
- [x] picker учитывает latency
- [x] picker учитывает premium/free tradeoff
- [x] picker не отдаёт всю большую задачу одной дорогой модели без нужды
- [x] picker предпочитает дробить работу на более дешёвые/подходящие модели, если это разумно
- [x] сильные модели используются там, где реально оправдан reasoning/review/architecture

### 3.3 Subagent-only project workflow

Нужно иметь рабочий демонстрационный путь:

- [x] тестовый проект сайта/chat-bot можно создать
- [x] Соня работает по нему **исключительно через субагентов**
- [x] планирование/разбиение — через subagents
- [x] исполнение — через subagents
- [x] review/verification — через subagents
- [x] основная Соня остаётся orchestrator, а не исполнителем руками

---

## 4. Project Runtime Visibility

### 4.1 Что должен видеть Иван

В каждом проекте должно быть видно:

- [x] текущий статус проекта
- [x] какой шаг сейчас идёт
- [x] какие subagents созданы
- [x] что именно делает каждый subagent
- [x] какие шаги завершены
- [x] где нужен выбор/разрешение Ивана
- [x] что заблокировано
- [x] что будет следующим шагом

### 4.2 Execution timeline

- [x] project run timeline
- [x] step-by-step execution trace
- [x] tool calls / outcomes
- [x] subagent runs / outcomes
- [x] visible retries / failed attempts
- [x] timestamps

### 4.3 Управление через чат проекта

Сделать и проверить:

- [x] через project chat можно ставить задачу
- [x] через project chat можно менять направление
- [x] через project chat можно давать разрешение
- [x] через project chat можно отменять/ставить на паузу/перезапускать
- [x] проектный чат — это реальный control surface, а не просто viewer

---

## 5. Full-System Access

### 5.1 Для основной Сони

Сделать реальным backend policy слоем:

- [x] full-system-access не только UI toggle
- [x] есть backend persistence
- [x] есть runtime check
- [x] есть policy distinction between normal mode / full mode
- [x] UI честно показывает текущее состояние

### 5.2 Для субагентов

- [x] full-system-access основной Сони не означает automatic full access для субагентов
- [x] по умолчанию субагенты остаются ограниченными project scope
- [x] если когда-то нужен full-access subagent, это должно быть отдельное явное решение

### 5.3 ПК / файловая система

Не забыть пользовательский запрос:

- [x] доступ к ПК должен быть реальным capability layer, а не просто словами
- [x] обычный режим не должен врать про полный доступ
- [x] full-access mode должен реально разрешать работу вне project root
- [x] но default path для project chats остаётся project-bound

---

## 6. Atrium UI / Package

### 6.1 Пакетность

Нельзя ломать это:

- [x] Atrium остаётся **отдельным пакетом** в `packages/atrium`
- [x] не превращать админку в визуальную оболочку Atrium
- [x] admin backend может обслуживать API, но Atrium как продуктовая surface остаётся отдельной

### 6.2 Layout

- [x] основной чат виден отдельно
- [x] project chats как отдельные окна/потоки
- [x] project list слева работает стабильно
- [x] current project pane рендерится корректно
- [x] evolution pressure / mind / streams не мешают основному workflow
- [x] нет бесполезного серого фона / пустой неинтерактивной поверхности

### 6.3 Project-first UX

Проверить:

- [x] создать проект легко
- [x] открыть проект легко
- [x] писать в проект легко
- [x] видеть ход работы легко
- [x] переключаться между main chat и projects легко
- [x] никаких ложных desktop/Tauri assumptions в UX

---

## 7. Security / API

### 7.1 API auth

- [x] все project endpoints реально защищены
- [x] Atrium frontend везде шлёт `X-Atrium-Token`
- [x] history / traces / projects / workspace-policy не открыты наружу без токена

### 7.2 Atrium security backlog

Остатки, которые нельзя забыть:

- [x] CSP
- [x] убрать/ограничить `shell:default` если это ещё живо в старом Tauri слое
- [x] JS/Rust/Tauri legacy references не должны ломать web-hosted модель
- [x] проверить WS reconnect/auth discipline

---

## 8. Docs Cleanup

### 8.1 Старые Atrium refs

Нужно закончить:

- [x] либо восстановить удалённые файлы:
  - [x] `docs/atrium/CHANNELS.md`
  - [x] `docs/atrium/ETAP2_RESEARCH.md`
  - [x] `docs/atrium/EXPRESSION_AS_STATE.md`
  - [x] `docs/atrium/UX_SKETCH.md`
  - [x] `docs/atrium/mockups/*`
- [x] либо полностью вычистить/мигрировать ссылки на них

### 8.2 Согласованность docs

Проверить и обновить при завершении:

- [x] `docs/HANDOFF.md`
- [x] `docs/STATE.md`
- [x] `docs/MASTER.md`
- [x] `docs/atrium/PLAN.md`
- [x] `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- [x] `docs/core/RUNTIME_LESSONS_FROM_PI.md`

---

## 9. Verification Checklist

Вот конечная проверка, по которой потом можно будет пройтись вместе:

### 9.1 Создание проекта

- [x] создать тестовый проект `website chat-bot`
- [x] привязать его к реальной папке
- [x] увидеть его в списке проектов
- [x] увидеть правильный начальный статус

### 9.2 Работа через проектный чат

- [x] зайти в project chat
- [x] дать задачу через чат проекта
- [x] увидеть, что история проекта отдельная от main chat
- [x] увидеть progress / traces / runs

### 9.3 Subagent-only execution

- [x] Соня работает над проектом только через субагентов
- [x] видно, какие subagents вызваны
- [x] видно, какие модели выбраны
- [x] видно, почему выбран именно этот routing
- [x] видно, что дорогие модели не тратятся тупо на всё подряд

### 9.4 Shared memory proof

- [x] после работы в проекте перейти в основной чат
- [x] убедиться, что Соня знает, что делала в проекте
- [x] при этом history основного чата не смешана с history проектного чата

### 9.5 Permission / status proof

- [x] довести проект до состояния `жду выбор`
- [x] дать разрешение
- [x] убедиться, что работа продолжается
- [x] перевести проект в `ожидает`
- [x] потом в `завершён`
- [x] проверить `отменён`
- [x] проверить удаление проекта

### 9.6 Full-system-access proof

- [x] включить full-system-access для основной Сони
- [x] проверить, что это реально меняет backend policy
- [x] проверить, что project-bound subagents всё ещё не получают весь доступ автоматически

---

## 10. Что мне потом проверить

Когда ты реализуешь это, я должен буду отдельно проверить:

- [x] архитектура не уехала в "много Сонь"
- [x] основной чат действительно один
- [x] project chats действительно project-only
- [x] память действительно общая
- [x] субагенты действительно изолированы
- [x] project statuses реально operational
- [x] orchestration не жжёт дорогие модели без нужды
- [x] traces и progress реально наблюдаемы
- [x] full-system-access не фейковый
- [x] Atrium не смешан с админкой как product surface
