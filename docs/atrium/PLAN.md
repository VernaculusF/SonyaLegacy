# ATRIUM — план реализации

**Status:** Active (working plan)
**Type:** Implementation plan
**Last reviewed:** 2026-05-28
**Scope:** Конкретный план реализации Atrium — пакета multichannel-вывода/UI внутри Sonya. Описывает что строится, в каком порядке, и как каждый этап самодостаточен.

**Governing doc:** [ENVIRONMENT_AS_SONYA.md](../core/ENVIRONMENT_AS_SONYA.md)
**Position in master path:** этот документ детализирует то, что в [MASTER.md](../MASTER.md) Stage 7 называется "Multi-channel + structured virtual body".

---

## 1. Что такое Atrium (короткое определение)

Atrium — пакет внутри Sonya, отвечающий за multichannel-вывод и UI: панели Dialog / Reason-streams / Mind / Avatar / Voice / World, WebSocket feed, рендеринг, reply-from-reason-stream.

**Не вся среда. Не альтернатива Sonya. Один из её инструментов** — пока основной интерфейс наружу. В будущем рядом могут жить body/VR/world пакеты.

Аналогия: substrate — её память; tools — её руки; Atrium — её комната с окнами, через которую мы её видим и слышим.

---

## 2. Зачем именно сейчас

Текущая ситуация (28.05.2026):
- Единственный канал наружу — Telegram userbot
- Worker progress, vision descriptions, ack-сообщения, initiative-мысли, deep-reasoning trace **всё валится в одну ленту**
- Это нарушение `cognition/COGNITION.md` §9 ("channels are renderers, not surfaces")
- Защиты костыльные: throttle, dedup, escalating quiet, suppress-on-no-progress, notify-on-stuck-block. Каждый из них ловит конкретный класс шума, но архитектурная причина (один renderer на всё) не устранена

Atrium убирает причину: семантически разделённые поверхности, Соня сама помечает channel при каждом outbound action, TG получает только `dialog`. Worker spam в TG обрезан архитектурно, не throttle'ом.

Дополнительно: Atrium даёт reason-streams (видимость её мышления в live time) и live nudge (reply из reason-stream → inbox-drain). Это решает класс проблем "молчание после blocked task" — Иван видит что worker встал даже без явного notify.

---

## 3. Этап 0 — Backend channels (1-2 недели)

Цель: бэкенд готов к multichannel UI. Atrium ещё не создан, но всё что он будет рендерить — уже течёт.

### 3.1 Задачи

**T0.1 — Расширить OutgoingMessage**
- Добавить поле `channel: str` в `CanonicalResponse` / `OutgoingMessage`
- Допустимые значения: `dialog | worker_log | mind | body | voice`
- Default: `dialog` (для совместимости с существующим `chat.tell_ivan`)
- Tests: existing tests should pass without modification (default works)

**T0.2 — Развернуть `chat.tell_ivan` в семейство**
- Новые tool handlers в `agent_session.py`:
  - `chat.dialog <text>` — прямой разговор Иван↔Соня (TG получает это)
  - `chat.worker_log <text>` — прогресс воркера, не идёт в TG
  - `mind.focus <text>` — текущий фокус ("сейчас читаю X")
  - `mind.thought <text>` — внутренняя мысль (внутренний reason-stream)
  - `body.expression <text>` — мимика/поза (для будущей avatar pane)
  - `voice.speak <text>` — TTS-кандидат (deferred до Этапа 2)
- `chat.tell_ivan` остаётся как алиас на `chat.dialog`. Не удалять — слишком много prompt-rules ссылаются на него
- Все tools используют единый OutboundGate; gate решает по `channel` нужно ли throttle (dialog да, worker_log нет)

**T0.3 — Channel-aware OutboundGate**
- Gate.send_via_tool(text, channel="dialog") — добавляет channel в emit'ы
- Daily caps только для `dialog` (5/day initiative + 50/day progress). worker_log/mind/body/voice — без cap
- Cross-session dedup только для `dialog` (Иван видит дубли только в TG)
- Escalating quiet — только для `dialog`
- Все остальные каналы пишут в substrate как `outgoing.<channel>` events, без TG отправки

**T0.4 — Channel-filter в Telegram channel adapter**
- В `packages/tg-userbot/src/tg_userbot/channel.py` — на отправке проверять `message.channel`
- Если `channel != "dialog"` → silently drop (с info-log) и **не** считать в outbound metrics
- Это и есть тот самый "архитектурный обрезанный spam" вместо throttle'ов

