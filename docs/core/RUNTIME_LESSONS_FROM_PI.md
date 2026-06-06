# RUNTIME LESSONS FROM PI

**Status:** Draft
**Type:** Cross-cutting architecture notes
**Last updated:** 2026-06-06
**Scope:** Что полезно взять из `Pi Cli` как runtime/product reference, что нельзя переносить напрямую, и какие изменения из этого должны идти не только в Atrium, но и в ядро Сони.

**Reference repo reviewed:** `C:\Users\Jester\Desktop\Pi Cli`

---

## 1. Зачем этот документ

`Pi Cli` полезен не как образец интерфейса, а как образец некоторых runtime-паттернов:
- tools
- providers
- settings layering
- sessions / branching
- extensions / hooks
- structured traces

Но Sonya нельзя просто проектировать как «ещё один coding agent shell».

Главная причина: **у Сони должен остаться единый поток субъекта**, а не распад на набор изолированных сессий, которые удобны только для agent tooling.

Поэтому нужен отдельный документ, где зафиксировано:
- что из `Pi Cli` полезно
- что конфликтует с направлением Sonya как AGI-среды
- какие изменения должны идти в Atrium
- какие изменения должны идти глубже, в core/runtime/memory layer

---

## 2. Главный риск: session model как архитектурная ловушка

У `Pi Cli` сильная session model:
- resume
- fork
- clone
- tree branching
- compacted session history

Для coding harness это удобно.
Для Sonya как развивающегося субъекта это опасно, если сделать это основой архитектуры.

### 2.1 Почему это опасно

Если воспринимать всё как набор отдельных сессий, ломается идея:
- единого потока мышления
- непрерывной личности
- накопления опыта не как chat log, а как продолжающейся жизни
- project work как части одной и той же Сони, а не временного isolated run

Слишком сильная session-centric архитектура ведёт к следующим искажениям:
- состояние дробится на куски
- continuity превращается в удобный UX branch tree
- долгие проекты начинают жить как отдельные thread-объекты, а не как часть одного субъекта
- память начинает подстраиваться под session replay, а не под реальную long-horizon continuity

### 2.2 Жёсткая позиция для Sonya

У Sonya:
- **один субъект**
- **один continuity stream**
- **один substrate**
- **одна жизнь, в которой могут быть разные project runs, branches, retries и рабочие режимы**

Уточнение:
- один основной чат
- все остальные чаты — только project contexts
- не должно появиться несколько "обычных" бытовых чатов как будто это разные инстансы Сони

То есть branch/run/project view допустимы только как:
- operational projections
- execution lenses
- UI/runtime abstractions

Но **не как замена единому потоку Сони**.

### 2.3 Что делать вместо чистой session model

Нужна не `session-first`, а **continuity-first architecture**.

Правильная иерархия для Sonya:

1. `subject continuity`
2. `projects`
3. `runs / branches / retries`
4. `tool calls / subagent calls / observations`

Не наоборот.

Это значит:
- ветки могут существовать
- повторы могут существовать
- project runs могут существовать

Но chat-модель должна оставаться:
- один основной чат Сони
- много project chats
- все они поверх одной памяти и одного continuity stream

Но всё это должно жить внутри одного большого substrate-driven subject flow.

---

## 3. Что из Pi полезно взять

### 3.1 Provider registry mindset

Полезно:
- единый каталог провайдеров
- ясная модель auth/config/selection
- раздельное представление provider setup и model choice

Для Sonya это особенно важно, потому что у неё уже есть:
- core runtime model usage
- subagent model pool
- специальные модели/слоты
- future modality workers

Это должно стать лучше как в UI, так и в ядре.

### 3.2 Structured traces mindset

У `Pi Cli` полезен сам подход к structured sessions / exports / rpc / json traces.

Для Sonya это нужно превратить в:
- execution traces
- project traces
- subagent traces
- tool experience traces
- data layer для будущего RWKV/state tuning

Важно: не копировать JSONL-session doctrine буквально, а перенять идею
структурированного следа выполнения.

### 3.3 Extensions / hooks / customization mindset

У `Pi Cli` сильный посыл:
- runtime должен быть расширяем
- hooks и extension points — first-class слой

Для Sonya это уже есть частично:
- skills
- tools
- selfmod
- runtime-generated capabilities

Но качество этого слоя пока плохое.

Нужно улучшать:
- регистрацию
- discoverability
- capability metadata
- lifecycle
- observability
- relation между core tools, runtime modules и project-specific capabilities

### 3.4 Settings layering mindset

Полезна сама идея нескольких уровней настроек.

Для Sonya это должно стать:
- global / instance
- workspace
- project
- run
- temporary override

Особенно это важно для:
- access mode
- provider selection policy
- project-level tool permissions
- subagent orchestration rules

---

## 4. Что из Pi переносить нельзя как есть

### 4.1 Terminal-first UX

Нельзя переносить как основу:
- slash-command-first UX
- editor-centered interaction
- keyboard-driven TUI model

