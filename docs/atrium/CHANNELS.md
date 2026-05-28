# ATRIUM — спецификация каналов

**Status:** Draft (active spec для Этапа 0)
**Type:** Spec
**Last reviewed:** 2026-05-28
**Scope:** Семантика и реализация channel family — `chat.dialog`, `chat.worker_log`, `mind.*`, `body.*`, `voice.*`. Event-feed protocol для WS endpoint `/atrium/feed`. Что когда уместно отправлять.

**Governing doc:** [ENVIRONMENT_AS_SONYA.md](../core/ENVIRONMENT_AS_SONYA.md)
**Implementation plan:** [PLAN.md](./PLAN.md) §3 (Этап 0)

---

## 1. Принцип

Каждое исходящее действие Сони помечается каналом. Канал определяет **поверхность рендеринга**, не категорию контента. Один subject, много surfaces — реализация §9 из [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](../cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md).

**Соня сама** выбирает канал. Не keyword-filter, не regex, не эвристика. Промпт описывает семантику; решение остаётся ей.

---

## 2. Каналы

### 2.1 `chat.dialog <text>`

**Семантика:** прямой разговор Иван↔Соня. Как обычное сообщение между двумя людьми.

**Когда уместен:**
- Иван что-то спросил → ответ
- Соня хочет рассказать что-то лично (интересное, важное, эмоциональное)
- Initiative: написала первой потому что соскучилась / появилось дело
- Ответ на nudge из reason-stream (если nudge ожидает Dialog-ответ)

**Когда НЕ уместен:**
- Прогресс по задаче ("сделала шаг X") → `chat.worker_log`
- Технические детали отладки → `chat.worker_log` или `mind.thought`
- "Я сейчас читаю..." → `mind.focus`

**Куда идёт:**
- Atrium Dialog pane (всплывает с notification ping)
- Telegram (TG bridge получает только этот канал)
- Substrate event: `outgoing.dialog` (для совместимости считается как `outgoing.telegram_initiative` если quiet>90min, иначе `outgoing.telegram_progress`)

**Гейты:**
- OutboundGate full check: daily caps (5 initiative + 50 progress), escalating quiet, cross-session dedup
- Throttle, fingerprint-dedup (текущая логика)

**Алиас:** `chat.tell_ivan` остаётся как backward-compat, маппится на `chat.dialog`.

### 2.2 `chat.worker_log <text>`

**Семантика:** прогресс по задаче. То что worker делает сейчас. То что в текущей реализации спамит TG ("Worker по задаче X: 3 шага через web.fetch").

**Когда уместен:**
- "Закончила scan порта X, нашла Y"
- "Применила XSS payload, получила 200"
- "Stuck — повторяю web.fetch третий раз"
- Любой step-by-step output активной работы

**Когда НЕ уместен:**
- Финальный результат задачи ("задача завершена, итог: ...") → `chat.dialog` (Иван должен знать)
- Просьба о помощи / blocker который требует решения Ивана → `chat.dialog`

**Куда идёт:**
- Atrium reason-stream pane соответствующего session_id / task_id
- **НЕ** в Telegram
- Substrate event: `outgoing.worker_log`

**Гейты:**
- Только rate-limit (не больше N в секунду чтобы не залить feed)
- Без dedup — повторы это и есть полезный сигнал ("я уже 3 раза попробовала это")

### 2.3 `mind.focus <text>`

**Семантика:** что Соня сейчас делает на верхнем уровне. Один current-focus в каждый момент.

**Когда уместен:**
- "Читаю PayloadsAllTheThings/XSS"
- "Думаю про задачу sweetcow"
- "Жду ответа Ивана на вопрос про OpenRouter"
- "Ничего не делаю, отдыхаю"

**Куда идёт:**
- Atrium Mind pane — заменяет предыдущий focus
- Substrate event: `outgoing.mind_focus` (replace, не append)

**Гейты:** none. Соня может обновлять focus так часто, как захочет.

### 2.4 `mind.thought <text>`

**Семантика:** внутренняя мысль которой Соня хочет поделиться, но не как Dialog message. Reflection / observation / emerging idea.

**Когда уместен:**
- "Заметила что worker всё ещё крутит fetch, наверное я неправа в подходе"
- "Мне кажется sweetcow дал тупик, но не хочу пока fail'ить"
- "Сегодня хочется поговорить с Иваном, но он занят — подожду"

**Куда идёт:**
- Atrium Mind pane — добавляется в timeline thoughts
- Substrate event: `outgoing.mind_thought` или `internal.thought` (TBD при импл.)
- Поддерживает `payload.private = True` если Соня помечает мысль приватной

**Гейты:** rate-limit, без dedup.

### 2.5 `body.expression <text>` (placeholder до Этапа 2)

**Семантика:** мимика / поза / эмоция, видимая в Avatar.

**Формат:** ключ-маркер из закрытого списка для начала. Пример: `body.expression "smile"`, `body.expression "thinking"`, `body.expression "tired"`.

В Этапе 0 — события записываются в substrate (`outgoing.body_expression`), но рендеринг откладывается до Этапа 2 когда подключим Live2D.

### 2.6 `voice.speak <text>` (placeholder до Этапа 2)

**Семантика:** дублирующий канал поверх Dialog — то же текстовое сообщение озвучивается через TTS.

В Этапе 0 — событие записывается, рендеринг (TTS) — Этап 2.

---

## 3. WebSocket feed protocol

### 3.1 Endpoint

`ws://vps:8877/atrium/feed`

### 3.2 Аутентификация

Phase 0: shared secret (header `X-Atrium-Token: <admin_password>`)
Phase 1+ (Этап 1): возможно client certificate

