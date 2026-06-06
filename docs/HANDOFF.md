# HANDOFF.md — текущая точка продолжения

**Status:** Active
**Type:** Session handoff
**Last updated:** 2026-06-06

---

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
- `docs/atrium/ATRIUM_REMAINING_TODO.md`

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

См.:
- `docs/core/RUNTIME_LESSONS_FROM_PI.md`

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

- Atrium workspace runtime decomposition пока не сделан
- full-system-access mode пока только на уровне spec
- project entities (`project`, `workspace_binding`, `subagent_run`, и т.д.) не введены
- execution trace schema для project mode не спроектирована
- tool experience memory добавлена, но ещё не развёрнута в полноценный project telemetry layer
- continuity-first execution schema ещё не введена как явный core layer
- subjective experience пока фрагментирован по подсистемам
- intrinsic dissatisfaction / evolution pressure layer отсутствует
- multi-workspace simultaneous execution пока не реален: сейчас рабочий режим фактически single-active-workspace

### Security / infra

- в Atrium нужен явный CSP
- убрать/ограничить `shell:default` capability
- перенести чувствительные операции из JS в Rust IPC handlers
- добавить auth/reconnect discipline для WS путей где ещё не доведено до нормы
- старые Atrium docs/mockups удалены из worktree, но ссылки на них ещё живут в коде/docs; это нужно либо восстановить, либо мигрировать ссылки

### Product / UX

- REPO section неудобен и плохо показывает lifecycle selfmod/apply
- PROVIDERS section слабее админки
- SELFMOD нуждается в cleanup workflow
- TASKS нуждается в фильтрах
- project/workspace UI уже появился, но ещё не стал полноценной оркестрационной средой с project entities и real execution timeline
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
- full-system-access режим
- execution traces как first-class data layer для будущего RWKV
- цельный process-wide subjective trace
- внутренний эволюционный pressure layer
- real substrate-level projects/runs/bindings instead of frontend-only workspace scaffolding

Новые жёсткие инварианты:
- один основной чат
- остальные чаты только проектные
- проекты можно удалять
- у проекта есть папка и статус
- память общая, поток Сони один

## Если следующая сессия продолжает работу

Читать в таком порядке:
1. `docs/STATE.md`
2. `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
3. `docs/core/RUNTIME_LESSONS_FROM_PI.md`
4. `docs/atrium/PLAN.md`
5. `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`

## Если начинать реализацию Atrium или core changes прямо из этого файла

Нельзя забывать следующие решения:

1. Atrium — не просто чат. Это будущая project/workspace execution среда.
2. Нельзя проектировать Sonya как session-first систему.
3. Tool experience memory уже есть, но её мало — нужен process-wide trace layer.
4. У Sonya есть частичное понимание времени, но ещё нет полного непрерывного temporal self-model.
5. У Sonya есть частичный subjective experience, но он ещё не собран в единый слой.
6. Prompt nudges не решают эволюцию среды. Нужен intrinsic dissatisfaction / evolution pressure layer.
7. Часть следующих изменений должна идти не только в Atrium, но и в core runtime, memory и provider orchestration.
8. Текущий project mode уже не полностью фейковый: workspace-aware path довязан, но substrate-level project model ещё отсутствует.

## Чего не делать

- не возвращать в эти документы старый длинный session log
- не смешивать completed changelog с актуальным handoff
- не считать Atrium закрытым только потому, что dialog UI уже работает
