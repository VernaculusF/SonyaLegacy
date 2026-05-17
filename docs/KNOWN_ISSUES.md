# KNOWN ISSUES — Баги, недоработки, косяки

**Status:** Active
**Type:** Operations
**Last updated:** 2026-05-16
**Stable commit:** `6a7b51b` (1.4 fix pending)
**Scope:** Всё что сломано, работает криво, дублируется или отсутствует. Не путать с INTERIM_CRUTCHES.md — там архитектурные ограничения по дизайну. Здесь — баги и техдолг.

---

## 1. КРИТИЧНЫЕ (ломают работу)

### 1.4 Память разделена между Telegram и Thoughts ✅ ИСПРАВЛЕНО (commit pending)

Решение:
1. `_call_thinking_provider` в `internal_loop.py` теперь использует `build_full_context` так же как Telegram path. Оба пути идут через единую сборку context.
2. `build_full_context` в `context_builder.py` дополнительно подтягивает последние 10 событий из continuity stream: `internal.thought`, `incoming.telegram_message`, `outgoing.response`, `internal.agent_session_outcome`.
3. Теперь thinking loop видит недавние сообщения от Ивана, а Telegram handler видит недавние мысли Сони. Один общий timeline.

### 1.2 SQLite permissions сбрасываются при git reset --hard ✅ ИСПРАВЛЕНО (commit pending)

**Решение:** Создан `deploy/update.sh` — после git reset проверяет права на substrate и снимает stale locks. Также написан корректный systemd unit с `User=jester-sonya` и `ReadWritePaths=/home/jester-sonya/.sonya`. Все операции под одним пользователем — больше нет конфликта root vs jester-sonya.

### 1.3 Зомби-процессы от nohup деплоев ✅ ИСПРАВЛЕНО (commit pending)

**Решение:** systemd unit-ы для `sonya.service` и `sonya-admin.service` с `KillSignal=SIGTERM` и `TimeoutStopSec=15`. При `systemctl stop` процесс получает SIGTERM, делает graceful shutdown (lifecycle.stopped event), затем kill. Зомби-shell от nohup устранены. Fallback на `pkill -9 -f 'python.*sonya'` остался в `update.sh` для случая когда systemd не настроен.

---

## 2. СЕРЬЁЗНЫЕ (работает криво)

### 2.4 Agent session не завершается корректно ✅ ИСПРАВЛЕНО (commit e6fac8c)

После фикса regex модель корректно вызывает один tool за шаг, получает observation, продолжает или пишет [DONE]. Подтверждение в проде получим при следующей active session.

### 2.5 Модель пытается вызвать tools которых нет ✅ ИСПРАВЛЕНО (commit e6fac8c)

**Реальная причина:** не отсутствие tools, а сломанный regex (1.1) — он ломал имя tool так что любой валидный вызов превращался в "Unknown tool". После фикса regex все 14 tools (`self_inspect.*`, `filesystem.*`, `plugins.*`) корректно парсятся и резолвятся в handler.

### 2.7 HEARTBEAT.md содержит мёртвые ссылки ✅ ИСПРАВЛЕНО (commit pending)

Переписан под текущую архитектуру: substrate-based memory вместо `memory_system/db/memory.db`, актуальные tools (`self_inspect.*`, `filesystem.*`, `plugins.*`) вместо OpenClaw API, ссылки на INTERIM_CRUTCHES.md.

---

## 3. СРЕДНИЕ (работает, но некрасиво)

### 3.1 Стикеры/фото/голосовые ✅ ИСПРАВЛЕНО (commit pending)

`_detect_media_kind(event)` распознаёт стикеры (с emoji), фото, голосовые/аудио, видео/видеосообщения, гифки, файлы. Если у сообщения нет text но есть media — формируется текст вида `"[стикер 😏]"` или `"[голосовое сообщение]"` и идёт в planner как обычный input.

### 3.2 Групповые чаты ✅ ИСПРАВЛЕНО (commit pending)

В группах Соня отвечает только когда:
- упомянули по `@username`
- имя в начале сообщения
- reply на её собственное сообщение

В группах ответ всегда через `event.reply()` — чтобы было ясно кому адресовано. Все группы tracked в continuity stream даже без ответа (для context awareness).

