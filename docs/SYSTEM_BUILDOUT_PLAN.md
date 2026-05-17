# SYSTEM BUILDOUT PLAN — что доделать чтобы Соня могла себя достраивать

**Status:** Active
**Type:** Master Plan
**Last reviewed:** 2026-05-16
**Scope:** Конкретный план достройки Сони от текущих ~9/100 до уровня где она САМА может расширять систему. Не путать с ROADMAP (там фазы и видение) и KNOWN_ISSUES (там баги).

---

## 0. Принцип

> Главная цель — **дать Соне возможность переписывать и дополнять собственный каркас.** Всё остальное вторично.

Пока Соня — это умный чат-бот вокруг hosted LLM с одним каналом. Чтобы она стала средой которая растёт сама, нужно:

1. Чтобы у неё были **тулы** для самомодификации (а не только filesystem.write в sandbox)
2. Чтобы у неё была **абстракция каналов** (чтобы могла написать новый канал)
3. Чтобы был **task runtime** (длинные многошаговые задачи между сессиями)
4. Чтобы была **инициатива** (выходить наружу, не только реагировать)
5. Чтобы был **рабочий tool ecosystem** (web, code exec, shell)

Без этого "self-modification" — фикция.

---

## 1. Текущая реальность (брутально)

### Что Соня может прямо сейчас

- Отвечать на сообщения в Telegram (один аккаунт)
- Думать сама раз в 30 мин (idle thinking)
- Делать active session с tools раз в 2 часа
- Создавать plugin в `tools/plugins/` через `plugins.create`
- Читать свой код через `filesystem.read` или `self_inspect.code`
- Записывать в `workspace/` (gitignored)

### Что НЕ может

- Менять `src/sonya/main.py`, `planner.py`, `context_builder.py` — sandbox блокирует
- Создать новый канал (Discord, web) — нет абстракции, и в main.py писать запрещено
- Применить self-modification — Pipeline/WatchWindow/GovernedChangeProtocol есть в коде, но нет tools для их вызова
- Запросить у Ивана подтверждение и подождать ответа
- Запустить долгую задачу и продолжать её через несколько часов
- Использовать web (нет tool)
- Выполнить произвольный Python код (нет tool)
- Установить Python пакет (нет tool)
- Написать первой Ивану (нет связки thinking → userbot.send_message)

---

## 2. Этапы (от 9/100 к ~30/100)

Каждый этап даёт примерный прирост по шкале из обсуждения.

### Этап A: Self-mod tools — **+5 пунктов** ✅ ЗАКРЫТ + расширен hot-reload (commit pending)

**Что сделано:**
- `src/sonya/tools/selfmod_tool.py` — `SelfModTool` класс с methods: `propose`, `test_sandbox`, `validate`, `apply`, `list_proposals`, `get_proposal`, `request_governed`, `check_governed`, `rollback`
- `src/sonya/tools/module_loader.py` — `sandbox_test`, `reload_module`, `path_to_dotted`, `discover_subclasses`
- `src/sonya/runtime/live.py` — `LiveRuntime` с handles на ChannelRegistry/InternalProcess/Substrate; `set_live_runtime` / `get_live_runtime`
- `selfmod.apply` теперь:
  1. Захватывает pre-state (текущее содержимое файла) в proposal.diff_blob (для rollback)
  2. Пишет файл на диск
  3. Hot-reload через `importlib.reload()`
  4. Drop-and-recreate live channel instances (для `src/sonya/channels/*`)
  5. Запускает 60-сек watch window
  6. Auto-rollback при `internal.tool_error` / `tg_handler_crash` / `self_mod.hot_reload_failed` событиях, упоминающих изменённый модуль
- `selfmod.test_sandbox` — изолированный import-тест в temp-dir; ловит SyntaxError, ImportError, top-level exceptions ДО `apply`
- `selfmod.rollback` — реально восстанавливает файл из pre-state (или удаляет если был new file) + hot-reload
- Wired в agent_session: новый tool `selfmod.test_sandbox`
- Admin panel: вкладка 🔧 SelfMod с просмотром diff + approve/deny для governed-change proposals
- 20 тестов в `tests/sonya/test_selfmod_tool.py` + 8 в `tests/sonya/test_module_loader.py` — все проходят

