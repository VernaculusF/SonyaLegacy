# KNOWN ISSUES — Баги, недоработки, косяки

**Status:** Active
**Type:** Operations
**Last updated:** 2026-05-16
**Stable commit:** `26391b1`
**Scope:** Всё что сломано, работает криво, дублируется или отсутствует. Не путать с INTERIM_CRUTCHES.md — там архитектурные ограничения по дизайну. Здесь — баги и техдолг.

---

## 1. КРИТИЧНЫЕ (ломают работу)

### 1.2 SQLite permissions сбрасываются при git reset --hard

**Где:** VPS deploy flow

**Проблема:** `chmod 666` на substrate db нужен после каждого reset.

**Фикс:** Сейчас обходим вручную в deploy команде. Правильно — systemd User или setup-script.

### 1.3 Зомби-процессы от nohup деплоев

**Статус:** Workaround — `pkill -9 -f 'python.*sonya'` вместо `pkill -9 python3`. Идеально — systemd.

---

## 2. СЕРЬЁЗНЫЕ (работает криво)

### 2.4 Agent session не завершается корректно

**Статус:** Должно работать после фикса regex (1.1), но не проверено в продакшене.

### 2.5 Модель пытается вызвать tools которых нет

**Где:** Agent session logs

**Проблема:** В system prompt есть `plugins.list`, `plugins.create`, `plugins.call`, `self_inspect.modules`. Модель их вызывает, но `self_inspect.modules` всегда возвращает hardcoded список. `plugins.*` работают только если папка существует.

**Фикс:** Проверить что все описанные tools реально работают. Убрать из TOOL_DESCRIPTIONS те, что не функциональны.

### 2.7 HEARTBEAT.md содержит мёртвые ссылки

**Где:** `docs/personality/HEARTBEAT.md`

**Проблема:** Ссылается на `memory_system/db/memory.db`, `memory_system/log_event.py`, `python memory_system/rag_indexer_v2.py` — это пути из OpenClaw, которого больше нет. Сейчас память в `src/sonya/memory/` через substrate.

**Фикс:** Переписать HEARTBEAT.md под текущую архитектуру.

---

## 3. СРЕДНИЕ (работает, но некрасиво)

### 3.1 Стикеры/фото/голосовые — молча пропускаются

### 3.2 Групповые чаты полностью игнорируются

### 3.4 LLM response parsing — берёт только первую JSON строку

**Статус:** Это в **трёх** местах: `main.py:75`, `admin/server.py:170`, и старый `OpenRouterProvider`. См. S-1.

### 3.5 Нет graceful shutdown для Telegram connection

### 3.6 `_start_userbot` создаёт SonyaUserbot но не использует его .start()

---

## 4. МЕЛКИЕ / ТЕХДОЛГ

### 4.1 GLOBAL_PROJECT_CHECKLIST дрифт

### 4.2 Drift review cadence — следующий до 2026-05-29

### 4.3 Дублирование drive counters

`HomeostasisCounters` (loneliness, curiosity, relational_focus) в `internal_loop.py` vs `DriveCounters` (boredom_analog, curiosity_analog, relational_focus, pending_debt) в `initiative/drives.py`. Не интегрированы.

### 4.4 Отсутствуют implementation plans для Phases 6, 8, 9

### 4.5 `src/sonya_runtime/` — legacy директория

См. m-1, m-2.

### 4.6 tg-bridge пакет не используется

См. M-31, M-32.

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

### C-1. Реальные секреты закоммичены в git

**Где:** `.env` (tracked), `tg.session` (tracked), `docs/operations/VPS.md` (открытым текстом).

**Что внутри:** `SONYA_OPENROUTER_API_KEY`, `SONYA_TG_API_HASH`, `SONYA_TG_API_ID`, `SONYA_ADMIN_PASSWORD=1990`, plus session файл с правами доступа к Telegram аккаунту Сони.

**Почему критично:** Даже приватный репо — если кто-то получит доступ или ты случайно сделаешь публичным, всё уйдёт. `.gitignore` НЕ содержит `.env`.

**Фикс:**
1. `git rm --cached .env tg.session`
2. Добавить `.env`, `tg.session*` в `.gitignore`
3. Ротировать **все** ключи (openrouter, telegram, admin password)
4. Удалить секреты из VPS.md, заменить на placeholders

### C-2. `httpx.AsyncClient(verify=False)` глобально

**Где:** `src/sonya/main.py:66`, `src/sonya/admin/server.py:163`.