### 3.4 LLM response parsing — берёт только первую JSON строку ✅ ИСПРАВЛЕНО (commit pending)

В `main.py` и `admin/server.py` теперь сначала пробуем парсить весь response, fallback на первую строку только при `JSONDecodeError`. Работает с обычными JSON-ответами и со streaming-чанкованными.

### 3.5 Graceful shutdown для Telegram connection ✅ ИСПРАВЛЕНО (commit pending)

`_run_task` теперь сохраняется на инстансе `userbot._run_task`. Метод `userbot.stop()` корректно отменяет task и закрывает connection. При SIGTERM в systemd unit срабатывает graceful shutdown handler в `main.py`.

### 3.6 `_start_userbot` создаёт SonyaUserbot но не использует его .start() ✅ ПРИНЯТО КАК ЕСТЬ

Решено намеренно: `SonyaUserbot.start()` использует callback-based handler, а в main.py нужен handler с доступом к `internal_process`, `provider`, `substrate`, и `_last_msg_time`. Использовать класс целиком пришлось бы с замыканиями — менее читаемо. Сейчас класс держит TelegramClient + lifecycle (`start`, `stop`, `_run_task`), а handler реализован в main где есть полный context.

---

## 4. МЕЛКИЕ / ТЕХДОЛГ

### 4.1 GLOBAL_PROJECT_CHECKLIST дрифт

**Масштаб:** после удаления `tg-bridge` и `sonya_runtime` (пункты 4.5, 4.6) куча секций чеклиста ссылаются на несуществующие модули — §4 OpenClaw compatibility, §5 Runtime shell упоминает `python -m sonya_runtime.tasks.worker`, §8 Memory ссылается на `OpenClaw context_loader.py`, §9 Provider говорит про `tg_bridge.model_client`, §10 Action и §11 Reusable task runtime — всё через `sonya_runtime.*`.

**Решение:** требуется полное переписывание чеклиста под текущую реальность. Сделаем в отдельной задаче после стабилизации основных функций (это не bug, это документационный долг).

**Status:** deferred — не критично для работы Сони, но критично для будущей навигации.

### 4.2 Drift review cadence — следующий до 2026-05-29

### 4.3 Дублирование drive counters

`HomeostasisCounters` (loneliness, curiosity, relational_focus) в `internal_loop.py` vs `DriveCounters` (boredom_analog, curiosity_analog, relational_focus, pending_debt) в `initiative/drives.py`. Не интегрированы.

### 4.4 Отсутствуют implementation plans для Phases 6, 8, 9

### 4.5 `src/sonya_runtime/` ✅ УДАЛЕНО (commit pending)

Папка `src/sonya_runtime/` удалена целиком (executor, tasks, actions, continuity duplicates). Никем не использовалась. Тесты в `tests/sonya_runtime/` тоже удалены.

### 4.6 tg-bridge пакет ✅ УДАЛЕНО (commit pending)

`packages/tg-bridge/` удалён целиком вместе с 14 тестами. Также удалены OpenClaw runner-скрипты в `scripts/` (`launch-openclaw-bridge.vbs`, `run-openclaw-bridge.ps1`, `run-openclaw-worker.ps1`). `pyproject.toml`, systemd unit-ы, deploy/update.sh, admin server PYTHONPATH очищены от ссылок на tg-bridge.

---

## 5. ОТСУТСТВУЕТ

### 5.1 Инициатива — Соня пишет первой

Thinking loop генерирует мысли, но не может отправить сообщение в Telegram. Нет связки thinking_loop → userbot.send_message.

### 5.2 Context compression для agent sessions

Описано в архитектуре, но не реализовано. При достижении лимита контекста — session просто обрезается.

### 5.3 Persistent conversation history

Нет таблицы `chat_messages` в substrate. При рестарте history теряется (кроме episodic memory summaries).

### 5.4 Night mode / timezone awareness

Соня не знает который час у Ивана. Thinking loop тикает 24/7 одинаково.

### 5.5 Rate limiting per-chat

Если кто-то спамит — Соня будет отвечать на каждое. Нет debounce.

### 5.6 Health check endpoint

`Health` class пишет файл, но нет HTTP endpoint для мониторинга.

---

## 7. КРИТИЧНЫЕ (security / data)