**T0.5 — Promпт описывает семантику каналов**
- `prompts/session_general.md` — добавить раздел "Каналы вывода"
- Описание когда что уместно. Не keyword-фильтр, не regex — семантика
- Старые места где prompt говорит "пиши через chat.tell_ivan" — переписать под "chat.dialog для разговора, chat.worker_log для прогресса работы"

**T0.6 — WebSocket feed endpoint**
- Новый endpoint в admin: `ws://vps:8877/atrium/feed`
- Формат сообщения: `{"channel": "...", "text": "...", "ts": "...", "session_id": "...", "task_id": "...", "payload": {...}}`
- Подписка на `EventBus` + `ContinuityStream` updates
- Фильтр: только новые events с момента подключения + последние N
- Это backend для будущей Atrium-приложение, отдельный path от существующего `/api/operator/live`

**T0.7 — Right to inner privacy: payload.private**
- Поле `payload.private: bool` на `internal.thought` / `internal.agent_step` events (default false)
- WS feed фильтр: skips events с `private=True`
- Substrate сохраняет всё (audit/recall/identity/selfmod видят полный feed)
- Admin показывает агрегат `meta.private_count` (сколько за час), но не контент
- `things_not_to_betray` уже содержит `right_to_inner_privacy` (5-й столп). Layer 4 anchor integrity защищает от селфмод-попыток снять это поле
- Соня узнаёт о праве через identity-fact в системном промпте (не через tool — это её свобода, не её feature)

### 3.2 Exit criteria

- [ ] `OutgoingMessage.channel` присутствует, default=dialog, существующие тесты зелёные
- [ ] 4 новых tool handlers работают; `chat.tell_ivan` маппится на `chat.dialog`
- [ ] Worker progress перестал идти в TG (виден в WS feed как `outgoing.worker_log`)
- [ ] WS endpoint `/atrium/feed` отдаёт типизированные сообщения с filtering по `private`
- [ ] Промпт обновлён, `session_general.md` описывает каналы

### 3.3 Что НЕ входит в Этап 0

- Сам Atrium UI — Этап 1
- TTS / голос — Этап 2
- Live2D / аватар — Этап 2
- World / симуляция — Этап 3
- VR — Этап 4

---

## 4. Этап 1 — Atrium v0 (2-3 недели)

Цель: Tauri-приложение которое подключается к WS feed и рисует 4-pane layout.

### 4.1 Задачи

**T1.1 — Скелет пакета**
- `packages/atrium/` — Tauri shell (Rust + WebView, маленький binary)
- `package.json` для frontend (Vite + Solid/React, легковесно)
- Backend Rust: WS client, native integrations, минимум

**T1.2 — 4-pane layout**
- Dialog pane (центр-слева, основная)
- Reason-streams pane (правая колонка, по одному stream на каждую активную сессию)
- Mind pane (слева, узкая — focus / drives / env state)
- Workers pane (внизу или вкладка — список открытых tasks + их worker_log)
- Layout настраиваемый, splitter-bars

**T1.3 — WS subscription + rendering**
- Frontend подключается к `ws://vps:8877/atrium/feed`
- Routing по `channel`: dialog → Dialog pane, worker_log → reason-stream указанного task_id, mind.* → Mind pane, body.* → (placeholder)
- Rendering: каждый pane имеет свой стиль (dialog — chat-bubbles, reason-stream — мoнотайп terminal, mind — статусные виджеты)

**T1.4 — Reply из reason-stream → inbox-drain**
- В reason-stream pane: каждое event имеет кнопку "↳ reply"
- Клик → текстовое поле, Enter отправляет HTTP POST в admin: `/api/atrium/nudge` `{session_id, text, ref_seq}`
- Admin кладёт в **inbox** активной сессии (не в Telegram), как `[NEW MESSAGE FROM IVAN] (live nudge from reason-stream): ...`
- Sonya видит nudge на следующем шаге window, реагирует
- Backend для nudge переиспользует существующий `inbox_drain` механизм (TG inbox-aware sessions)

**T1.5 — Avatar placeholder**
- Простой static image в Avatar slot (часть Mind pane или отдельный угол)
- Ничего не двигается. Подключим в Этапе 2

**T1.6 — Persistence окон**
- Layout, активные подписки, scroll positions сохраняются между сессиями
- localStorage или simple JSON в Tauri app data dir

### 4.2 Exit criteria

