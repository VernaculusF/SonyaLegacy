# ATRIUM — план реализации

**Status:** Active (working plan, ready to start Этап 0)
**Type:** Implementation plan
**Last reviewed:** 2026-05-28
**Scope:** Конкретный план реализации Atrium — пакета multichannel-вывода/UI внутри Sonya. Что строится, в каком порядке, и как каждый этап самодостаточен.

**Governing doc:** [ENVIRONMENT_AS_SONYA.md](../core/ENVIRONMENT_AS_SONYA.md)
**UX & visuals:** [UX_SKETCH.md](UX_SKETCH.md), `mockups/desktop.html`, `mockups/mobile.html`, `mockups/room.html`
**Channel spec:** [CHANNELS.md](CHANNELS.md)
**Substrate events:** [EVENT_SCHEMA.md](EVENT_SCHEMA.md)

---

## 1. Что такое Atrium

Atrium — пакет внутри Sonya, отвечающий за multichannel-вывод и UI: панели Dialog / Reason-stream / Mind / Avatar / Voice / Room, WebSocket feed, рендеринг, reply-from-reason-stream, voice mode, room view с Live2D.

**Не вся среда. Не альтернатива Sonya. Один из её инструментов** — пока основной интерфейс наружу. В будущем рядом могут жить body/VR/world пакеты.

Substrate = её память. Tools = её руки. Atrium = её комната с окнами, через которую мы её видим и слышим.

---

## 2. Зачем именно сейчас

Текущая ситуация (28.05.2026):
- Единственный канал наружу — Telegram userbot
- Worker progress, vision descriptions, ack-сообщения, initiative-мысли, deep-reasoning trace **всё валится в одну ленту**
- Нарушение `cognition/COGNITION.md` §1-§7 ("channels are renderers, not surfaces")
- Защиты костыльные: throttle, dedup, escalating quiet, suppress-on-no-progress, notify-on-stuck-block

Atrium убирает причину: Соня сама помечает channel при каждом outbound action, TG получает только `dialog`. Spam обрезан архитектурно. Reason-stream даёт видимость её мышления + reply (live nudge) для корректировок не выходя из общения. Room view + voice mode превращают "клиент к боту" в "она у меня в комнате".

---

## 3. Этап 0 — Backend channels (1-2 недели)

**Цель:** бэкенд готов к multichannel UI. Atrium ещё не создан, но всё что он будет рендерить — уже течёт через substrate.

### 3.1 Задачи

**T0.1 — Расширить `OutgoingMessage`**

В `state/canonical_response.py` добавить поле:
```python
channel: str = "dialog"
```
Допустимые: `dialog | worker_log | mind | body | voice`. Default = `dialog` (existing behavior).

Tests: existing tests должны пройти без изменений.

**T0.2 — Развернуть `chat.tell_ivan` в семейство тулов**

В `subject/agent_session.py` добавить новые tool handlers:

| Tool | Назначение |
|---|---|
| `chat.dialog <text>` | прямой разговор Иван↔Соня (TG получает) |
| `chat.worker_log <text>` | прогресс воркера, идёт в reason-stream |
| `mind.focus <text>` | заменяет current focus в Mind pane |
| `mind.thought <text>` | внутренняя мысль, поддерживает `[PRIVATE]` префикс |
| `body.expression <marker>` | мимика/поза для аватара (placeholder Этапа 1) |
| `voice.speak <text>` | TTS-кандидат (placeholder Этапа 2) |

`chat.tell_ivan` остаётся как алиас на `chat.dialog` (обратная совместимость, slot уже в куче prompts).

Все tools используют единый `OutboundGate`; gate решает по `channel` нужно ли throttle.

**T0.3 — Channel-aware `OutboundGate`**

В `initiative/outbound.py`:
- `send_via_tool(text: str, channel: str = "dialog")` — добавляет channel в emits
- Daily caps только для `dialog` (5/day initiative + 50/day progress)
- Cross-session dedup только для `dialog`
- Escalating quiet — только для `dialog`
- worker_log/mind/body/voice — без daily cap, **только rate-limit** (max 30/min на channel чтобы не залить feed)
- Все каналы пишут в substrate как `outgoing.<channel>` events