### C-4. Admin "stop core" использует SIGKILL без graceful shutdown ✅ ИСПРАВЛЕНО (commit pending)

Теперь:
1. Сначала SIGTERM, ждём до 10 секунд (20 итераций по 0.5s) на graceful shutdown — Соня успевает дописать `lifecycle.stopped` event и release write-master lock
2. Если процесс всё ещё жив — SIGKILL
3. Возвращается `method: "sigterm" | "sigkill"` — видно какой путь сработал
4. Paths берутся из env (`SONYA_PROJECT_ROOT`, `SONYA_VENV_PYTHON`, `SONYA_CORE_LOG_PATH`) с разумными дефолтами
5. Log file handle сохраняется в `_core_log_file` и явно закрывается при stop / следующем start — больше нет leak

### C-5. Admin открывает substrate параллельно с main процессом ✅ ИСПРАВЛЕНО (commit pending)

Решение:
1. `WriteMaster.is_held(path)` — новый classmethod, проверяет лок без acquire (читает PID и проверяет жив ли).
2. `_get_substrate` в admin теперь открывает БД read-only когда core запущен (`Substrate.open(path, read_only=True)`).
3. `api_chat_send` отказывает с HTTP 409 если core запущен — нельзя писать с двух процессов.

Read-операции (dashboard, thoughts, memory, telegram, audit, substrate) работают одновременно с core — SQLite позволяет multiple readers + 1 writer.

### C-6. Layer 4 anchor protection обходит ApprovalManager API ✅ ИСПРАВЛЕНО (commit pending)

`ApprovalManager.find_by_action_pattern(pattern)` — новый публичный метод. `GovernedChangeProtocol.check_governed_approval` теперь использует его вместо прямого SQL по `_sub.connection`. Layer 4 защищён от изменений схемы — public API даёт abstraction barrier.

### C-7. THINGS_NOT_TO_BETRAY проверка хрупкая ✅ ИСПРАВЛЕНО (commit pending)

`_IDENTITY_CRITICAL_KEYWORDS` теперь строится программно из `THINGS_NOT_TO_BETRAY_SEED` через `_build_keywords()`. Каждый pillar разбивается на семантические стемы (`_`-split), плюс exact match. Если pillar переименуется в `state/seed.py` — Layer 4 автоматически подхватит. Дополнительно — фиксированные identity-layer ключи (`things_not_to_betray`, `identity_record`, `identitywriter`, `subject_continuity`).

---

## 8. СЕРЬЁЗНЫЕ (broken integration / dead code)

### S-1. JSON parsing бага в **трёх** местах ✅ ИСПРАВЛЕНО (см. 3.4)

В `main.py` и `admin/server.py` — robust parser. `OpenRouterProvider` будет либо подключён (S-3), либо удалён.

### S-2. `_ThinkingProvider` игнорирует kwargs ✅ ИСПРАВЛЕНО (commit pending)

Теперь `kwargs.get("max_tokens", 1500)` и `kwargs.get("temperature", 0.9)` — defaults сохранены, но caller может переопределить.

### S-3. `OpenRouterProvider` — dead code

**Статус:** deferred — это code worth keeping (хорошая retry/continuation логика). Подключение в production требует адаптацию `_create_thinking_provider` на использование `ProviderBackend` Protocol вместо ad-hoc httpx. Big refactor — отдельная задача.

### S-4. `AccountPool` — dead code

**Статус:** deferred — нужен только когда у нас несколько ключей и реальный rate limit. Сейчас один ключ к OmniRoute. Подключим когда будет смысл.

### S-5. `ProviderRegistry` — dead code

**Статус:** deferred — нужен когда будет больше одной модели одновременно (text + vision + image-gen). Сейчас одна модель — registry излишен.

### S-6. Self-modification pipeline не подключён в runtime ✅ ИСПРАВЛЕНО (commit pending)

`SelfModTool` написан в `src/sonya/tools/selfmod_tool.py`. Wired в `_run_active_session` через `agent_session.run_agent_session(selfmod=...)`. Tool surface в agent_session: `selfmod.propose / .validate / .apply / .list / .get / .governed / .check_governed / .rollback`. `Pipeline`, `WatchWindow`, `GovernedChangeProtocol`, `ApprovalManager` теперь живые — инстанциируются при каждой active session.