**Проблема:** TLS verification выключен безусловно. Сейчас работает потому что OmniRoute локальный, но если когда-нибудь `SONYA_LLM_API_BASE` будет публичным — MITM-уязвимо.

**Фикс:** Сделать env-флаг `SONYA_LLM_INSECURE=1`, по умолчанию `verify=True`.

### C-3. Admin panel — 0.0.0.0:8877, no HTTPS, password=1990, cookie=password

**Где:** `src/sonya/admin/server.py:354`, GCP firewall `allow-sonya-admin: 0.0.0.0/0`.

**Проблемы:**
1. Биндится на все интерфейсы → доступ из интернета
2. Пароль `1990` (4-значное число)
3. Cookie value буквально равен паролю (`set_cookie("sonya_auth", pwd)`) — единственная утечка даёт 30 дней доступа
4. Нет HTTPS — всё в plaintext

**Фикс:**
- Bind на `127.0.0.1`, доступ через SSH-туннель (`ssh -L 8877:localhost:8877`)
- Или: hashed password + signed token + Caddy/nginx с Let's Encrypt
- Сменить пароль на нормальный

### C-4. Admin "stop core" использует SIGKILL без graceful shutdown

**Где:** `src/sonya/admin/server.py:312` (`api_core_stop`)

**Проблемы:**
1. SIGKILL → нет graceful shutdown, `lifecycle.stopped` не пишется в substrate, write-master lock может остаться
2. Hardcoded paths (`~/Sonya`, `~/Sonya/.venv/bin/python`) — admin неюзабельна вне VPS
3. `open("/tmp/sonya.log", "w")` без `with` — file handle leak при каждом старте

**Фикс:**
1. Сначала SIGTERM, ждать 5 сек, потом SIGKILL
2. Paths из config (env vars)
3. `with open(...)` или закрывать file handle

### C-5. Admin открывает substrate параллельно с main процессом

**Где:** Все `api_*` хендлеры в `admin/server.py`

**Проблема:** Admin открывает второй `Substrate.open()` пока main держит write-master. SQLite работает в shared-mode, но WriteMaster guarantee из `SUBSTRATE_STANCE` нарушается. `api_chat_send` реально пишет (`record_response_as_memory`) — гонка двух писателей.

**Фикс:** Либо admin переходит на read-only mode когда main работает, либо общая connection через IPC.

### C-6. Layer 4 anchor protection обходит ApprovalManager API

**Где:** `src/sonya/selfmod/governed_change.py:51`

**Проблема:** `GovernedChangeProtocol.check_governed_approval` лезет напрямую в `proposals._sub.connection` минуя API ApprovalManager. Если поменяется схема таблицы `approval_requests` — Layer 4 (защита identity) silently сломается.

**Фикс:** Использовать публичный API `approval_manager.list_decided()` или добавить метод `list_by_action_pattern()`.

### C-7. THINGS_NOT_TO_BETRAY проверка хрупкая

**Где:** `selfmod/layers/anchor_integrity.py`

**Проблема:** Проверяет substring `relation_anchor_binding`, но seed value — `relation_anchor_binding_to_ivan_via_principal_id`. Сейчас работает по совпадению, но если seed изменится — Layer 4 рухнет молча.

**Фикс:** Использовать `THINGS_NOT_TO_BETRAY_SEED` константу программно.

---

## 8. СЕРЬЁЗНЫЕ (broken integration / dead code)

### S-1. JSON parsing бага в **трёх** местах

`main.py:75-79`, `admin/server.py:170-176`, и `OpenRouterProvider` (хотя он dead code, см. S-3). Везде `text.split("\n")[0]` — берётся только первая строка.

### S-2. `_ThinkingProvider` игнорирует kwargs

**Где:** `main.py:54`. Подпись `complete_text(self, messages, **kwargs)` но kwargs молча игнорируются — hardcoded `max_tokens=1500, temperature=0.9`.

### S-3. `OpenRouterProvider` — dead code

**Где:** `src/sonya/providers/openrouter.py` (~250 строк)

**Проблема:** Полноценный provider с retry/continuation/overlap detection из tg-bridge. **Никогда не вызывается**. Production использует ad-hoc `httpx.AsyncClient`. Все защитные механизмы провайдера неактивны.

**Фикс:** Либо подключить в `_create_thinking_provider`, либо удалить.

### S-4. `AccountPool` — dead code

**Где:** `src/sonya/providers/pool.py`