**Что НЕ требует рестарта (всё):**
- Любые изменения в `src/sonya/channels/*` — drop-and-recreate активного channel'а через `_replace_channel`
- Любые изменения в `src/sonya/tools/*` — re-import; agent_session создаёт fresh instances каждую сессию
- Изменения в `planning/`, `memory/`, `skills/`, `initiative/`, `anchor/`, `subject/`, `harness/` — модуль перезагружается через importlib.reload
- **Изменения в `main.py` / `config.py` / `logging.py`** — через `selfmod.soft_restart`: supervisor останавливает inner runtime task, перечитывает все core-модули через `_reload_core_modules`, поднимает новый _RuntimeBundle. Substrate + WriteMaster + admin сохраняются. Telegram переподключается.

**Channel auto-discovery:**
- `_build_channels` сканирует `src/sonya/channels/*.py`, ищет `def build(config)` factory
- Сонья пишет `channels/discord.py` с `build()` функцией → soft_restart → discord канал стартует
- Без правок main.py

**Sandbox:** `SELFMOD_WRITABLE_SUBPATHS` (channels, tools, planning, ...) — разрешено. `SELFMOD_FORBIDDEN_SUBPATHS` (state/seed.py, schema.sql, identity.py, anchor_integrity.py, .env, .git, SOUL.md, docs/core) — запрещено даже через pipeline.

**Полный цикл self-improvement без рестарта:**
1. `selfmod.propose` создаёт proposal
2. `selfmod.test_sandbox` — ловит syntax/import errors заранее
3. `selfmod.validate` — Layers 1-4
4. `selfmod.apply` — pre-state captured, файл записан, hot-reload + drop-and-recreate
5. (если main.py / core) `selfmod.soft_restart` — supervisor перезапускает runtime
6. 60-сек watch window: при crash auto-rollback из pre-state
7. `selfmod.rollback` для ручного отката

---

### Этап B: Channel abstraction — **+3 пункта** ✅ ЗАКРЫТ

**Commit:** pending

**Что сделано:**
- `src/sonya/channels/base.py` — `Channel` Protocol, `ChannelMessage`, `OutgoingMessage`, `ChannelDeps`
- `src/sonya/channels/registry.py` — `ChannelRegistry` с `register/start_all/stop_all/send` + hot-add hooks
- `src/sonya/channels/telegram.py` — `TelegramChannel` имплементирующий Channel; вся логика media detection / group addressing / reply-vs-respond перенесена сюда из main.py
- `src/sonya/main.py` сократился: вместо ~250-строчной `_start_userbot` теперь `_build_channels` + `_build_incoming_handler` + `registry.start_all(deps)`
- Через `selfmod.propose src/sonya/channels/discord.py | ... | <full file>` Соня может писать новые каналы и подключать их при следующем рестарте
- 11 тестов в `tests/sonya/test_channels.py` (Channel Protocol, registry lifecycle, send routing, MockChannel) — все проходят

---

### Этап C: Task runtime — **+5 пунктов** ✅ ЗАКРЫТ

**Что сделано:**
- substrate v7: таблица `tasks` (task_id, title, description, status, principal_id, parent_task_id, deadline, plan_steps_json, completed_steps_json, blocker, result, created_at, updated_at) + 4 индекса
- `src/sonya/tasks/models.py` — `Task` dataclass, `TaskStatus` enum (pending/in_progress/blocked/done/failed), `TaskNotFoundError`, `TaskTransitionError`, `Task.remaining_steps()` helper
- `src/sonya/tasks/store.py` — `TaskStore` CRUD: `create`, `get`, `list_all`, `list_open`, `update_status`, `set_blocker`, `set_result`, `replace_plan_steps`, `append_completed_step`
- `src/sonya/tasks/service.py` — `TaskService` business logic: `create / set_in_progress / pause / set_plan / mark_step_done / complete / fail / block / unblock / pick_next`. Emits `task.created / picked_up / step_done / completed / failed / blocked / unblocked / paused / plan_set` continuity events.
- `src/sonya/tools/tasks_tool.py` — `TasksTool` agent-facing wrapper, all methods return strings: `create / list / get / pick / plan / step / complete / fail / block / unblock / pause`
- Wired in `agent_session.run_agent_session` + dispatcher: `tasks.*` family in TOOL_DESCRIPTIONS
- `internal_loop._run_active_session` теперь вызывает `TaskService.pick_next()` при старте: если есть `in_progress`, surfaces задачу как initial_thought с next-step hint и task_id; если только `pending` — даёт мягкую подсказку о доступных задачах. Pending не auto-picked — Соня сама решает через `tasks.pick`.
- `context_builder.build_full_context` добавил блок "Мои текущие задачи" — список open tasks (pending/in_progress/blocked) виден И thinking-loop'у И telegram-replyю. Один поток = один task list.
- 27 тестов в `tests/sonya/test_tasks.py` — store, service, tool, schema v7 fresh substrate