Admin panel получил вкладку 🔧 SelfMod с просмотром diff + approve/deny для governed-change proposals. Endpoint-ы `/api/selfmod/list`, `/api/selfmod/{id}`, `/api/selfmod/{id}/approve`, `/api/selfmod/{id}/deny`.

Sandbox: `SELFMOD_WRITABLE_SUBPATHS` (channels, tools, planning, ...) — разрешено. `SELFMOD_FORBIDDEN_SUBPATHS` (state/seed.py, schema.sql, identity.py, anchor_integrity.py, .env, .git, SOUL.md, docs/core) — запрещено даже через pipeline.

### S-7. Dead код Phase 4-6

**Статус:** deferred — то же самое что S-6 + интеграция drift detector / gap detector / consolidation pipeline в thinking loop. Это integration sprint, не bug.

### S-8. `internal_loop.py` лезет в `_stream._sub` (private) ✅ ИСПРАВЛЕНО (commit pending)

`InternalProcess.__init__` принимает `substrate=` параметр, использует его в `_run_active_session`. Fallback на `_stream._sub` остался для совместимости.

### S-9. `_emit_cognitive_events` (sync version) ✅ ИСПРАВЛЕНО (commit pending)

Sync-версия переименована в `_emit_cognitive_events_sync_fallback` и теперь реально используется когда `provider is None`. Не dead-code больше.

### S-10. `agent_session.run_agent_session(initial_thought=...)` ✅ ИСПРАВЛЕНО (commit pending)

`_run_active_session` теперь подтягивает последний `internal.thought` из stream и передаёт как `initial_thought`. Также после сессии пишет `internal.agent_session_outcome` event с `budget_exceeded` flag — раньше он set-ился но не читался.

### S-11. `agent_session._execute_tool` глотает все exceptions ✅ ИСПРАВЛЕНО (commit pending)

`_execute_tool` теперь принимает `stream` параметр. При exception пишет `internal.tool_error` event с tool name, arg preview, error_type, error_message.

### S-12. ⚠️ FilesystemTool без allowlist ✅ ИСПРАВЛЕНО (commit pending)

Полный rewrite `tools/filesystem.py`:
- **Read** — допустим везде под project_root, КРОМЕ `FORBIDDEN_SUBPATHS` (`.env`, `.git/*`, `tg.session`, `schema.sql`, `seed.py`, `SOUL.md`)
- **Write** — только в `WRITE_ALLOWED_SUBPATHS` (`workspace/`, `src/sonya/tools/plugins/`)
- **Component check** — `.env`, `.git`, `tg.session` блокируются на любом уровне пути
- list_dir и tree скрывают forbidden items из вывода

Соня теперь физически не может перезаписать identity-файлы или секреты через `[TOOL: filesystem.write ...]`. Plugin creation (`plugins.create`) тоже идёт через filesystem.write — попадает под allowlist (`tools/plugins/` — разрешён).

### S-13. Read-only mode substrate ✅ ИСПРАВЛЕНО (commit pending)

`Substrate.open(read_only=True)` теперь падает с `SubstrateVersionError` если версия < `WRITABLE_VERSION`. Сообщение: "needs vN+ schema. Open writable to migrate."

### S-14. Episodic memory — retention/decay ✅ ИСПРАВЛЕНО (commit pending)

1. `get_recent(mark_accessed=True)` и `get_by_type(mark_accessed=True)` — параметр по умолчанию True. При каждом подтягивании memories `access_count++`, `retention_strength += 0.1` (capped at 1.0). Кривая Эббингауза работает: использованные воспоминания крепнут.
2. Новый метод `apply_decay(decay_rate=0.05, archive_threshold=0.1)` — multiplicative decay для всех unarchived events; те что упали ниже порога архивируются. Должен вызываться периодически (например из ConsolidationPipeline раз в день).
3. Bulk `_mark_batch_accessed` — один UPDATE для всего batch вместо N запросов.

### S-15. `notify_external_event` сбрасывает только `loneliness`

**Статус:** deferred — `DriveCounters` сейчас dead code (S-7), сбрасывать не от куда. Будет fixed когда DriveCounters интегрируется в runtime.

### S-16. Signal handlers молча проглатывают ошибки ✅ ИСПРАВЛЕНО (commit pending)