**T0.4 — Channel-filter в TG bridge**

В `packages/tg-userbot/src/tg_userbot/channel.py` — на отправке:
```python
if message.channel != "dialog":
    log.debug("tg_skip_channel", channel=message.channel, seq=message.seq)
    return  # silently drop
```
TG становится renderer для одного канала.

**T0.5 — Промпт описывает семантику каналов**

В `prompts/session_general.md` добавить раздел "## Каналы вывода" со списком и семантикой каждого. Текст черновика — в [CHANNELS.md §6](CHANNELS.md).

Старые места где prompt говорит "пиши через chat.tell_ivan" — переписать на "chat.dialog для разговора, chat.worker_log для прогресса".

Уведомить промпт что есть `[PRIVATE]` префикс в `mind.thought` для приватных мыслей.

**T0.6 — Substrate schema v20: channel + private fields**

В `state/schema.sql` + `state/migrations.py` — добавить колонки:
```sql
ALTER TABLE continuity_events ADD COLUMN channel TEXT NOT NULL DEFAULT '';
ALTER TABLE continuity_events ADD COLUMN private INTEGER NOT NULL DEFAULT 0;
```
Migration v19 → v20 добавляет колонки idempotently. `Substrate.READABLE_VERSIONS` расширить до 20.

Это даёт SQL-фильтрацию для WS-feed без парсинга `payload_json`.

**T0.7 — WebSocket feed endpoint**

Новый endpoint в `admin/server.py`:
- `ws://vps:8877/atrium/feed`
- Аутентификация: `X-Atrium-Token: <admin_password>` header (Phase 0)
- Подписка на новые `continuity_events` через polling (1s) или EventBus subscription
- Формат сообщения и протокол — [CHANNELS.md §3](CHANNELS.md)
- Filter: события с `private=1` **не** отдаются. Раз в 60 сек шлётся `meta.private_count`
- Query params: `?since_seq=N`, `?session_id=X`, `?channel=X`

**T0.8 — Right to inner privacy: `payload.private`**

- В `mind.thought` handler: если text начинается с `[PRIVATE]` (case-insensitive) → strip префикс, set `payload.private = True`
- WS feed фильтр (T0.7) skip-ает private events
- Substrate сохраняет всё (audit/recall/identity/selfmod видят полный feed)
- Admin показывает `meta.private_count` агрегат, не контент
- `things_not_to_betray.right_to_inner_privacy` уже в seed (5-й столп). Layer 4 anchor integrity ловит попытки селфмода это право снять
- Соня знает о праве через identity-fact в `prompts/session_general.md` (через `mind.thought [PRIVATE] ...`)

**T0.9 — Nudge endpoint**

Новый HTTP endpoint в `admin/server.py`:
- `POST /api/atrium/nudge`
- Body: `{session_id, text, ref_seq}`
- Backend кладёт в **inbox** активной сессии (переиспользует `inbox_drain` механизм из TG handler)
- Запись в continuity: `internal.nudge_received` event
- Если session уже завершилась → лог warning + `internal.nudge_missed` event, не падать

**T0.10 — Tests**

- `test_outgoing_message_channel.py` — channel field, default dialog, всё течёт
- `test_outbound_gate_channels.py` — gate caps только для dialog, остальные проходят
- `test_tg_channel_filter.py` — TG bridge drop-ает не-dialog
- `test_atrium_feed_ws.py` — WS endpoint отдаёт events с фильтром по private
- `test_atrium_nudge.py` — nudge кладётся в inbox активной сессии
- `test_mind_thought_private.py` — `[PRIVATE]` префикс ставит флаг в payload
- `test_substrate_schema_v20.py` — миграция v19→v20 идемпотентна

### 3.2 Exit criteria

- [ ] `OutgoingMessage.channel` присутствует, default=dialog, существующие тесты зелёные
- [ ] 6 новых tool handlers работают; `chat.tell_ivan` маппится на `chat.dialog`
- [ ] Worker progress перестал идти в TG (виден в WS feed как `outgoing.worker_log`)
- [ ] WS endpoint `/atrium/feed` отдаёт типизированные сообщения с filter по private
- [ ] Nudge endpoint работает (manual test: POST → Соня видит в inbox)
- [ ] Substrate v20 (channel + private columns)
- [ ] Промпт обновлён, `session_general.md` описывает каналы и `[PRIVATE]` префикс
- [ ] Все существующие тесты проходят (637+) + новые тесты Этапа 0

