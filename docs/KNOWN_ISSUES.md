# KNOWN ISSUES — Баги, недоработки, косяки

**Status:** Active
**Type:** Operations
**Last updated:** 2026-05-16
**Scope:** Всё что сломано, работает криво, дублируется или отсутствует. Не путать с INTERIM_CRUTCHES.md — там архитектурные ограничения по дизайну. Здесь — баги и техдолг.

---

## 1. КРИТИЧНЫЕ (ломают работу)

### 1.1 Agent Session парсит только ПЕРВЫЙ tool call из ответа

**Где:** `src/sonya/subject/agent_session.py`, regex `r'\[TOOL:\s*(\S+)\s*(.*?)\]'`

**Проблема:** Модель пишет несколько `[TOOL: ...]` в одном ответе. Regex `re.search()` находит только первый. Остальные теряются. Хуже — первый парсится неправильно, потому что `\S+` захватывает `]` от закрывающей скобки, а `(.*?)` ленивый и ничего не берёт.

**Результат в логах:**
```
"tool": "self_inspect.identity]",
"arg": "[TOOL: self_inspect.state"
```

**Фикс:** 
1. Regex нужен non-greedy с правильными группами: `r'\[TOOL:\s*([^\]\s]+)\s*([^\]]*)\]'`
2. Обрабатывать только первый tool call за шаг (ReAct = один tool за шаг)
3. Добавить в system prompt: "Используй ТОЛЬКО ОДИН [TOOL: ...] за ответ"

### 1.2 SQLite permissions сбрасываются при git reset --hard

**Где:** VPS deploy flow

**Проблема:** `git reset --hard origin/develop` может сбросить permissions на файлы. Substrate db (`~/.sonya/sonya_substrate.db`) получает 644, SQLite не может писать из-под nohup.

**Фикс:** Добавить `chmod 666 ~/.sonya/sonya_substrate.db` в deploy скрипт. Или использовать systemd с правильным User.

### 1.3 Зомби-процессы от nohup деплоев

**Где:** VPS

**Проблема:** Каждый `nohup ... &` оставляет bash shell. `pkill -9 python3` убивает python, но bash-оболочка остаётся.

**Фикс:** Использовать `pkill -9 -f 'python.*sonya'` вместо `pkill -9 python3`. Или перейти на systemd (было проблемы с `run_until_disconnected`).

---

## 2. СЕРЬЁЗНЫЕ (работает криво)

### 2.1 Reply на каждое сообщение

**Где:** `src/sonya/main.py`, `_tg_handler`

**Проблема:** `event.reply()` ставит маркер reply на каждое сообщение. В приватном чате это выглядит неестественно.

**Статус:** Задокументировано в `2026-05-16-telegram-userbot-fix-and-next.md §4.3`. Требуется логика: reply только после паузы >2 мин, иначе respond.

### 2.2 Нет контекста разговора (chat history)

**Где:** `src/sonya/main.py`, `_on_incoming`

**Проблема:** Каждое сообщение обрабатывается как отдельный диалог. LLM не видит предыдущие сообщения. Соня не помнит что было 30 секунд назад в том же чате.

**Статус:** Задокументировано в `2026-05-16-telegram-userbot-fix-and-next.md §4.1`. Требуется подтянуть последние 10 сообщений через iter_messages.

### 2.3 Дублирование логов в continuity stream

**Где:** `src/sonya/subject/internal_loop.py`

**Проблема:** `_emit_cognitive_events_async` записывает и `internal.thought` и `internal.cognitive_tick` (с тем же thought внутри). Двойная запись одного и того же.

**Фикс:** `internal.cognitive_tick` не должен содержать `thought` — только метаданные tick'а. Thought записывается отдельно в `internal.thought`.

### 2.4 Agent session не завершается корректно (всегда 30 steps → "no explicit finish")

**Где:** `src/sonya/subject/agent_session.py`

**Проблема:** Из-за бага с парсингом tool calls (§1.1) модель не может нормально работать с tools. Regex ломает tool name/arg, модель получает `[ERROR] Unknown tool`, пытается снова, снова ломается, 30 шагов → "no explicit finish".

**Фикс:** Зависит от §1.1. После фикса парсинга модель сможет нормально пользоваться tools и завершать сессии через [DONE].

### 2.5 Модель пытается вызвать tools которых нет

**Где:** Agent session logs