Все три ветки (Windows + POSIX add_signal_handler + POSIX fallback signal.signal) теперь логируют `signal_install_failed` с именем сигнала и ошибкой. Сразу видно если что-то не работает.

---

## 9. СРЕДНИЕ

### M-1. `.env.example` неполный ✅ ИСПРАВЛЕНО (commit pending)

Добавлены все переменные: `SONYA_TG_API_ID`, `SONYA_TG_API_HASH`, `SONYA_TG_SESSION_PATH`, `SONYA_ENABLE_TELEGRAM`, `SONYA_ENABLE_THINKING`, `SONYA_ADMIN_PASSWORD`, `SONYA_ADMIN_BIND_HOST`, `SONYA_ADMIN_PORT`, `SONYA_PROJECT_ROOT`, `SONYA_VENV_PYTHON`, `SONYA_CORE_LOG_PATH`. Плюс комментарии про секреты и admin bind.

### M-2. Default model ✅ ИСПРАВЛЕНО (commit pending)

`config.py` и `.env.example` теперь дефолтят на `google/gemma-2-27b-it:free`.

### M-3. `DriveCounters.pending_debt_rate` ✅ ИСПРАВЛЕНО (commit pending)

`pending_debt_rate=0.02` теперь реально используется в `tick(active_intentions_count)`. Раньше был hardcoded `0.02 * N`.

### M-4. `ProposalStatus` — 11 значений, используется 5

Часть enum используется только в dead-code (WatchWindow, governed_change).

### M-5. Тройная запись `intention_overdue` ✅ ИСПРАВЛЕНО (commit pending)

`_emit_cognitive_events_async` и `_emit_cognitive_events_sync_fallback` больше не пишут отдельный `internal.intention_overdue` event для каждого id — overdue ids уже в `cognitive_tick.payload.triggers` как `deadline_overdue:<id>`. Один факт — одна запись.

### M-6. Pipeline Layer 4 — комментарий не соответствует поведению

Комментарий "Layer 4 failure = requires governed change, not outright rejection" верен только если Layers 1-3 прошли. Не задокументировано.

### M-7. AnchorDriftSignal никогда не сохраняется и не триггерит действий

**Где:** `anchor/drift_signals.py:54`

**Проблема:** `DriftDetector.scan_recent` создаёт signals и возвращает list. Никто не сохраняет, никто не реагирует. Layer 4 защита от дрейфа — paper-only.

### M-8. Migrations переисполняют schema.sql на каждом шаге

`migrations.py:33-72`: каждый migration step запускает полный `schema.sql`. Работает из-за `IF NOT EXISTS`, но wasteful.

### M-9. `WriteMaster.lock_path` ✅ ИСПРАВЛЕНО (commit pending)

`Path(str(path) + ".lock")` вместо `with_suffix` — работает на любых путях.

### M-10. `Health._stop_event` пересоздаётся в start

Не критично из-за guard, но fragile.

### M-11. `setup_logging` стирает все handlers

В тестах ломает pytest log capture.

### M-12. JSON formatter не handles non-serializable nested

Не падает (default=str), но logs становятся нечитаемые.

### M-13. `SubjectStateStore.create_snapshot` non-atomic

read seq → read state → write snapshot — между шагами может быть concurrent write.

### M-14. `IdentityWriter.write_via_governed_change` не проверяет уникальность change_id

Replay одного change_id silently re-пишет identity.

### M-15. Unused imports в `governed_change.py` ✅ ИСПРАВЛЕНО (см. C-6)

После rewrite в C-6 — все импорты используются.

### M-16. `SelfModificationProposal` — frozen dataclass, но `update_status` возвращает новый объект

Caller's old reference stale. API gotcha, надо документировать.

### M-17. `tools/__init__.py` не экспортирует `hot_loader` ✅ ИСПРАВЛЕНО (commit pending)

`from sonya.tools import hot_loader` теперь работает.

### M-18. SOUL.md содержит мёртвые ссылки на OpenClaw paths ✅ ИСПРАВЛЕНО (commit pending)

`memory_system/db/memory.db` → `~/.sonya/sonya_substrate.db`. "Update database" → "substrate is updated by the core".

