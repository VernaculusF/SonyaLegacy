# Telegram Userbot — Постмортем и план улучшений

**Status:** Active
**Type:** Work Doc
**Last updated:** 2026-05-16
**Stable commit:** `4fb631d`
**Code pointers:** [src/sonya/main.py](../../src/sonya/main.py), [packages/tg-userbot/src/tg_userbot/client.py](../../packages/tg-userbot/src/tg_userbot/client.py)

---

## 1. Что было сломано

Userbot запускался, логи показывали `userbot_running`, но handler никогда не срабатывал — сообщения не обрабатывались, ответов не было, mark_read не работал.

### Корневые причины

| # | Проблема | Симптом |
|---|----------|---------|
| 1 | `client.start()` вместо `connect()` + `is_user_authorized()` | На headless сервере `start()` может зависнуть (пытается спросить телефон интерактивно) или молча не авторизоваться |
| 2 | Нет try/except в handler | Любая ошибка (sqlite readonly, network drop) молча проглатывалась Telethon'ом — ничего в логах |
| 3 | SQLite readonly на substrate DB | `chmod` после `git reset --hard` сбрасывал permissions; handler падал на `ContinuityStream.append()` |
| 4 | Зомби-процессы от nohup деплоев | Несколько bash-оболочек висели мёртвыми, настоящий python3 процесс давно убит |
| 5 | `event.respond()` вместо `event.reply()` | Не критично для работы, но сообщения отправлялись без маркера reply |

### Хронология дебага

1. Лог показывал только 2 строки (startup) → handler не вызывается
2. `ps aux` — нет живого python3 процесса с sonya, только зомби bash shells
3. `curl http://127.0.0.1:20128/v1/models` без auth → "Authentication required" (ложная тревога — ключ передаётся через header, это ок)
4. После перезапуска — `sqlite3.OperationalError: attempt to write a readonly database`
5. `chmod 666` на substrate.db → исправлено
6. Чистый перезапуск с новым кодом → работает

---

## 2. Что пофиксили

### 2.1 Правильный connect flow

```python
# БЫЛО (ломалось на headless):
await userbot._client.start()

# СТАЛО:
await userbot._client.connect()
if not await userbot._client.is_user_authorized():
    _log.error("tg_not_authorized")
    return None
```

### 2.2 Полное логирование

Каждый этап handler'а теперь пишет в лог:
- `tg_incoming` — входящее сообщение (chat_id, sender_id, text preview, is_private)
- `tg_skip` — причина пропуска (не private, пустой text)
- `tg_no_provider` — LLM provider не настроен
- `tg_response_generated` — ответ сгенерирован (длина, preview)
- `tg_handler_crash` — exception в handler (с traceback)
- `userbot_response_error` — exception в planner (с traceback)

### 2.3 Robust handler

```python
@userbot._client.on(_tg_events.NewMessage(incoming=True))
async def _tg_handler(event):
    try:
        await event.mark_read()
        # ... обработка ...
    except Exception as e:
        _log.error("tg_handler_crash", extra={"error": str(e)})
        import traceback
        _log.error("tg_handler_traceback", extra={"tb": traceback.format_exc()})
```

### 2.4 reply() вместо respond()

```python
# БЫЛО:
await event.respond(response)

# СТАЛО:
await event.reply(response)
```

### 2.5 Typing indicator

```python
if event.is_private and event.text:
    async with userbot._client.action(event.chat_id, 'typing'):
        response = await _on_incoming(msg_data)
    if response:
        await event.reply(response)
```

---

## 3. Текущее рабочее состояние

| Функция | Статус |
|---------|--------|
| Приём сообщений | ✓ работает |
| mark_read | ✓ |
| Typing indicator | ✓ |
| Reply маркер | ✓ |
| Ответ через LLM (minimax-m2p7) | ✓ |
| Логирование | ✓ полное |
| Personality context (SOUL.md + USER.md) | ✓ загружается |
| Memory injection (episodic + semantic) | ✓ |
| Budget cap (200 req/day) | ✓ |

---

## 4. Что надо улучшать

Приоритеты расставлены по влиянию на качество общения. **Менять текущий handler только аддитивно** — текущая базовая система ответов стабильна и не трогается.

### 4.1 Контекст разговора (chat history)

**Проблема:** Сейчас каждое сообщение обрабатывается как отдельный диалог. Нет истории переписки.

**Решение:** Перед вызовом LLM подтягивать последние N сообщений из этого чата (через `client.iter_messages`) и класть в `session_messages`. Personality prompt остаётся в system, история чата — в user/assistant чередовании.

**Ограничения:** Не раздувать context window. Лимит — 10-15 последних сообщений или ~3000 токенов.

**Реализация:**
```python
# В _on_incoming, перед build_full_context:
recent = await userbot._client.iter_messages(msg_data["chat_id"], limit=10)
session_messages = []
for m in reversed(recent):
    role = "assistant" if m.sender_id == my_id else "user"
    if m.text:
        session_messages.append({"role": role, "content": m.text})

ctx = build_full_context(substrate=substrate, user_input=text, session_messages=session_messages, ...)
```