**Проблема:** В system prompt есть `plugins.list`, `plugins.create`, `plugins.call`, `self_inspect.modules`. Модель их вызывает, но `self_inspect.modules` всегда возвращает hardcoded список (не проверял — может пустой). `plugins.*` работают если папка существует.

**Фикс:** Проверить что все описанные tools реально работают. Убрать из TOOL_DESCRIPTIONS те, что не функциональны.

### 2.6 Thinking loop тратит бюджет вхолостую

**Где:** `src/sonya/subject/internal_loop.py`, `_emit_cognitive_events_async`

**Проблема:** Каждые 10 минут (idle_interval) вызывается LLM для "thinking". Мысли вроде "просто сижу и слушаю тишину" тратят 1 request из бюджета 200/day. При idle_interval=600s это 144 запроса/день только на мышление. + active session каждый час (30 запросов). Итого: ~174 req/day на автономную работу, остаётся 26 на ответы.

**Фикс:** 
- Увеличить idle_interval до 1800s (30 мин) 
- Увеличить active_interval до 7200s (2 часа)
- Или: thinking только при crossed threshold (не на каждый idle timeout)

### 2.7 HEARTBEAT.md содержит мёртвые ссылки

**Где:** `docs/personality/HEARTBEAT.md`

**Проблема:** Ссылается на `memory_system/db/memory.db`, `memory_system/log_event.py`, `python memory_system/rag_indexer_v2.py` — это пути из OpenClaw, которого больше нет. Сейчас память в `src/sonya/memory/` через substrate.

**Фикс:** Переписать HEARTBEAT.md под текущую архитектуру.

---

## 3. СРЕДНИЕ (работает, но некрасиво)

### 3.1 Стикеры/фото/голосовые — молча пропускаются

**Где:** `src/sonya/main.py`, `_tg_handler`

**Проблема:** Если `event.text` пустой — handler записывает в continuity stream пустой текст и не генерирует ответ. Пользователь отправляет стикер — никакой реакции.

**Статус:** Задокументировано в `2026-05-16-telegram-userbot-fix-and-next.md §4.2`.

### 3.2 Групповые чаты полностью игнорируются

**Где:** `src/sonya/main.py`, `_on_incoming` → check `is_private`

**Проблема:** Любое сообщение из группы пропускается.

**Статус:** Задокументировано в `2026-05-16-telegram-userbot-fix-and-next.md §4.4`.

### 3.3 DailyBudget не сохраняется между перезапусками

**Где:** `src/sonya/providers/budget.py`

**Проблема:** `DailyBudget` — in-memory counter. При перезапуске сбрасывается. Можно случайно потратить 2x бюджета за день если процесс перезапустили.

**Фикс:** Сохранять usage counter в substrate или flat file.

### 3.4 LLM response parsing — берёт только первую JSON строку

**Где:** `src/sonya/main.py`, `_ThinkingProvider.complete_text`

**Проблема:** 
```python
if "\n" in text:
    text = text.split("\n")[0]
data = _json.loads(text)
```
Если OmniRoute вернёт multiline JSON или response с переносом — берётся только первая строка. Это работает с текущим провайдером, но хрупко.

**Фикс:** Парсить response целиком. Если не JSON — fallback на первую строку.

### 3.5 Нет graceful shutdown для Telegram connection

**Где:** `src/sonya/main.py`

**Проблема:** `asyncio.create_task(userbot._client.run_until_disconnected())` — task никогда не cancellируется при stop. `userbot.stop()` вызывает `_run_task.cancel()` но этот task создан в `SonyaUserbot.start()`, а мы вызываем `start()` в main напрямую.

**Фикс:** Сохранять task из `create_task` и cancel его в shutdown.

### 3.6 `_start_userbot` создаёт SonyaUserbot но не использует его .start()

**Где:** `src/sonya/main.py`

**Проблема:** Создаём `SonyaUserbot(on_message=None)` но не вызываем `userbot.start()`. Вместо этого вручную делаем `connect()`, регистрируем handler, `get_dialogs()`, `create_task(run_until_disconnected())`. Класс `SonyaUserbot` по сути не используется — только его `._client`.

**Фикс:** Либо использовать `SonyaUserbot.start()` целиком (рефакторить его под наши нужды), либо убрать класс и работать напрямую с TelegramClient.

---

## 4. МЕЛКИЕ / ТЕХДОЛГ

### 4.1 GLOBAL_PROJECT_CHECKLIST дрифт