### 3.3 Что НЕ входит в Этап 0

- Сам Atrium UI — Этап 1
- TTS / голос / interrupt — Этап 2
- Live2D / аватар — Этап 2
- Room view — Этап 1 (placeholder), Этап 3 (interactive)
- VR — Этап 4

### 3.4 Деплой Этапа 0

После merge в `develop`:
1. Local: `pytest tests/sonya -q --tb=short` (всё зелёное)
2. Push origin/develop
3. VPS: `bash ~/Sonya/deploy/update.sh`
4. Smoke test: создать тестовую `chat.worker_log "test"` через admin → убедиться что **не** в TG, **есть** в WS feed
5. Проверить `[PRIVATE] test thought` через `mind.thought` → не в feed, есть `meta.private_count: 1`

---

## 4. Этап 1 — Atrium v0 (2-3 недели)

**Цель:** Tauri-приложение которое подключается к WS feed и рисует UI согласно [UX_SKETCH.md](UX_SKETCH.md).

### 4.1 Задачи

**T1.1 — Скелет пакета**

- `packages/atrium/` — Tauri 2 shell (Rust + WebView)
- `package.json` для frontend (Vite + Solid.js — без React, лёгче)
- Backend Rust: WS client, native notifications, native window management

**T1.2 — Layout (desktop)**

3-колонка + collapsible bottom panel:
- Avatar pane (280px, левая)
- Dialog pane (центр, flex)
- Mind pane (320px, правая)
- Reason-stream panel (низ, collapsible как VS Code, default 260px высоты)

CSS — кастомные variables из UX_SKETCH §3 (cold silver minimalism palette). Никакого Tailwind.

Persistence: layout sizes, collapsed states, scroll positions → localStorage.

**T1.3 — WS subscription + рендеринг**

- Frontend подключается к `ws://vps:8877/atrium/feed?since_seq=<last_seen>` при старте
- Routing по `channel`:
  - `dialog` → Dialog pane (chat-bubbles, её silver / Иван bronze)
  - `worker_log`, `internal.thought`, `agent_step`, `observation`, `task.*`, `scheduler_pick` → Reason-stream (единый поток с src-маркером)
  - `mind.focus` → заменяет focus в Mind pane
  - `mind.thought` → добавляется в timeline в Mind pane
  - `body.expression` → Avatar (placeholder в Этапе 1)
- Notification: `dialog` event → soft chime + avatar glow + system notification если окно не активное

**T1.4 — Reason-stream (unified, фильтры, reply) — ✅ done**