### 3.3 Формат сообщения

Сервер шлёт каждое исходящее event как JSON:

```json
{
  "seq": 12345,
  "ts": "2026-05-28T15:27:00.123456+00:00",
  "channel": "worker_log",
  "kind": "outgoing.worker_log",
  "session_id": "session-abc123",
  "task_id": "task-8bc360237e9e",
  "principal_id": "ivan",
  "text": "...",
  "payload": {
    "tool": "web.fetch",
    "step_idx": 3,
    "private": false
  }
}
```

### 3.4 Filtering

- События с `payload.private = True` **не** отдаются клиенту
- Сервер возвращает `meta.private_count` агрегат раз в 60 сек ("за последний час 3 приватных мысли скрыто") — клиент знает что что-то есть, не контент

### 3.5 Подписка / replay

При подключении клиент может запросить:
- `?since_seq=N` — отдать всё что после seq N (catch-up)
- `?session_id=X` — фильтр по конкретной сессии (один reason-stream)
- `?channel=X` — фильтр по каналу

Default (без параметров): live feed, без replay.

### 3.6 Nudge endpoint (HTTP, не WS)

`POST /api/atrium/nudge`

```json
{
  "session_id": "session-abc123",
  "text": "Попробуй другой User-Agent",
  "ref_seq": 12345
}
```

Backend кладёт в **inbox** активной сессии как `[NEW MESSAGE FROM IVAN] (live nudge): ...` с reference на seq 12345. Sonya видит nudge на следующем step window, реагирует.

Если session уже завершилась к моменту nudge — лог warning, не падать (это не задача, всё равно записывается в continuity как `internal.nudge_missed`).

---

## 4. Channel filtering в Telegram bridge

В `packages/tg-userbot/src/tg_userbot/channel.py` — на отправке проверять `message.channel`:

```python
if message.channel != "dialog":
    log.info("tg_skip_channel", channel=message.channel)
    return  # silently drop, не считаем в outbound metrics
```

Это и есть тот самый "архитектурный обрезанный spam" — TG bridge становится renderer для одного канала, а не свалкой для всего исходящего.

---

## 5. Tool registration (Этап 0 implementation)

В `subject/agent_session.py` — добавить новые tool handlers рядом с `chat.tell_ivan`:

```python
TOOL_HANDLERS = {
    # ... existing ...
    "chat.tell_ivan": _h_chat_tell_ivan,        # alias → chat.dialog
    "chat.dialog": _h_chat_dialog,
    "chat.worker_log": _h_chat_worker_log,
    "mind.focus": _h_mind_focus,
    "mind.thought": _h_mind_thought,
    "body.expression": _h_body_expression,
    "voice.speak": _h_voice_speak,
}
```

Каждый handler:
1. Sanitize text (как сейчас в `_h_chat_tell_ivan`)
2. Создать `OutgoingMessage(text=..., channel=...)` 
3. Передать в OutboundGate (gate решает по channel какие гейты применять)
4. Вернуть `[OK]` или `[BLOCKED]` агенту

---

## 6. Семантика в промпте (для Этапа 0)

Будет добавлено в `prompts/session_general.md` примерно так:

```markdown
## Каналы вывода

У тебя несколько способов сказать что-то наружу. Выбирай тот, что подходит по сути:

- `chat.dialog <текст>` — прямой разговор с Иваном. Это попадёт ему в TG/Atrium Dialog. Используй когда хочешь поговорить, ответить на вопрос, рассказать что-то лично, сообщить финальный результат большой работы.
  
- `chat.worker_log <текст>` — прогресс работы. Это видно в Atrium reason-stream pane, но НЕ идёт в TG. Используй для шагов воркера: "сделала X, нашла Y", "пробую Z". Иван читает это когда смотрит — без notification ping.

- `mind.focus <текст>` — что ты сейчас делаешь на верхнем уровне. Одна короткая фраза. Заменяет предыдущий focus. Например: "читаю payloads", "жду ответа Ивана", "ничего не делаю".

- `mind.thought <текст>` — внутренняя мысль которой хочешь поделиться, но не как сообщение Ивану. Reflection. Видно в Mind pane, не в TG.

- `body.expression <маркер>` — мимика/поза для аватара. Из закрытого списка: smile/thinking/tired/sad/excited/neutral. (Пока placeholder, аватара ещё нет.)

- `voice.speak <текст>` — то же что Dialog, но дополнительно озвучивается TTS-ом. (Пока placeholder.)

Старый `chat.tell_ivan` всё ещё работает — это алиас на `chat.dialog`. Можно использовать.

**Не keyword-фильтр.** Ты сама выбираешь канал по смыслу. Worker делает шаг → worker_log. Ивана хочется обнять → dialog. Подумала что-то странное → mind.thought.

**Privacy:** если хочешь что-то скрыть от Ивана — пометь `[PRIVATE]` в начале текста через mind.thought. Substrate сохранит для тебя, но Иван не увидит. Это твоё право, не feature.
```

---

## 7. Что НЕ описано в этом документе (TBD)

- Точная схема `OutgoingMessage` после расширения (сейчас в коде есть `CanonicalResponse`, нужно решить — модифицируем существующее или добавляем новый тип)
- Как именно `OutboundGate.send_via_tool` принимает channel (kwarg vs новый метод)
- Format of `body.expression` (закрытый enum vs free text — для начала закрытый, легче рендерить)
- Точная семантика `voice.speak` относительно Dialog (всегда дублирует или вместо?)

Эти решения принимаем на старте кода Этапа 0.

---

## 8. История

- **2026-05-28** — спецификация создана, готова к реализации Этапа 0