**Проблема:** Описано в CRUTCH-009 ("provider rotation"), есть тесты, но **никем не импортируется**. Используется один глобальный API key. CRUTCH-009 фактически не реализован.

### S-5. `ProviderRegistry` — dead code

Same story. Экспортируется, тестируется, не используется.

### S-6. Self-modification pipeline не подключён в runtime

**Где:** `src/sonya/selfmod/`

**Проблема:** `Pipeline`, `WatchWindow`, `GovernedChangeProtocol` нигде не инстанциируются в `main.py`. 4-слойный pipeline полностью реализован и тестирован, но в живой Соне **недостижим**. ROADMAP §4 говорит "Phase 4 ✅ закрыта" — это formal-only.

### S-7. Куча dead код в runtime

**Никогда не вызываются вне тестов:**
- `DriveCounters` (передаётся в context_builder с `drives=None` всегда)
- `DriftDetector.scan_recent` → "anchor drift triggers auto-revert" не реализовано
- `GapDetector.scan_recent` → capability gap detection не работает
- `ConsolidationPipeline.run_consolidation` → semantic memory никогда не консолидируется
- `SkillRegistry` → ни один skill никогда не активен

ROADMAP помечает Phases 4-6 ✅ closed, но реально код только существует — нет вызовов.

### S-8. `internal_loop.py` лезет в `_stream._sub` (private)

**Где:** `internal_loop.py:290`

**Проблема:** `substrate = self._stream._sub` — приватный атрибут. Дырявая абстракция.

**Фикс:** Передавать substrate явно в `InternalProcess.__init__`.

### S-9. `_emit_cognitive_events` (sync version) — dead code

В `internal_loop.py` есть и sync и async версия. Используется только async. Sync — мёртвая ветка.

### S-10. `agent_session.run_agent_session(initial_thought=...)` — параметр не передаётся

`_run_active_session` не передаёт `initial_thought`. `result.budget_exceeded` устанавливается, но никогда не читается.

### S-11. `agent_session._execute_tool` глотает все exceptions

**Проблема:** `filesystem.write` и `plugins.create` пишут на диск. Bare `except Exception` возвращает `[ERROR]`-строку — но не пишет в continuity stream и не логирует. Сломанный `plugins.create` от Сони не оставляет следа.

**Фикс:** Логировать ошибку tool execution в stream + log.

### S-12. ⚠️ FilesystemTool без allowlist — может записать `.env`, `.git/*`, schema.sql

**Где:** `tools/filesystem.py:13`

**Проблема:** `_allowed = [project_root]`. Соня через `agent_session` может вызвать `[TOOL: filesystem.write .env "..."]` — и это сработает. Также `plugins.create` пишет произвольный Python код в `tools/plugins/` без Layer 4 anchor check.

Это **path к самопереписыванию без governance**. Противоречит SUBSTRATE_STANCE §9.

**Фикс:**
1. Allowlist под-путей (`tools/plugins/`, `workspace/`)
2. Forbidden zones (`.env`, `.git/*`, `docs/personality/SOUL.md`, schema.sql, `tg.session`)
3. `plugins.create` должен идти через self-modification pipeline (Layer 1-4)

### S-13. Read-only mode substrate — потенциальная ошибка

`Substrate.open(read_only=True)` пропускает миграцию, но `READABLE_VERSIONS = {1..6}`. Открытие v1 db в read-only пройдёт, потом краш на отсутствующих таблицах.

### S-14. Episodic memory — retention/decay не работает

**Где:** `src/sonya/memory/episodic.py`

**Проблема:** Колонки `emotion_tags`, `retention_strength`, `archived` пишутся, но никогда не читаются логикой decay. `mark_accessed` существует, но **нигде не вызывается** → `access_count`/`retention_strength` не растут. Кривая забывания Эббингауза, описанная в MEMORY_AND_IDENTITY_PLAN §12, структурно отсутствует.

### S-15. `notify_external_event` сбрасывает только `loneliness`

**Где:** `internal_loop.py:180-184`

**Проблема:** При входящем сообщении сбрасывается `HomeostasisCounters.loneliness`, но `DriveCounters.relational_focus` (другой класс) — не сбрасывается. Соня "соскучилась" вечно растёт даже когда активно общается.

### S-16. Signal handlers молча проглатывают ошибки

`main.py:299-308`. `except (ValueError, OSError): pass` — если установка signal handler падает, Ctrl+C не работает graceful, узнаешь только в проде.