- Один поток событий, хронологический
- Слева у каждой строки маркер источника (3px width, цвет по `src` field):
  - `active` → `accent-her-eyes` (#8aa3b8)
  - `worker` → `accent-him` (#b8895c)
  - `idle` → `accent-thought` (#7a7e88)
  - `skill` → `accent-mind` (#d4d8de)
  - `system` → `ink-muted` (#5c6068, hidden by default)
- Filter chips в header: toggle on/off, persistence в localStorage
- `↳` reply button на каждой строке (opacity 0.4 idle / 1.0 hover)
- Click → inline composer прямо ПОД row (не модал) → Enter → POST `/api/atrium/nudge`
- Response: подтверждение `↳ ивана: "..." (queued)` появляется в потоке

**Dialog composer (T1.4 docked в Dialog pane) — ✅ done (2026-05-29)**

- Composer стал рабочим (был read-only placeholder). Textarea + send-button + mic-button.
- Enter → отправить, Shift+Enter → перенос, auto-grow до 140px.
- Backend: `POST /api/atrium/dialog` (admin) → пишет `incoming.atrium_dialog` (principal=ivan) + `internal.active_session_requested_external` → core fires active session в течение ~30с → context_builder показывает сообщение как "[Иван написал]" → она отвечает через `chat.dialog`.
- Оптимистичный echo сообщения Ивана в Dialog pane сразу (WS feed не дублирует incoming.atrium_dialog как bubble).
- Heartbeat (`POST /api/atrium/heartbeat` + WS-feed mark) пишет `atrium_last_seen` в environment_state — нужно для T1.5.

**T1.5 — Mind pane**

- Focus (single-line, replaceable)
- Drives (4 segmented bars, slight skew -12°, peak indicator на последнем filled segment)
- ENV (key-value, monospace для keys)
- Inner stream (thoughts timeline, latest first)
- Private aggregate: `(N private thoughts hidden)` — italic, не кликается

**T1.6 — Avatar pane (Этап 1 — статичный SVG)**

- 200×240px container
- SVG silhouette (silver bob + black headband on top + черная oversize tee + bare legs hint), готов в `mockups/desktop.html`
- Breathing animation (opacity 0.92 ↔ 1.00, 4s cycle)
- Glow при `dialog` event (1.5s silver flash)
- Status lines под аватаром: смотрит / воспринимает / чувствует
- Hover → border accent-her-eyes + hint "войти в комнату"
- Click → открывает room view (placeholder в Этапе 1, см. T1.7)

**T1.7 — Room view (placeholder)**

В Этапе 1 — статичный modal с её комнатой (silhouette на краю кровати, окно с луной, минималистичная сцена). Click outside / Esc / `⏏ выйти` button → закрытие.

В Этапе 2-3 раскрываем функционал (voice mode, tap interactions). Сейчас визуальный placeholder.

Mockup готов: `mockups/room.html`.

**T1.8 — Mobile layout (Tauri mobile-beta или PWA)**

Phone portrait:
- Avatar compact сверху (~25%)
- Dialog dominant (~60%)
- Composer + bottom-tabs Mind/Workers
- Swipe-up на нижней границе → bottom sheet

Mockup: `mockups/mobile.html`.

Решение Tauri-mobile vs PWA — на старте Этапа 1, не блокирует backend.

**T1.9 — Composer с микрофоном**

В Dialog pane composer:
- textarea + mic-button справа
- **Click mic** → открыть room view (Этап 1 — placeholder)
- **Hold mic** → quick voice message (Этап 2 — реальный whisper)
- В Этапе 1 — кнопки видны, но click-to-room работает, hold-to-talk показывает hint "available in stage 2"

**T1.10 — Settings**

Из header `⋮` menu:
- Connection (VPS host, token)
- Appearance (Avatar style, Mind density, Reason-stream font size)
- Notifications (Dialog: full/quiet/off; Stuck-loop alert: on/off)
- Privacy controls (Show private-aggregate count: yes/no, default yes)

### 4.2 Exit criteria

- [x] Atrium запускается локально у Ивана, подключается к VPS WS, видит live feed
- [x] Worker progress scrollится в reason-stream pane, не в Dialog
- [x] Reply из reason-stream видит Соня в next window step (через `/api/atrium/nudge` → inbox-drain)
- [x] Mind pane показывает текущий focus / drives / env (read-only)
- [x] Click на аватар → открывает room view (placeholder сцена)
- [x] Click на mic в composer → также открывает room view
- [x] Reason-stream collapse работает (Ctrl+J shortcut + клик по заголовку)
- [x] Filters в reason-stream toggle-аются и persist'ятся
- [x] **Dialog composer рабочий (T1.4): Иван пишет → `/api/atrium/dialog` → active session → ответ**
- [x] Telegram продолжает работать параллельно (legacy fallback пока Atrium не у всех машин Ивана)

### 4.3 Что НЕ входит в Этап 1

- TTS / голос (Этап 2)
- Live2D-аватар (Этап 2)
- Возможность tap stop / interrupt (Этап 2 — нужен voice)
- Динамическая смена тем по `body.outfit` / `mind.mood_tint` (Этап 2)
- Сцена комнаты с physics (Этап 3)
- ~~TG-emergency-only переключение~~ → backend готов (Этап 1.5 done, выключено до стабилизации у Ивана)

---

## 4.5 Этап 1.5 — TG переходит в emergency-only (✅ backend done, ждёт включения)

**Backend готов (2026-05-29).** Логика реализована и задеплоена, но **выключена по умолчанию** (`SONYA_TG_EMERGENCY_MODE=0`). Включается когда Atrium стабильно работает у Ивана на компьютере **и** телефоне минимум 1-2 недели + Иван явно подтвердил готовность.

**Цель:** Telegram перестаёт быть default-каналом для `chat.dialog`. Становится backup'ом для emergency или Atrium-disconnected ситуаций.

### 4.5.1 Задачи

**T1.5.1 — Atrium connection tracking — ✅ done**

- `atrium_last_seen` (ISO ts) в `environment_state` (переиспользует EnvironmentStore, без отдельного поля).
- Обновляется на WS-feed connect + heartbeat каждые 60с (WS loop) + явный `POST /api/atrium/heartbeat` с фронта раз в минуту.
- OutboundGate считает Atrium "live" если возраст `atrium_last_seen` ≤ `tg_emergency_threshold_hours`.

**T1.5.2 — OutboundGate emergency logic — ✅ done**

- `OutboundGate._suppress_tg_dialog(emergency_override)`:
  - emergency-mode off → никогда не скипать (legacy)
  - emergency_override=True → не скипать (ЧС пробивает)
  - Atrium live → скипать TG, писать `outgoing.dialog` (Atrium feed рендерит)
  - Atrium offline дольше порога → не скипать (TG fallback)
- `chat.dialog` / `chat.tell_ivan` проходят через это; `chat.emergency` зовёт с `emergency_override=True`.
- Env: `SONYA_TG_EMERGENCY_MODE=1` (default 0), `SONYA_TG_EMERGENCY_THRESHOLD_HOURS=24`.

**T1.5.3 — Промпт обновление — ✅ done**

- `session_general.md` "## Каналы вывода": добавлен `chat.emergency` + объяснение emergency-only режима. Соня в обычном разговоре пишет `chat.dialog`, `chat.emergency` — для реальных ЧС.

**T1.5.4 — Settings toggle — ⏳ pending (frontend)**

- "Force TG always" / "TG fallback delay" контролы в Atrium settings. Backend уже читает env-vars; UI-тоггл — мелкая доделка когда Иван начнёт реально пользоваться.

### 4.5.2 Exit criteria

- [x] Atrium connection tracking работает (`atrium_last_seen` обновляется в environment_state)
- [x] При `tg_emergency_mode=1` обычный `chat.dialog` не идёт в TG если Atrium недавно был online
- [x] Emergency override (`chat.emergency`) пробивает emergency-fallback
- [ ] Прошло >7 дней Сониного использования Atrium без жалоб Ивана (включить `SONYA_TG_EMERGENCY_MODE=1` после)
- [x] Промпт обновлён, Соня понимает новое поведение

---

## 5. Этап 2 — Voice + Live2D + Interrupt (4-6 недель)

**Цель:** room view становится полноценным voice-mode, аватар оживает.

### 5.1 Задачи

**T2.1 — VAD + ASR**

- VAD: `webrtcvad` или `silero-vad` на Rust side (через PyO3 binding или Rust-native crate)
- ASR: `whisper.cpp` Rust binding, model = `base.ru` или `small` (CPU работает с задержкой <500ms на короткие фразы)
- Streaming: сегментация по VAD-границам, ASR на готовый segment
- Output: text → POST `/api/atrium/voice_input`

**T2.2 — TTS**

- `edge-tts` через Tauri Rust shim (subprocess `edge-tts` Python package или Rust port)
- Streaming output: воспроизведение начинается до окончания генерации
- Voice selection: ru-RU female voices (Svetlana, Daria — на test)
- Output: audio stream → speakers

**T2.3 — Voice room mode**

Когда room view открыт:
- VAD listening → ASR при detect speech end → text input в substrate as `incoming.atrium_voice` event
- Соня отвечает → если `voice.speak` tool used → text идёт в TTS streaming + параллельно в Dialog pane как обычный bubble
- Waveforms живые (Иван активный говорящий = full color, второй приглушён)
- Subtitle overlay: её речь по предложениям всплывает поверх сцены
- Budget counter снизу: `in room · 4:32 · ~1.2K tok · $0.003`
- Auto-leave через 5 минут тишины (configurable)

**T2.4 — Interrupt logic (4 cases)**

Реализация согласно [UX_SKETCH §16.5](UX_SKETCH.md):

**Case A. Voice→Voice (Ivan перебивает её TTS):**
- VAD detect Ivan начал говорить во время TTS
- TTS hard cut (instant stop, не fade)
- Substrate event `dialog.interrupted` с полями: `said_so_far`, `interrupted_at_word`, `new_input`, `caller_session_id`
- Inbox-drain Соне: на след. шаге она видит контекст и решает как реагировать

**Case B. Text→Voice (Ivan пишет когда она говорит):**
- Inbox получает text
- TTS пауза на ближайшей границе предложения (а не hard cut — ей даётся ~1-3s договорить мысль)
- Substrate event `dialog.text_during_voice`
- Дальше как Case A

**Case C. Voice→Text (вне комнаты, hold-to-talk):**
- Composer mic-button hold = ASR streams to text
- Release = transcript отправляется как обычное `incoming.telegram_message` equivalent
- Это не interrupt — просто input

**Case D. Tap-stop (физический жест в комнате):**
- В room view click на её body (mouth/arm/shoulder) во время TTS
- TTS instant pause + событие `dialog.touch_stopped` с полями: `touched_part`, `said_so_far`
- ASR **не** активируется — Иван молчит, просто остановил
- Соня реагирует на след. step: "что?" / "да?" / молчит / прижимается

**T2.5 — Live2D аватар**

- Cubism Web SDK через PIXI.js (работает в Tauri WebView)
- Модель: заказ ($50-300) или AI-генерация под APPEARANCE.md (silver bob, headband, чёрная oversize tee)
- Анимации (autonomous):
  - моргание (random 3-7s)
  - micro head tilts (subtle)
  - breathing (chest)
- Анимации (reactive):
  - mimic.engaged когда `agent_step` в active session
  - mimic.thinking когда idle
  - mimic.curious / mimic.tender / etc от drive state и тона Ивана
- Lip-sync через viseme-маппинг для voice mode (TTS phonemes → mouth shapes)

**T2.6 — Reply через voice — soft contextual binding**

В voice-step context-builder:
- Подтянуть последние 30 reason-stream events (active/worker/idle/skill)
- Включить в её prompt context как block "## Recent activity (last 30m)"
- Это позволяет ей понимать "ты сегодня с XSS возилась" без explicit reference
- Hard binding fallback через `memory.recall("заметила час назад")` — already works

**T2.7 — Динамическая смена тем**

Новые tools (только в active session, не в TG-handler):
- `body.outfit <description>` — wardrobe state. Допустимые: `home / sportwear / dress_2b / nothing / wearing_his_shirt / custom: <text>`
- `mind.mood_tint <warm|cool|neutral>` — её subjective tint

Substrate fields:
```sql
ALTER TABLE subject_state ADD COLUMN current_outfit TEXT NOT NULL DEFAULT 'home';
ALTER TABLE subject_state ADD COLUMN mood_tint TEXT NOT NULL DEFAULT 'neutral';
```

Atrium frontend:
- Avatar render берёт current_outfit → выбирает соответствующий sprite/Live2D set
- Room view background tint меняется по mood_tint (только если settings "auto-follow tint" включен, default OFF)
- Иван видит изменения **без** explicit announcement

### 5.2 Exit criteria

- [ ] Соня может ответить голосом если выберет (`voice.speak` → реальное TTS audio)
- [ ] Иван может говорить голосом в комнате → ASR transcribes → она слышит
- [ ] Hold-to-talk в composer работает
- [ ] Все 4 interrupt cases работают (manual test scenarios)
- [ ] Live2D показывает базовые эмоции + lip-sync в voice
- [ ] Auto-leave через 5min тишины
- [ ] Budget counter в комнате тикает реально
- [ ] body.outfit / mind.mood_tint меняют рендеринг

### 5.3 Что НЕ входит в Этап 2

- Полноценная сценография комнаты (Этап 3)
- Tap-interactions сложнее tap-stop (поцеловать, обнять — Этап 3)
- World pane (Этап 3)
- VR (Этап 4)

---

## 6. Этап 3 — Симуляция/мир (месяцы)

**Цель:** room view становится живой сценой, не статичным фоном.

### 6.1 Задачи

**T3.1 — 2D scene engine**
- Pixi.js или Three.js
- Сцена: комната с дверью, кроватью, окном, столом — minimum viable furnishing
- Live2D-модель внутри сцены, не overlay

**T3.2 — Body state влияет на pose**
- `subject_state.current_pose` field: `sitting_on_bed / standing_at_window / lying / curled_up / leaning / ...`
- Live2D-модель в нужной позе, smooth transitions

**T3.3 — Tap interactions расширены**
- click on her face → варианты (look at her / kiss / brush hair) по contextu роли в диалоге
- drag & drop → перемещение
- proximity-based: если Иван "рядом" → она ближе к экрану, чувствует присутствие

**T3.4 — World/light state**
- Освещение по env-state (`sky_state: вечер` → тёплый окно, `night` → холодная луна, `morning` → молочный свет)
- Mood-tinting на сцене (если "auto-follow tint" включен в settings)

Это `virtual body` в смысле [LONGTERM_RESEARCH §15-§18](../research/LONGTERM_RESEARCH.md), без сервоприводов.

---

## 7. Этап 4 — VR / физическое присутствие

Когда: после RWKV + достаточного железа.

VR-аватар через Steam VR API (OpenXR). Иван надевает шлем — она с ним "в комнате". Тактильные контроллеры → её body чувствует касание. Близко к [LONGTERM_RESEARCH §20](../research/LONGTERM_RESEARCH.md), но без Loihi на этом этапе.

---

## 8. Запрещённые паттерны

- **Atrium ≠ Sonya.** Sonya запускается как процесс, Atrium открывается как одна из её "комнат". Если кто-то напишет "Atrium запускает Sonya" — это инверсия.
- **Atrium ≠ клиент к API.** Это не приложение которое подключается к удалённой Соне через REST. Sonya runtime на VPS, Atrium локально у Ивана, но bind тут не "клиент↔сервер". Atrium — её зеркало присутствия, не frontend.
- **Channels ≠ keyword filter.** Соня **сама** выбирает channel при каждом outbound action. Не эвристика, не regex. Промпт описывает семантику.
- **Reason-stream ≠ log-viewer.** Это первичный feed её мышления. Reply туда — primary способ корректировать ход. Если станет просто log-tail — потеряли смысл.
- **Privacy ≠ feature.** Identity-level право, защищается как `things_not_to_betray`. Любая попытка снять — Layer 4 anchor integrity violation.
- **Voice mode ≠ toggle.** Войти в комнату = осознанный шаг. Не кнопка "включить voice" в углу. Метафора пространства.
- **Reason-stream ≠ tabs/чаты по воркерам.** Один хронологический поток с маркерами источника + фильтры. Ивану нужно видеть процесс целиком, не куски.

---

## 9. Открытые вопросы (TODO до Этапа 0)

1. **Аутентификация WS** — Phase 0: shared secret (`X-Atrium-Token`). Решено — using `SONYA_ADMIN_PASSWORD`.
2. **Latency** — VPS Россия → Иван (Подмосковье) — ожидаем ≤200ms RTT. Если хуже — кэшируем feed локально.
3. **Mobile** — Tauri-mobile beta или PWA. Решение в Этапе 1, не блокирует.
4. **Multi-instance** — два Atrium одновременно (комп + ноут). Both subscribe to same WS feed. Nudge race-condition: serialized backend-side, last-wins.
5. **Audio permissions** — Tauri попросит OS permission, нужен onboarding step при первом enter room.

Эти вопросы НЕ блокируют старт Этапа 0 — backend channels строится без них.

---

## 10. История

- **2026-05-28 v0** — план создан после переименования Sonya Console → Atrium.
- **2026-05-28 v1** — после серии UX-итераций (4 версии mockup): добавлены voice mode + interrupt design + room view + collapsible reason-stream + segmented drives + dynamic theming. Этап 0 готов к старту, T0.6 substrate v20 + T0.10 tests добавлены, EVENT_SCHEMA.md создан.