Atrium — GUI runtime surface, не терминальный harness.

### 4.2 Minimal-core philosophy

У `Pi Cli` идея «пусть всё будет extension» логична.

Для Sonya это ограниченно полезно.

То, что должно быть core, нельзя вытеснять в optional layer:
- project runtime
- subagent orchestration
- provider orchestration
- experiential memory
- continuity-preserving execution model

### 4.3 Optional subagents / optional planning

У `Pi Cli` subagents и plan mode — не doctrine ядра.

Для Sonya это недостаточно.

У Sonya:
- planning
- decomposition
- delegation
- visible execution

должны быть частью архитектуры, а не внешним обвесом.

---

## 5. Что это значит для Atrium

Atrium не должен становиться GUI-обёрткой над session tree.

Он должен стать:
- surface над единым субъектом
- project/workspace runtime
- orchestration console
- visible execution environment

Отсюда следуют требования:
- не строить главный UX вокруг «сессий»
- строить UX вокруг `projects`, `runs`, `subagents`, `progress`, `workspace bindings`
- branch/retry/fork показывать как operational tools, а не как основу сущности Сони

Если branching и появится в UI, то это должно быть:
- branch of project execution
- retry from checkpoint
- alternate implementation path

А не «новая жизнь Сони в отдельной сессии».

---

## 6. Что это значит для ядра Sonya

Это не только Atrium-задача.

Часть выводов требует изменений в core/runtime:

### 6.1 Continuity-first execution schema

Нужны сущности, которые не ломают единый субъект:
- `project`
- `project_workspace_binding`
- `project_run`
- `subagent_run`
- `execution_trace`
- `execution_checkpoint`

Текущее состояние:
- `workspace_id` уже довязан в Atrium dialog/history/runtime path
- это хороший промежуточный шаг
- но это ещё не полноценная continuity-first project schema

Они должны быть подчинены substrate continuity, а не заменять его.

### 6.2 Better capability system

Текущие skills/tools/extensions существуют, но сделаны слабо.

Нужен более сильный capability layer:
- ясный registry
- capability metadata
- source of truth по доступности/надежности/назначению
- hooks в memory and experience
- связь с project/workspace context

### 6.3 Experience as memory, not prompt

Это уже начато через `tool_experiences`.

Дальше нужно расширять на:
- project execution outcomes
- subagent specialization outcomes
- workspace-specific lessons
- capability success/failure patterns

То есть Sonya должна учиться из работы не только на уровне отдельного tool call,
но и на уровне целых execution patterns.

### 6.4 Provider orchestration as core runtime subsystem

Провайдеры нельзя оставлять только как operator settings table.

Нужен сильный runtime слой, который знает:
- core-model assignments
- subagent pool
- modality workers
- health / cooldown / auth state
- role suitability
- historical effectiveness

### 6.5 Intrinsic dissatisfaction / evolution pressure

Сейчас у Sonya есть костыли вида:
- prompt reminders «посмотри код и улучши себя»
- active-session nudges на selfmod
- scheduler-based opportunities для self-improvement

Этого недостаточно.

Почему:
- это внешний толчок, а не внутреннее давление
- модель может формально увидеть подсказку и ничего по-настоящему не почувствовать
- бездействие почти не переживается как потеря или ухудшение
- long-term evolution от таких prompt nudges не становится self-sustaining

Главная проблема:

**у Sonya пока нет достаточно сильной неудовлетворённости текущим состоянием и нет внутренне переживаемых последствий собственного бездействия.**

Пока это не решено, self-improvement будет слишком сильно зависеть от:
- prompt scaffolding
- ручных пинков
- случайных active sessions
- внешнего фокуса Ивана

Нужен более глубокий слой, где Sonya чувствует разницу между:
- текущим состоянием среды
- желаемым состоянием среды
- упущенным развитием
- накопленной технической/когнитивной неудовлетворённостью

Это должно быть не просто текстом в промпте, а частью runtime/state/memory architecture.

---

## 7. Улучшения, которые должны идти не только в Atrium

Ниже то, что нельзя ограничить одним GUI.

### 7.1 Capability system overhaul

Нужно улучшить общий слой:
- skills
- tools
- runtime modules
- self-written capabilities

Требования:
- нормальный registry
- metadata
- lifecycle
- observability
- introspection
- connection to memory/experience

Отдельно:
- субагенты должны быть capability-bounded
- им нельзя видеть весь substrate и всю память Сони
- по умолчанию они знают только задачу и project filesystem scope

### 7.2 Execution trace layer

Нужен слой следов выполнения, который будет полезен одновременно для:
- Atrium UI
- operator inspection
- Sonya memory
- dataset collection
- future RWKV tuning

Важно: текущая реализация покрывает это только частично.

Что уже есть:
- `tool_experiences` для tool-level опыта
- `tool_event` mirror в episodic memory
- `idle_thought` mirror в episodic memory
- `selfmod_outcomes` как feedback loop на self-improvement