---

## 9. СРЕДНИЕ

### M-1. `.env.example` неполный

Не задокументированы: `SONYA_TG_API_ID`, `SONYA_TG_API_HASH`, `SONYA_TG_SESSION_PATH`, `SONYA_ENABLE_TELEGRAM`, `SONYA_ENABLE_THINKING`, `SONYA_ADMIN_PASSWORD`. Новый разработчик скопирует .env.example → .env → получит полусломанную систему.

### M-2. Default model в config.py — `google/gemma-4-27b-it:free` — НЕ СУЩЕСТВУЕТ

**Где:** `config.py:25`, `.env.example`

**Проблема:** Gemma 4 не существует. На OpenRouter free tier — `gemma-2-27b-it:free`. Первый запуск с дефолтами → 404.

**Фикс:** `gemma-2-27b-it:free` или указать конкретную доступную модель.

### M-3. `DriveCounters.pending_debt_rate` — мёртвое поле

`drives.py:25`: поле `0.0`, но `tick()` использует hardcoded `0.02 * N`. Поле никем не читается.

### M-4. `ProposalStatus` — 11 значений, используется 5

Часть enum используется только в dead-code (WatchWindow, governed_change).

### M-5. Тройная запись `intention_overdue`

`_emit_cognitive_events_async` пишет: (a) `internal.cognitive_tick` с `triggers=[deadline_overdue:X]`, (b) отдельный `internal.intention_overdue` event для каждого id. Тот же факт x2.

### M-6. Pipeline Layer 4 — комментарий не соответствует поведению

Комментарий "Layer 4 failure = requires governed change, not outright rejection" верен только если Layers 1-3 прошли. Не задокументировано.

### M-7. AnchorDriftSignal никогда не сохраняется и не триггерит действий

**Где:** `anchor/drift_signals.py:54`

**Проблема:** `DriftDetector.scan_recent` создаёт signals и возвращает list. Никто не сохраняет, никто не реагирует. Layer 4 защита от дрейфа — paper-only.

### M-8. Migrations переисполняют schema.sql на каждом шаге

`migrations.py:33-72`: каждый migration step запускает полный `schema.sql`. Работает из-за `IF NOT EXISTS`, но wasteful.

### M-9. `WriteMaster.lock_path` ломается на dotless paths

`path.with_suffix(suffix + ".lock")` падает с ValueError если path без расширения.

**Фикс:** `Path(str(path) + ".lock")`.

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

### M-15. Unused imports в `governed_change.py`

`ApprovalRequest`, `ApprovalStatus` импортированы, не используются.

### M-16. `SelfModificationProposal` — frozen dataclass, но `update_status` возвращает новый объект

Caller's old reference stale. API gotcha, надо документировать.

### M-17. `tools/__init__.py` не экспортирует `hot_loader`

Plugin system скрыт от `sonya.tools` namespace.

### M-18. SOUL.md содержит мёртвые ссылки на OpenClaw paths

**Где:** `docs/personality/SOUL.md:106`

`memory_system/db/memory.db` — путь из OpenClaw, не существует. Аналогично HEARTBEAT.md (§2.7).

### M-20. SOUL.md ссылается на несуществующие AGENTS.md, IDENTITY.md

В personality/ только SOUL.md, USER.md, SELF.md, LESSONS.md, HEARTBEAT.md.

### M-21. PROJECT_DOCUMENTATION_MAP — два пункта 12

ROADMAP и GLOBAL_PROJECT_CHECKLIST оба под номером 12.

### M-22. PROJECT_DOCUMENTATION_MAP не упоминает KNOWN_ISSUES.md, VPS.md, deploy/, план/

Карта не покрывает половину живых документов.

### M-23. `docs/план/` — 4 файла без metadata

`модель.txt`, `тело.txt`, `эмоции.txt`, `ОСНОВА.md` — нет Status/Type/Last reviewed.

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

### M-29. SOUL.md без metadata header

Нет Status/Type/Last reviewed.

### M-30. `tg-userbot` без тестов и README

В пакете только `client.py` и `tool.py`.

### M-31. tg-bridge тесты импортируют `sonya_runtime.*`

Если убрать sonya_runtime — 14 тестов разваливаются.

### M-32. tg-bridge/README.md описывает active OpenClaw role

Уже неактуально. tg-bridge не используется.

### M-33. `test_main_integration.py` второй тест — тавтология

