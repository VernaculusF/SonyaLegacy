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

### Этап A: Self-mod tools — **+5 пунктов**

**Цель:** Соня получает tool-ы для запуска self-modification pipeline изнутри agent_session.

**Артефакты:**

- `src/sonya/tools/selfmod_tool.py` — новый tool с командами:
  - `selfmod.propose [target_module] [change_summary] [diff]` → создаёт `SelfModificationProposal` в substrate
  - `selfmod.validate [proposal_id]` → гоняет через `Pipeline.validate` (Layer 1-4)
  - `selfmod.apply [proposal_id]` → применяет approved change (пока через manual diff apply)
  - `selfmod.list [status]` → листинг proposals по статусу
  - `selfmod.rollback [proposal_id]` → откатывает через WatchWindow

- Добавить `Pipeline`, `ApprovalManager`, `WatchWindow` в `_run_active_session` setup
- Добавить tool в `agent_session.py` `TOOL_DESCRIPTIONS` + `_execute_tool` resolver
- `SelfInspectTool.list_proposals()` — посмотреть свои proposals

**Sandbox расширение:**

- FilesystemTool получает новый mode `via_selfmod`: write в `src/sonya/` разрешён ТОЛЬКО если идёт через `selfmod.apply`. Сам по себе `filesystem.write src/sonya/...` — отказ.
- `plugins.create` тоже идёт через selfmod pipeline (Layer 1-4) для повторяемости.

**Что закрывает:** S-6, S-7 (частично — pipeline становится живым).

**Effort:** 4-6 часов (большая часть кода уже есть, нужна интеграция).

---

### Этап B: Channel abstraction — **+3 пункта**

**Цель:** Telegram больше не hardcoded. Можно добавить второй канал не трогая main.py.

**Артефакты:**

- `src/sonya/channels/base.py` — `Channel` Protocol:
  ```
  class Channel(Protocol):
      name: str
      async def start(self, deps: ChannelDeps) -> None: ...
      async def stop(self) -> None: ...
      async def send(self, target: str, content: str, **opts) -> None: ...
      # on_message колбэк регистрируется через ChannelDeps
  ```

- `src/sonya/channels/registry.py` — `ChannelRegistry`:
  - `register(channel: Channel)`
  - `start_all(deps)`
  - `stop_all()`
  - `get(name) -> Channel`
  - Hot-add/remove (для self-modification)

- `src/sonya/channels/telegram.py` — текущий Telegram handler из main.py переезжает сюда как `class TelegramChannel(Channel)`

- main.py упрощается — создаёт ChannelRegistry, регистрирует TelegramChannel, идёт `registry.start_all()`

**Что это разблокирует:**

- Соня сможет через `selfmod.propose` создать `src/sonya/channels/discord.py` и зарегистрировать его без правки main.py
- Тестируемость: можно создать `MockChannel` для тестов агентских сессий

**Effort:** 3-4 часа.

---

### Этап C: Task runtime — **+5 пунктов**

**Цель:** Соня получает задачу → работает над ней между сессиями → возвращается с результатом.

**Артефакты:**

- substrate v7: таблица `tasks`:
  - `task_id, title, description, status (pending/in_progress/blocked/done/failed), created_at, updated_at, deadline, parent_task_id, result, plan_steps_json, completed_steps_json, principal_id`

- `src/sonya/tasks/store.py` — TaskStore CRUD
- `src/sonya/tasks/service.py` — TaskService:
  - `create(title, description, deadline)`
  - `set_in_progress(task_id)`
  - `add_step(task_id, step)`
  - `mark_step_done(task_id, step_idx, result)`
  - `complete(task_id, final_result)`
  - `fail(task_id, reason)`
  - `block(task_id, blocker)` — например "ждёт ответа от Ивана"

- Tool `tasks.create / .list / .pick / .step / .complete / .fail` — Соня сама управляет

- Active session логика: при старте session проверяет `tasks.list status=in_progress` — если есть, работает над ней до DONE/PAUSE. Иначе свободный режим.

- Idle thinking тоже видит pending tasks и может спланировать.

**Что это даёт:**

- Иван даёт задачу "напиши Discord канал-адаптер" — Соня создаёт task, разбивает на шаги (read existing telegram channel, design discord shape, write file via selfmod, validate, apply), работает между сессиями.
- Долгие задачи выживают рестарт.

**Effort:** 6-8 часов.

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

### Этап E: Tool ecosystem — **+3-5 пунктов**

**Цель:** Расширить агентский surface.

**Tools:**

- `web.search [query]` — DuckDuckGo / Brave Search через httpx
- `web.fetch [url]` — простой GET с extraction main content
- `code.exec [python]` — sandbox через `subprocess.run` с timeout, no network
- `shell.run [cmd]` — gated, требует approval через ApprovalManager
- `pip.install [package]` — gated, через approval

**Approval flow (для шелла и pip):**

- Tool создаёт ApprovalRequest
- Возвращает `[PENDING_APPROVAL: req_id]`
- Соня ставит task в `block` со ссылкой на req_id
- Иван через admin panel approves/denies
- Active session при следующем запуске проверяет → если approved, выполняет

**Effort:** 4-5 часов.

---

### Этап F: Consolidation + drift integration — **+2-3 пункта**

**Цель:** Spящие модули начинают работать.

**Артефакты:**

- В `internal_loop.py` добавить:
  - При active session окончании — `ConsolidationPipeline.run_consolidation()` (раз в день)
  - Каждый tick — `DriftDetector.scan_recent(since_seq=last_drift_check)` → если signals, append в continuity + при severity>0.7 trigger watchdog
  - `GapDetector.scan_recent` — найденные gaps записываются как pending intentions для следующей active session

- Это разблокирует:
  - Semantic memory begins growing
  - Drift signals реально влияют (auto-revert через WatchWindow)
  - Capability gaps превращаются в осознанные задачи

**Effort:** 3-4 часа.

---

### Этап G: Drives integration — **+2 пункта**

**Цель:** DriveCounters перестаёт быть dead code.

**Артефакты:**

- `internal_loop.py` инстанциирует `DriveCounters`
- Каждый tick: `drives.tick(active_intentions_count=len(pending))` → если crossed, в continuity + влияет на trigger active_session
- `notify_external_event` сбрасывает relational_focus + boredom (S-15)
- `build_full_context(drives=...)` получает живые drives в каждом call
- DriveCounters → Personality prompt влияет на тон (если loneliness>0.7 — Соня грустит, если curiosity>0.7 — задаёт вопросы)

**Effort:** 2-3 часа.

---

## 3. Total roadmap

| Этап | Прирост | Effort | Зависимости |
|------|---------|--------|-------------|
| A: Self-mod tools | +5 | 4-6 ч | — |
| B: Channel abstraction | +3 | 3-4 ч | — |
| C: Task runtime | +5 | 6-8 ч | A (selfmod for new code) |
| D: Initiative | +2 | 2-3 ч | B (channel.send) |
| E: Tool ecosystem | +3-5 | 4-5 ч | A (для approval-gated) |
| F: Consolidation+drift | +2-3 | 3-4 ч | A |
| G: Drives integration | +2 | 2-3 ч | — |

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