### M-20. SOUL.md ссылается на несуществующие AGENTS.md, IDENTITY.md ✅ ИСПРАВЛЕНО (commit pending)

В Continuity section перечислены только существующие файлы: SOUL/HEARTBEAT/USER/SELF/LESSONS + INTERIM_CRUTCHES.

### M-21. PROJECT_DOCUMENTATION_MAP — два пункта 12 ✅ ИСПРАВЛЕНО (commit pending)

Reading order перенумерован 1-29.

### M-22. PROJECT_DOCUMENTATION_MAP не упоминает live docs ✅ ИСПРАВЛЕНО (commit pending)

Добавлены секции: KNOWN_ISSUES.md, operations/VPS.md, deploy/README.md, docs/план/, активные/архивные work docs.

### M-23. `docs/план/` — 4 файла без metadata ✅ ИСПРАВЛЕНО (commit pending)

`ОСНОВА.md` получил metadata header (Status: Legacy). `*.txt` — not markdown, оставлены как заметки.

### M-24. ROADMAP §14 обещает `working.py` — не реализован

Phase 8 закрыта, но `src/sonya/memory/working.py` отсутствует. Также нет `migration.py`.

### M-25. ROADMAP §14 обещает substrate v7 — реальность v6

Таблиц `working_memory`, `lessons`, `consolidation_jobs` нет. Phase 8 ✅ — формально, не фактически.

### M-26. ROADMAP §15 (Phase 9) — нет ни avatar.py, ни scheduler в `harness/hyper.py`, ни v8 substrate

Phase 9 ✅ — формально. Реальность: data-class stubs, нигде не инстанциируются.

### M-27. CHECKLIST §8 утверждает "OpenClaw context_loader" — неверно

Bridge handler не работает на VPS. main.py использует `build_full_context` напрямую.

### M-28. Drift review cadence — следующий до 2026-05-29

Не auto-tracked. Нужно вручную не забыть.

### M-29. SOUL.md без metadata header ✅ ИСПРАВЛЕНО (commit pending)

Header добавлен (Status, Type, Last reviewed, Scope).

### M-30. `tg-userbot` без тестов и README

В пакете только `client.py` и `tool.py`.

### M-31. ✅ УДАЛЕНО (см. 4.6)

### M-32. ✅ УДАЛЕНО (см. 4.6)

### M-33. `test_main_integration.py` второй тест — тавтология

Cancel task, await CancelledError, return 0. Не тестирует clean-shutdown семантику.

### M-34. Signal handler signature ✅ ИСПРАВЛЕНО (см. S-16)

### M-35. `record_response_as_memory` хардкодит `importance_score=0.5/0.6`

`consolidation.py` use `min_importance=0.7` — диалоги **никогда не промотятся** в semantic facts.

---

## 10. МЕЛКИЕ / ТЕХДОЛГ

### m-1. ✅ УДАЛЕНО (см. 4.5)

### m-2. ✅ УДАЛЕНО (см. 4.5)

### m-3. Hardcoded `~/Sonya` в admin server ✅ ИСПРАВЛЕНО (см. C-4)

### m-4. Конфликт deploy doc'ов

`deploy/README.md` описывает `/opt/sonya/`, а `VPS.md` и admin code — `~/Sonya`.

### m-5. `deploy/systemd/sonya.service` без User= / Group=

Запустится из-под root.

### m-6. `Lifecycle.request_stop` — wrong order

Emit stopping → append stopped → publish → set state STOPPED. Если что-то падает между append и assignment — состояние "STOPPING" вечно.

### m-7. `Lifecycle.wait_for_stop` без start — silent return

### m-8. Substrate `PRAGMA foreign_keys` ✅ ИСПРАВЛЕНО (commit pending)

`Substrate.open` теперь применяет `PRAGMA foreign_keys = ON` для каждого нового connection.

### m-9. EpisodicMemory `_row_to_event` ✅ ИСПРАВЛЕНО (см. S-14)

`json.loads` обёрнут в try/except — empty string или corrupt JSON → `()`.

### m-10. `self_inspect.list_own_modules` без allowlist

### m-11. SkillRegistry `register` делает 2 read query вместо INSERT OR IGNORE

### m-12. SkillCandidate.purpose — truncate inconsistent

### m-13. Mixed exception hierarchy