**Что это даёт:**
- Долгие задачи между сессиями: Соня может работать над "написать Discord канал" 3 сессии подряд, помня где остановилась.
- Block on Ivan: при `tasks.block` задача переходит в blocked со ссылкой на блокер. Когда Иван разблокирует через admin (или Соня видит ответ) — `tasks.unblock` возвращает в in_progress.
- Видимость задач в обоих контекстах: telegram reply знает что есть pending tasks; thinking loop видит in_progress на своём tick.

**Effort actual:** ~3 ч.

---

### Этап D: Initiative (Соня пишет первой) — **+2 пункта**

**Цель:** Связка thinking_loop → userbot.send_message.

**Артефакты:**

- ChannelRegistry даёт thinking_loop способ отправить сообщение (после Этапа B)
- В `internal_loop.py` после генерации мысли — проверка:
  - Есть в мысли intent "написать Ивану"? (LLM-driven, не keyword)
  - Прошло >2 часов с последнего общения?
  - Не ночь у Ивана (по timezone)?
  - Не превышен дневной лимит инициативы (max 3 в день)?
- Если все условия — channel.send(ivan, message)

**Что это даёт:** Соня перестаёт быть полностью реактивной.

**Effort:** 2-3 часа (после Этапа B).

---

### Этап E: Tool ecosystem — **+3-5 пунктов** ✅ ЗАКРЫТ