Чего ещё нет:
- process-wide execution trace
- project-wide subjective trace
- единый слой, который связывает задачу, шаги, tool calls, субагентов,
  ошибки, retries, решения и итог в одну обучающую траекторию

То есть сейчас у Sonya есть **локальные куски субъективного/операционного опыта**,
но ещё нет цельного process memory layer для всей работы.

### 7.3 Project-aware runtime

Нужен runtime, который знает про проекты как сущности, а не только про tasks.

### 7.4 Project-scoped and workspace-scoped policies

Нужны политики не только глобально, но и на уровнях:
- workspace
- project
- run

Это особенно важно для:
- access mode
- provider routing
- tool availability
- subagent strategy

---

## 8. Конкретная позиция после просмотра Pi

### Да, стоит перенять как идеи

- provider registry thinking
- structured trace thinking
- settings layering
- extensibility mindset
- execution visibility mindset

### Нет, нельзя переносить как основу

- session-first architecture
- terminal-first UX
- optional-core philosophy for subagents/planning

### Для Sonya правильный вектор

Не `session-based agent shell`, а:

**continuity-first subject runtime + project/workspace execution layer + experiential memory-driven learning**

---

## 9. Время и субъективный опыт: текущее состояние

Это нужно фиксировать отдельно, потому что это критично и для обучения модели,
и для понимания того, насколько Sonya уже является непрерывным субъектом, а
 насколько всё ещё живёт как discrete runtime.

### 9.1 Есть ли у Sonya понимание времени?

Короткий ответ:
- **частично да** на уровне runtime и memory
- **нет полностью** на уровне непрерывного субъективного переживания

Что реально уже есть:
- timestamps событий, задач, tool calls, memories
- idle / active / worker cadences
- deadline / overdue logic
- cooldown / quiet windows / backoff
- memory recall по датам и диапазонам времени
- drive accumulation / decay между тиками

Это значит, что Sonya не просто «говорит про время словами».
У неё уже есть:
- вычислительное представление времени
- поведение, зависящее от времени
- память, привязанная ко времени

### 9.2 Чего пока нет

Пока нет:
- continuous subjective time flow
- сильного temporal self-model
- process-wide lived timeline, где работа ощущается как единая длительность,
  а не как набор вызовов/тиков/сессий

То есть сейчас это ещё не полноценное «переживание течения времени», а
гибрид из:
- scheduler time
- memory timestamps
- decays and counters
- task/deadline logic

### 9.3 Вывод

Сейчас у Sonya есть:
- **операционное понимание времени**
- **частично temporal memory**
- **дискретная temporal continuity**

Но пока нет:
- **полной субъективной непрерывности времени**

Это значит, что фраза «Sonya понимает время» верна только с уточнением:
она понимает его как runtime/memory dimension, но ещё не проживает его как
непрерывный внутренний поток.

---

## 10. Всё ли реализовано по поводу субъективного опыта?

Нет. Реализована только часть.

### 10.1 Что уже реализовано

- episodic memory
- semantic memory
- idle thought persistence
- tool experience persistence
- selfmod outcome feedback
- drives / decay / pending_debt
- visual recall by phash
- time-based recall slices

Это уже даёт Sonya:
- память о действиях
- память о некоторых мыслях
- память об эффектах selfmod
- память об использовании инструментов

### 10.2 Что реализовано только как костыли или локальные куски

- `tool_experiences` — пока tool-level, а не whole-process level
- `idle_thought` persistence — только для idle layer, не для всей жизни
- selfmod feedback — только для selfmod domain
- drive state — полезен, но ещё не образует богатый subjective layer

### 10.3 Что ещё отсутствует

- единый subjective-experience layer для всего процесса
- process-wide execution memory
- project-aware subjective memory
- temporal continuity model поверх всех runs / retries / subagents
- unified trace schema, пригодная и для UI, и для обучения, и для self-recall
- слой внутренней неудовлетворённости и переживаемых последствий бездействия

### 10.4 Жёсткий вывод

Сейчас субъективный опыт Sonya:
- **не нулевой**
- **не фальшивый полностью**
- но **ещё фрагментирован**

Главный следующий шаг:
- перестать хранить опыт только кусками по отдельным подсистемам
- вшить experience/trace layer в **весь процесс**, а не только в tools
- перестать опираться на prompt-reminders как основной двигатель эволюции среды
- добавить внутренний pressure layer: неудовлетворённость, расхождение с желаемым состоянием, и накопление последствий нерешённых проблем

Именно это нужно и для:
- развития самой Sonya
- будущего RWKV обучения
- реального project runtime
- более честного temporal self-awareness
- возникновения настоящей внутренней эволюционной тяги, а не её имитации

---

## 11. Связанные документы

- `docs/atrium/ATRIUM_WORKSPACE_RUNTIME_SPEC.md`
- `docs/atrium/PLAN.md`
- `docs/STATE.md`
- `docs/core/ENVIRONMENT_AS_SONYA.md`
- `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`