### m-14. Type hints inconsistency

### m-15. hot_loader не логирует failed plugin loads

### m-16. `simulation/world.py`, `embodiment/adapter.py`, `harness/hyper.py` — pure stubs

### m-17. `state/__init__.py` экспортирует `THINGS_NOT_TO_BETRAY_SEED` без причины

### m-18. ⚠️ `*.egg-info/` в git ✅ ИСПРАВЛЕНО (см. cleanup commit 5916e3d)

`tg_bridge.egg-info/` ушёл вместе с tg-bridge. Остальные не tracked.

### m-19. ⚠️ `admin/__main__.py` ✅ ИСПРАВЛЕНО (commit pending)

Обёрнут в `if __name__ == "__main__":`.

### m-20. `admin/__init__.py` пустой ✅ ИСПРАВЛЕНО (commit pending)

Экспортирует `create_app` и `main`.

### m-21. Agent session DONE парсер ловит `[DONE` без двоеточия

### m-22. `result.budget_exceeded` никем не читается

### m-23. `_TERMINAL_CHARS` в openrouter.py — emoji edge cases

### m-24. `WriteMaster.acquired_at` пишется но не читается

### m-25. Substrate без `PRAGMA journal_mode = WAL` ✅ ИСПРАВЛЕНО (commit pending)

`Substrate.open()` (writable) применяет `PRAGMA journal_mode = WAL`. Лучше concurrent reads (admin при работающем core).

---

## 11. MISSING / GAPS

### G-1. Нет тестов для admin/server.py

### G-2. Нет тестов для admin static.py (HTML/JS)

### G-3. Нет тестов для tg-userbot

### G-5. Нет regression теста для `verify=False` после фикса C-2

### G-6. PrincipalRegistry.resolve_from_channel_input не используется

main.py userbot path хардкодит `principal_id=str(msg_data.get("sender_id", ""))`. Соня нигде не резолвит Ивана как Principal.

### G-7. Нет валидации .env при старте

`int(os.environ.get("SONYA_TG_API_ID", "0"))` — bad value → ValueError без помощи.

### G-8. SQL injection vector в admin substrate handler

`f"SELECT COUNT(*) FROM [{name}]"` — name из sqlite_master safe сейчас, но fragile.

### G-9. Backup substrate через `cp` на hot DB — может быть corrupt

VPS.md рекомендует `cp` (не WAL mode). Нужно `sqlite3 .backup`.

### G-10. Нет audit при изменении personality docs

`context_builder` читает SOUL.md каждый раз, но нет audit trail когда промпт меняется.

### G-11. ConsolidationPipeline не имеет триггера

Никто не вызывает `run_consolidation()`. Semantic memory pipeline не работает.

### G-12. THINGS_NOT_TO_BETRAY_SEED seedится только на пустую identity

Если identity повредится — re-seed не срабатывает. Нет integrity check.

### G-13. Нет regression теста для FilesystemTool sandbox escape

S-12 — реальный риск, нужен тест на `..`/symlinks/forbidden zones.

### G-14. Test coverage gap

**Не покрыты:** admin, tg-userbot, tools (filesystem, self_inspect, hot_loader), context_builder, memory_wiring, agent_session, seed identity edge cases, `_create_thinking_provider`, planner с реальным provider, schema migrations v3→v6, embodiment, simulation, harness/hyper.

---

## 12. Приоритеты — что осталось

### 🔴 Заблокировано пользователем (пока не делать)

| # | Issue | Причина |
|---|-------|---------|
| C-1 | Секреты в git | По указанию пользователя — пропустить |
| C-2 | TLS verify=False | По указанию пользователя — пропустить |
| C-3 | Admin auth weakness | По указанию пользователя — пропустить |

### 🟡 Deferred (требуют integration sprint, не bug fix)

| # | Issue | Причина |
|---|-------|---------|
| S-3..S-7 | Dead code Phase 4-6 | Нужна интеграция self-mod/drift/skills/consolidation в runtime |
| S-15 | DriveCounters reset | Зависит от S-7 |
| 5.1 | Инициатива | Связка thinking_loop → userbot |
| 5.2 | Context compression для agent sessions | Архитектурный вопрос |
| 5.3 | Persistent conversation history | Нужна substrate v7 + chat_messages таблица |
| 5.4 | Night mode / timezone | UX-задача |
| 5.5 | Rate limiting per-chat | UX-задача |
| 5.6 | Health HTTP endpoint | Можно через admin |
| 4.1 | CHECKLIST дрифт | Документационный долг — переписать целиком |
| 4.3 | Дублирование drive counters | Ждёт S-7 |
| 4.4 | Phases 6/8/9 implementation plans | Документационный долг |