### 4.2 Стикеры и медиа

**Проблема:** Если сообщение — стикер, фото, голосовое — text пустой, handler пропускает.

**Решение:** Распознавать тип контента и формировать текстовое описание:
- Стикер → `"[стикер: {emoji}]"`
- Фото → `"[фото]"` (или с caption)
- Голосовое → `"[голосовое сообщение]"` (позже — speech-to-text)
- Видео → `"[видео]"` (или с caption)

**Важно:** Не отвечать на каждый стикер. Стикеры чаще всего реакция, не вопрос. Можно: записывать в continuity stream, но не генерировать ответ. Или отвечать только если контекст подразумевает диалог.

### 4.3 Режим ответа (reply vs обычное сообщение)

**Проблема:** Reply на каждое сообщение — перебор. В обычном чате люди не reply'ят на каждое.

**Решение:** `event.reply()` только если:
- Прошло >2 минут с последнего сообщения (новый "виток" разговора)
- Есть другие собеседники в чате (чтобы было понятно кому ответ)
- Сообщение — ответ на конкретный вопрос после паузы

Иначе — `event.respond()` (просто новое сообщение в чат).

**Реализация:** Трекать timestamp последнего сообщения в чате. Если delta < 120 секунд → respond. Если > 120 → reply.

### 4.4 Групповые чаты

**Проблема:** Сейчас `is_private` check отсекает все групповые сообщения.

**Решение (поэтапно):**
1. Реагировать в группах только на прямое обращение (упоминание, reply на её сообщение)
2. В будущем — анализ контекста, участие в общих разговорах

**Trigger'ы для ответа в группе:**
- `@Соня` или `@sonya` в тексте
- Reply на сообщение Сони
- Прямое обращение по имени в начале сообщения

### 4.5 Инициатива — писать первой

**Проблема:** Соня только реагирует, никогда не пишет первой.

**Решение:** Привязать к existing InternalProcess (thinking loop). Когда thinking loop генерирует мысль с intent "написать Ивану" — отправлять через userbot.

**Условия для инициативы:**
- Прошло >2 часов с последнего общения
- Drive `closeness_need` выше порога
- Thinking loop сгенерировал intent с target=telegram

**Ограничения:** Не спамить. Max 2-3 инициативных сообщения в день. Не писать ночью (проверять timezone).

### 4.6 Conversation memory (history between sessions)

**Проблема:** При перезапуске процесса conversation context теряется. Episodic memory записывается, но не используется как chat history.

**Решение:** Уже частично работает — episodic memory инжектится в system prompt. Но это summary, не точная история.

**Улучшение:** Хранить последние 50 сообщений каждого чата в substrate (отдельная таблица `chat_messages`). При формировании context — брать последние 10-15 оттуда, а не через Telethon API (быстрее + работает после рестарта).

---

## 5. Порядок реализации

| # | Задача | Риск сломать текущее | Effort |
|---|--------|---------------------|--------|
| 1 | Chat history (4.1) | Низкий — аддитивно | 30 мин |
| 2 | Reply/respond logic (4.3) | Низкий — замена одной строки | 15 мин |
| 3 | Стикеры/медиа (4.2) | Нулевой — новый код path | 30 мин |
| 4 | Групповые чаты (4.4) | Нулевой — новый if-branch | 45 мин |
| 5 | Conversation memory (4.6) | Низкий — новая таблица | 1 час |
| 6 | Инициатива (4.5) | Средний — связка с thinking loop | 2 часа |

**Правило:** Каждый пункт деплоится отдельно. После деплоя — тест в живом чате. Если сломалось — откат на предыдущий коммит.

---

## 6. Деплой процедура

```bash
# С локальной машины:
git add -A; git commit -m "..."; git push origin develop

# На сервере:
ssh jester-sonya@34.38.255.149 "sudo pkill -9 -f 'python.*sonya' 2>/dev/null; sleep 1; rm -f ~/.sonya/*.lock; cd ~/Sonya && git fetch origin && git reset --hard origin/develop && PYTHONPATH=src:packages/tg-userbot/src:packages/tg-bridge/src nohup .venv/bin/python -m sonya > /tmp/sonya.log 2>&1 &"

# Проверка:
ssh jester-sonya@34.38.255.149 "sleep 5; cat /tmp/sonya.log"
```

**Если сломалось:**
```bash
ssh jester-sonya@34.38.255.149 "cd ~/Sonya && git reset --hard 4fb631d && sudo pkill -9 -f 'python.*sonya'; sleep 1; rm -f ~/.sonya/*.lock; PYTHONPATH=src:packages/tg-userbot/src:packages/tg-bridge/src nohup .venv/bin/python -m sonya > /tmp/sonya.log 2>&1 &"
```