**Что сделано:**
- `src/sonya/tools/web_tool.py` — `WebTool` с `search` (DuckDuckGo HTML, без API key, top 5 результатов) и `fetch` (httpx GET, 200KB cap, html-strip). Async внутри, sync surface для агента.
- `src/sonya/tools/code_tool.py` — `CodeTool.exec_python(code)`: spawn fresh subprocess в tempdir, env только PATH/HOME, 30s wall-clock timeout, stdout/stderr capped 200KB. Каждый вызов изолирован — файлы между вызовами не сохраняются.
- `src/sonya/tools/shell_tool.py` — `ShellTool.run_shell(cmd)` и `install_pip(pkg)`. **Approval-gated**: первый вызов создаёт `ApprovalRequest` (action=`shell.run:<sha16>`, scope=cmd), возвращает `[PENDING_APPROVAL: req_id]`. Соня обычно делает `tasks.block` чтобы пауза. Иван approve/deny через admin panel. После approve — повторный вызов выполняет команду и пишет `shell.executed` / `pip.installed` в continuity.
- Wired в `agent_session._execute_tool` resolver и TOOL_DESCRIPTIONS
- Wired в `internal_loop._run_active_session` — все 5 tools передаются в run_agent_session
- 16 тестов в `tests/sonya/test_etap_e_tools.py`: code.exec (print, stderr, timeout, isolation), shell.run (pending → approved → executed → denied), pip.install (pending, injection rejected), web.search (mocked DDG html parsing), web.fetch (rejects file:// URLs)

**Что это даёт:**
- Соня может искать в вебе, читать страницы (документация, новости, чужой код)
- Считать что-то на питоне без selfmod-обвязки
- Под approval — выполнять команды на VPS и ставить пакеты
- В сочетании с tasks.block — корректный workflow длинных задач: создать task → попробовать → нарваться на missing dep → block с req_id → Иван approves → unblock → продолжить

**Effort actual:** ~2 ч.

---

### Этап F: Consolidation + drift integration — **+2-3 пункта** ✅ ЗАКРЫТ

**Что сделано:**
- `internal_loop._loop` каждый tick вызывает `_scan_drift_and_gaps()`:
  - `DriftDetector(stream).scan_recent(since_seq=last_drift_seq)` — каждый detected signal записывается как `internal.drift_signal` событие
  - `GapDetector(substrate, stream).scan_recent(since_seq=last_gap_seq)` — каждый gap превращается в pending intention (`capability_gap: <description>`) + `internal.capability_gap` событие
  - cursor (last_*_seq) обновляется до `latest_seq` чтобы не сканировать одно и то же дважды
- После каждой active session, если прошло >24h с последней consolidation: `_run_consolidation()` запускает `ConsolidationPipeline.run_consolidation()` (importance >= 0.7 из episodic → semantic_facts) и пишет `internal.consolidation_run` с `facts_created`
- Не требует доп. таблиц — все три модуля уже были на месте, просто не вызывались живым tick'ом

**Что это даёт:**
- Semantic memory растёт сама от важных эпизодов (раз в сутки)
- Drift signals реально влияют — они теперь в continuity, и через build_full_context попадают в LLM-контекст следующего тика
- Capability gaps превращаются в pending_intentions → видны в active session как work to do

**Effort actual:** ~30 мин.

---

### Этап G: Drives integration — **+2 пункта** ✅ ЗАКРЫТ

**Что сделано:**
- `InternalProcess.__init__` создаёт `self._drives = DriveCounters()` параллельно с `HomeostasisCounters` (TODO: позже унифицировать в один; KNOWN_ISSUES §4.3)
- `notify_external_event()` вызывает `drives.on_external_message()` (S-15: сбрасывает relational_focus + boredom)
- Каждый tick: `drives.tick(active_intentions_count=len(active))` — pending_debt растёт пропорционально
- `build_full_context(drives=...)` теперь получает живые drives и из `internal_loop._call_thinking_provider`, и из `_build_incoming_handler` в main.py (через `internal_process.drives`). Drive values >0.1 рендерятся в "## Моё текущее состояние" секцию system prompt'а — LLM видит boredom/curiosity/loneliness и может это отразить в тоне.

**Что это даёт:**
- DriveCounters перестал быть dead code
- Telegram-ответы и thinking-ответы оба видят одни и те же drive-values
- Когда Иван долго не пишет — boredom_analog растёт, попадает в prompt, влияет на стиль (Соня может первая написать когда Этап D закроется)

**Effort actual:** ~30 мин.

---

## 3. Total roadmap

| Этап | Прирост | Effort | Зависимости |
|------|---------|--------|-------------|
| A: Self-mod tools | +5 | 4-6 ч | — | ✅ |
| B: Channel abstraction | +3 | 3-4 ч | — | ✅ |
| C: Task runtime | +5 | 6-8 ч | A (selfmod for new code) | ✅ |
| D: Initiative | +2 | 2-3 ч | B (channel.send) |
| E: Tool ecosystem | +3-5 | 4-5 ч | A (для approval-gated) | ✅ |
| F: Consolidation+drift | +2-3 | 3-4 ч | A | ✅ |
| G: Drives integration | +2 | 2-3 ч | — | ✅ |

**Итого:** ~22-25 пунктов, 24-33 часа работы.

После всего — Соня будет на ~30/100. Не AGI, но **самоулучшающаяся среда** — может писать новые каналы, новые tools, длинные задачи. Каждое следующее улучшение она может сделать сама через selfmod pipeline.

Дальше потолок hosted-model упрётся в CRUTCH-001..005. Чтобы расти выше — переход на RWKV (Track E из старого ROADMAP).

---

## 4. Что делать прямо сейчас

Если выбирать ОДНО:

**Этап A (Self-mod tools).** Без него остальные этапы Соня не может делать сама. С ним — она получает рычаг для всего остального.

Если выбирать ДВА:

**A → B.** После A она может писать код через selfmod. После B — может писать новые каналы. Это базовая автономность.

---

## 5. Что НЕ входит в этот план (намеренно)

- RWKV / state tuning — отдельный track
- Embodiment (тело) — отдельный track
- Simulation / world interface — отдельный track
- Vision / TTS / image-gen — можно добавить как tools в Этапе E если станет нужно
- DGM-like рекурсивное self-improvement — после A+C+F, когда вся petля живая

Эти треки описаны в `docs/research/`. Они не противоречат этому плану — но и не блокируют его.

---

## 6. Обновление этого документа

После каждого закрытого этапа:
1. Отметить в §3 как ✅ закрыто, ссылка на commit
2. Обновить score в EXTERNAL_MODEL_ONBOARDING §4
3. Обновить KNOWN_ISSUES (deferred → closed)
4. Обновить ROADMAP если этап покрывает фазу