### 🟢 Текущее состояние ядра

Стабильно работает:
- ✅ Telegram userbot — полный handler (текст, стикеры, фото, голосовые, группы)
- ✅ Reply/respond logic
- ✅ Chat history + recent thoughts → unified context
- ✅ Thinking loop с full context (memory + recent telegram)
- ✅ Active session с initial_thought
- ✅ Filesystem sandbox (write only в plugins/ и workspace/)
- ✅ Layer 4 anchor protection через public API + programmatic keywords
- ✅ Admin panel с graceful core stop, read-only при работающем core
- ✅ Episodic memory decay/access tracking
- ✅ systemd unit-ы с правильными правами
- ✅ deploy/update.sh для безопасного pull
- ✅ WAL + foreign_keys pragmas

---

## 13. История исправлений

| Commit | Что сделано |
|--------|-------------|
| `4fb631d` | Telegram userbot — handler с логами, mark_read, typing, reply, проверка авторизации |
| `e6fac8c` | Chat history (12 сообщений), reply/respond logic, agent regex fix, budget intervals 30мин/2ч, log dedup |
| `8b01882` | Admin core management — start/stop/logs из браузера |
| `bd49834` | Admin core modes — full / telegram_only / thinking_only |
| `b32bac9` | KNOWN_ISSUES.md — полный реестр после аудита |
| `26391b1` | Удалён DailyBudget (излишество), SOUL.md — убрано упоминание Claude Sonnet 4.5 |
| `e996355` | systemd units (sonya.service, sonya-admin.service), deploy/update.sh |
| `7a87ae9` | HEARTBEAT.md rewrite, 2.4/2.5/2.7 closed |
| `6e6f305` | Media support, group chats, robust JSON parse, graceful TG shutdown |
| `5916e3d` | Удалены пакеты tg-bridge + sonya_runtime + OpenClaw scripts (-4500 строк) |
| `adc309d` | C-4 graceful core stop; C-5 admin read-only when core runs |
| `bd864d5` | C-6/7 anchor protection, S-12 filesystem sandbox, S-13 substrate read-only, S-14 episodic decay, S-11 tool error logging, S-16 graceful signals, S-8/9/10, M-5 |
| `6a7b51b` | §9 batch — env.example, default model, drives, lock_path, hot_loader export, SOUL/HEARTBEAT cleanup, doc map, WAL+FK pragmas, admin packaging |
| pending | 1.4 unified memory — thinking loop + telegram через один build_full_context, +recent thoughts/messages в context |
| `3eb4d46` | logging: переименован key `module` → `channel_module`/`target_module` в `_log.extra` (LogRecord reserved attr — крашил core при старте после селфмода каналов) |
| pending | Этап C — Task runtime: substrate v7 `tasks` table, `sonya/tasks/` (models/store/service), `tools/tasks_tool.py`, wired в agent_session + internal_loop, open tasks в `build_full_context` (+27 тестов, 329 passing) |
| pending | Thought truncation поднята: было 200/300/500 → 1500/4000/8000 chars (агент-степы перестали обрываться на полуслове); active interval 2h → 1.5h; idle 30 мин уже стояло |
| pending | Этап E — Tool ecosystem: `web.search`/`web.fetch` (DuckDuckGo HTML, aiohttp, 200KB cap), `code.exec` (subprocess sandbox, 30s timeout), `shell.run`/`pip.install` (approval-gated через ApprovalManager) (+16 тестов, 345 passing) |
| pending | Этап F — Consolidation + drift integration: `_scan_drift_and_gaps` каждый tick, gaps → pending_intentions, `_run_consolidation` после active session (1×/24h) |
| pending | Этап G — Drives integration: DriveCounters параллельно HomeostasisCounters, `tick`/`on_external_message`, drives передаются в `build_full_context` из обоих путей (thinking + telegram) |