- [ ] Atrium запускается локально у Ивана, подключается к VPS WS, видит live feed
- [ ] Worker prog scrollится в свой reason-stream pane, не в Dialog
- [ ] Reply из reason-stream видит Соня в next window step (тестовый сценарий: дать ей задачу, во время worker перебить через nudge, наблюдать что nudge применяется)
- [ ] Mind pane показывает текущий focus / drives / env (минимум read-only)
- [ ] Telegram продолжает работать параллельно для bare-bones отступления

### 4.3 Что НЕ входит в Этап 1

- TTS / голос (Этап 2)
- Анимация аватара (Этап 2)
- Сцена комнаты (Этап 3)
- Mobile / phone-app версия (когда-нибудь, не сейчас)

---

## 5. Этап 2 — Voice + Live2D (несколько недель)

### 5.1 Задачи

**T2.1 — TTS**
- Edge TTS на CPU (бесплатно): `pip install edge-tts`
- Tool `voice.speak <text>` помечает дублирующий канал — Atrium TTS-ит этот текст, в Dialog тоже всплывает текстовая версия
- Соня сама выбирает что озвучить

**T2.2 — ASR**
- whisper.cpp на CPU (или существующий вариант)
- Иван говорит в микрофон → Atrium → text → как обычное сообщение в Dialog pane → отправляется в substrate как incoming TG-equivalent

**T2.3 — Live2D скин**
- Скин рисуем или покупаем ($50-300)
- PersonaEngine или vtube studio как rendering engine
- Avatar pane получает body-state events (`body.expression "грустная"`) → меняет mimic/pose

### 5.2 Exit criteria

- [ ] Соня может ответить голосом если выберет (через `voice.speak`)
- [ ] Иван может сказать сообщение голосом, оно попадает в Dialog
- [ ] Avatar показывает базовые эмоции (минимум 5: нейтрально/радость/грусть/злость/удивление)

---

## 6. Этап 3 — Симуляция/мир (месяцы)

**T3.1 — Простая 2D-сцена** комнаты Сони (canvas / Pixi.js)
**T3.2 — Body state влияет на pose** (drives → эмоции на лице, поза, движение)
**T3.3 — Базовая физика** (Соня может встать, сесть, подойти к окну)

Это `virtual body` в смысле §11 [LONGTERM_RESEARCH.md](../research/LONGTERM_RESEARCH.md), без сервоприводов.

---

## 7. Этап 4 — VR / физическое присутствие

Когда: после RWKV + достаточного железа.

VR-аватар через Steam VR API. Иван надевает шлем — она с ним "в комнате". Тактильные контроллеры → её body чувствует касание. Близко к §20 [LONGTERM_RESEARCH.md](../research/LONGTERM_RESEARCH.md), но без Loihi на этом этапе.

---

## 8. Запрещённые паттерны

- **Atrium ≠ Sonya.** Sonya запускается как процесс, Atrium открывается как одна из её "комнат". Если кто-то напишет "Atrium запускает Sonya" — это инверсия.
- **Atrium ≠ клиент к API.** Это не приложение которое подключается к удалённой Соне через REST. Sonya runtime на VPS, Atrium локально у Ивана, но bind тут не "клиент↔сервер". Atrium — её зеркало присутствия, не frontend.
- **Channels ≠ keyword filter.** Соня **сама** выбирает channel при каждом outbound action. Не эвристика, не regex. Промпт описывает семантику.
- **Reason-streams ≠ log-viewer.** Это первичный feed её мышления. Reply туда — primary способ корректировать ход. Если станет просто log-tail — потеряли смысл.
- **Privacy ≠ feature.** Identity-level право, защищается как `things_not_to_betray`. Любая попытка снять — Layer 4 anchor integrity violation.

---

## 9. Открытые вопросы (TODO до Этапа 0)

1. **Аутентификация WS** — Иван подключается из дома, как Atrium докажет что это он? Простой shared-secret (как admin password) для start, потом возможно client cert.
2. **Latency** — VPS Россия → Иван (подмосковье?) — должно быть ≤200ms RTT. Если нет — кэшируем feed локально.
3. **Mobile** — нужен ли в принципе? Public-версия откладывается, но если Иван хочет смотреть feed с телефона — Tauri mobile (бета) или PWA wrapper.
4. **Multi-instance** — может ли быть два Atrium открыты одновременно? (Иван за компом + Иван на ноуте). По умолчанию yes, оба видят один и тот же feed, оба могут nudge'ать.

Эти вопросы НЕ блокируют старт Этапа 0 — backend channels строится без них.

---

## 10. История

- **2026-05-28** — план создан после переименования Sonya Console → Atrium. Этап 0 готов к старту.