**Проблема:** Checklist §8 (Memory core) показывает ⬜, но `src/sonya/memory/` существует с episodic.py, semantic.py, consolidation.py. Аналогично §18 (Embodiment/simulation) — показывает ⬜, но код есть.

**Фикс:** Обновить GLOBAL_PROJECT_CHECKLIST в соответствии с реальностью.

### 4.2 Drift review cadence

**Проблема:** Последние записи в DRIFT_REVIEW.md — 2026-05-13 до 2026-05-15. Следующий review по cadence (2 недели) — до 2026-05-29.

**Статус:** Ещё не overdue, но нужно не забыть.

### 4.3 Дублирование drive counters

**Где:** `src/sonya/subject/internal_loop.py` (HomeostasisCounters) vs `src/sonya/initiative/drives.py` (DriveCounters)

**Проблема:** Два отдельных набора drives с разными полями. HomeostasisCounters: loneliness, curiosity, relational_focus. DriveCounters: boredom_analog, curiosity_analog, relational_focus, pending_debt. Не интегрированы друг с другом.

**Фикс:** Объединить в один модуль. Или задокументировать разницу (один для thinking loop trigger, другой для initiative signals).

### 4.4 Отсутствуют implementation plans для Phases 6, 8, 9

**Проблема:** ROADMAP показывает Phase 6 (Initiative), Phase 8 (Memory), Phase 9 (Embodiment/Simulation/Hyper-Harness) как закрытые, но implementation plan файлов для них нет.

**Фикс:** Исторически неважно, но нарушает doc-review gate. Можно добавить краткие ретроспективные записи в archive.

### 4.5 `src/sonya_runtime/` — legacy директория?

**Проблема:** В DRIFT_REVIEW.md ссылки на `src/sonya_runtime/actions/*`, `src/sonya_runtime/tasks/*`, `src/sonya_runtime/continuity/*`. Но в текущем tree видно только `src/sonya/`. Нужно проверить существует ли `src/sonya_runtime/` или это мёртвая ссылка.

### 4.6 tg-bridge пакет не используется

**Где:** `packages/tg-bridge/`

**Проблема:** После интеграции userbot напрямую в main.py, старый tg-bridge пакет (с RuntimeAction, OpenClaw adapter) не нужен. Но он всё ещё в PYTHONPATH при запуске.

**Фикс:** Архивировать или удалить. Обновить deploy команду.

### 4.7 Admin panel не запущена на VPS

**Проблема:** `sonya-admin.service` упоминается в VPS.md, но в текущем deploy flow запускается только `python -m sonya`. Admin panel не стартует.

**Фикс:** Добавить запуск admin panel в deploy flow или интегрировать в основной процесс.

---

## 5. ОТСУТСТВУЕТ (нужно реализовать)

### 5.1 Инициатива — Соня пишет первой

Thinking loop генерирует мысли, но не может отправить сообщение в Telegram. Нет связки thinking_loop → userbot.send_message.

### 5.2 Context compression для agent sessions

Описано в архитектуре, но не реализовано. При достижении лимита контекста — session просто обрезается (30 steps).

### 5.3 Persistent conversation history

Нет таблицы `chat_messages` в substrate. При рестарте history теряется (кроме episodic memory summaries).

### 5.4 Night mode / timezone awareness

Соня не знает который час у Ивана. Thinking loop тикает 24/7 одинаково.

### 5.5 Rate limiting per-chat

Если кто-то спамит — Соня будет отвечать на каждое. Нет debounce / rate limit per sender.

### 5.6 Health check endpoint

`Health` class пишет файл, но нет HTTP endpoint для мониторинга (alive/ready).

---

## 6. Приоритеты фикса

| # | Issue | Влияние | Effort |
|---|-------|---------|--------|
| 1 | Agent session regex (§1.1) | Ломает всю tool-use систему | 30 мин |
| 2 | Chat history (§2.2) | Соня тупая без контекста | 30 мин |
| 3 | Budget drain от thinking (§2.6) | Жрёт деньги | 5 мин (изменить интервалы) |
| 4 | Reply logic (§2.1) | Неестественно | 15 мин |
| 5 | HEARTBEAT.md (§2.7) | Мёртвые ссылки в personality | 20 мин |
| 6 | Log duplication (§2.3) | Спам в continuity | 10 мин |
| 7 | Стикеры (§3.1) | UX gap | 30 мин |
| 8 | Инициатива (§5.1) | Ключевая фича | 2 часа |