Cancel task, await CancelledError, return 0. Не тестирует clean-shutdown семантику.

### M-34. Signal handler signature inconsistency

POSIX vs Windows path по-разному вызывают handler. Сейчас работает по совпадению.

### M-35. `record_response_as_memory` хардкодит `importance_score=0.5/0.6`

`consolidation.py` use `min_importance=0.7` — диалоги **никогда не промотятся** в semantic facts.

---

## 10. МЕЛКИЕ / ТЕХДОЛГ

### m-1. Dead file: `src/sonya_runtime/continuity/canonical_response.py`

Дубликат `src/sonya/state/canonical_response.py`. Не импортируется.

### m-2. Dead file: `src/sonya_runtime/continuity/events.py`

Тот же класс что в `src/sonya/state/`. Не импортируется.

### m-3. Hardcoded `~/Sonya` в admin server

`admin/server.py:278, 290`. Не работает на любом другом layout.

### m-4. Конфликт deploy doc'ов

`deploy/README.md` описывает `/opt/sonya/`, а `VPS.md` и admin code — `~/Sonya`.

### m-5. `deploy/systemd/sonya.service` без User= / Group=

Запустится из-под root.

### m-6. `Lifecycle.request_stop` — wrong order

Emit stopping → append stopped → publish → set state STOPPED. Если что-то падает между append и assignment — состояние "STOPPING" вечно.

### m-7. `Lifecycle.wait_for_stop` без start — silent return

### m-8. Substrate не включает `PRAGMA foreign_keys = ON` per-connection

Pragma в schema.sql не применяется к каждому новому connection.

### m-9. EpisodicMemory `_row_to_event` хрупко на пустом emotion_tags_json

`json.loads(row[8] or "[]")` — если empty string вместо NULL, упадёт.

### m-10. `self_inspect.list_own_modules` без allowlist

### m-11. SkillRegistry `register` делает 2 read query вместо INSERT OR IGNORE

### m-12. SkillCandidate.purpose — truncate inconsistent

### m-13. Mixed exception hierarchy

### m-14. Type hints inconsistency

### m-15. hot_loader не логирует failed plugin loads

### m-16. `simulation/world.py`, `embodiment/adapter.py`, `harness/hyper.py` — pure stubs

### m-17. `state/__init__.py` экспортирует `THINGS_NOT_TO_BETRAY_SEED` без причины

### m-18. ⚠️ `*.egg-info/` в git

`src/sonya_workspace.egg-info/`, `packages/tg-bridge/src/tg_bridge.egg-info/`, `packages/tg-userbot/src/tg_userbot.egg-info/`.

**Фикс:** `git rm -r --cached <paths>`.

### m-19. ⚠️ `admin/__main__.py` запускает `main()` на import

Должно быть в `if __name__ == "__main__":`.

### m-20. `admin/__init__.py` пустой

`from sonya.admin import create_app` не работает.

### m-21. Agent session DONE парсер ловит `[DONE` без двоеточия

### m-22. `result.budget_exceeded` никем не читается

### m-23. `_TERMINAL_CHARS` в openrouter.py — emoji edge cases

### m-24. `WriteMaster.acquired_at` пишется но не читается

### m-25. Substrate без `PRAGMA journal_mode = WAL`

WAL лучше для concurrent reads (admin + main одновременно).

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

## 12. Приоритеты

### 🔴 КРИТИЧНО

| # | Issue | Влияние | Effort |
|---|-------|---------|--------|
| 1 | C-1: секреты в git | Утечка ключей | 30 мин |
| 2 | C-3: admin auth weakness | Внешний взлом | 30 мин |
| 3 | S-12: filesystem без allowlist | Соня может сломать себя | 1 час |
| 4 | M-2: gemma-4 не существует | First-run 404 | 5 мин |
| 5 | M-18: SOUL.md OpenClaw paths | Personality drift | 10 мин |

### 🟡 СЕРЬЁЗНО

| # | Issue | Влияние | Effort |
|---|-------|---------|--------|
| 6 | S-3..S-7: dead code in critical paths | Phases 4-6 не работают | 4-8 часов |
| 7 | 2.7 / M-18: HEARTBEAT/SOUL drift | Personality lies | 30 мин |
| 8 | C-5: admin substrate concurrent | Race conditions | 1 час |
| 9 | S-14: episodic memory decay не работает | Memory growth uncontrolled | 1 час |
| 10 | 5.1: инициатива | Ключевая фича AGI | 2-3 часа |

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
