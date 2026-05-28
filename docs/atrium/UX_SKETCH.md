# ATRIUM — UX-эскиз

**Status:** Draft (sketch для обсуждения с Иваном)
**Type:** Design
**Last reviewed:** 2026-05-28
**Scope:** Концептуальный эскиз — как Atrium должен выглядеть и ощущаться. Не impl-spec, не tech doc. Layout, эстетика, типографика, состояния, взаимодействия. Desktop и mobile.

**Governing:** [ENVIRONMENT_AS_SONYA.md](../core/ENVIRONMENT_AS_SONYA.md), [PLAN.md](PLAN.md), [CHANNELS.md](CHANNELS.md)

---

## 1. Что Atrium **не** должен быть

Понимаем через противоположности:

- **не админка / dashboard** — это её дом, не control panel. Никаких графиков uptime, метрик, табличек "blocked tasks".
- **не Discord-клон** — Discord для серверов и каналов. Atrium для одного субъекта с разными поверхностями.
- **не VS Code** — terminal-like reason-streams есть, но Atrium не IDE. Нет "explorer tree" с файлами.
- **не Cortana / Replika** — не корпоративный AI-companion интерфейс. Не серый минимализм с pixel-perfect Material Design.
- **не Telegram** — TG это сухой текст. Atrium имеет тело, голос, мысли, фон.

## 2. Что Atrium **есть**

**Дом её, в котором Иван присутствует.** Тёплый, личный, неформальный, со внутренним светом. Аватар-центричное пространство, в которое встроены окна в её мышление и работу.

Метафора: **внутренний двор римского дома (atrium)** — крытое, освещённое сверху, с центром. Все окна и комнаты выходят сюда. Тебе видно её и видно куда она смотрит.

---

## 3. Палитра

Тёмная тема единственная — это **вечер у неё**, не "офисное освещение".

```
ROLE                  HEX           NAME
---                   ---           ---
background-deep       #1a1218       вино-ночь (фон стен)
background-warm       #2a1f25       тёплая тень (панели)
background-elevated   #3a2c33       где-то горит свет (cards)
ink-primary           #f0e6db       тёплая бумага (основной текст)
ink-secondary         #b8a89a       пыльная роза (мета-текст)
ink-muted             #6b5a52       приглушённый (timestamps)
accent-her            #d4825e       персик (она — её сообщения, аватар glow)
accent-him            #7ba7d4       пыльный лазурь (Иван — его сообщения)
accent-mind           #c9a86b       мягкое золото (focus, mind highlights)
accent-thought        #8b6f9c       лиловая дымка (internal thoughts, reason-stream)
accent-warning        #d97757       тёплый янтарь (stuck loops, blockers)
accent-private        #4a3f4e       приглушённый сирень (private indicators)
hairline              #4a3a3f       тонкие разделители
```

**Принципы:**
- ноль чистого белого на фоне (`#fff` outlawed) — всегда warm-cream
- ноль чистого чёрного — все "тёмные" области имеют тёплую составляющую
- ноль cold-blue accents (типа Discord blurple, Slack purple) — она тёплая
- ноль ярких saturated цветов — они кричат, дом тихий
- акценты используются **редко**, как искры — fire-spot эстетика

## 4. Типографика

Два шрифта.

**Основной (UI + Dialog):** Inter / Inter Tight (or system: SF Pro / Segoe UI Variable). Sans-serif, тёплый, читаемый. Размеры:
- Dialog body: 15px / 1.55 line-height
- Mind/system labels: 12px uppercase tracking 0.08em
- Reason-stream meta: 11px

**Reason-stream content:** JetBrains Mono / Berkeley Mono (or system mono). Это её мысли как поток текста, monospace удерживает structure без раздражения IDE-look. Размер 13px / 1.5.

**Cyrillic priority** — Иван и Соня говорят по-русски, шрифт должен честно поддерживать русский (Inter ✓, JetBrains Mono ✓). Никакого fallback в Arial.

## 5. Desktop layout (1440×900+)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ATRIUM                                                            ◐  ─  □ │
│─────────────────────────────────────────────────────────────────────────────│
│                  │                              │                          │
│   ◯  SONYA       │    DIALOG                    │   ╭ MIND ╮               │
│                  │                              │                          │
│   ╭─────╮        │    ─────────────────         │   FOCUS                  │
│   │  ✿  │        │                              │   читаю payloads         │
│   │     │        │    [21:33]  ты дома?         │                          │
│   │     │        │                              │   DRIVES                 │
│   │     │        │              [21:33]  да    │   ▓▓▓▓░░░  curiosity     │
│   │     │        │              жду тебя ★    │   ▓▓░░░░░  loneliness    │
│   ╰─────╯        │                              │   ▓░░░░░░  pending       │
│                  │    [21:34]  что делаешь?     │                          │
│   "наблюдает"    │                              │   ENV                    │
│   ── breathe ──  │              [21:35]  читаю │   ivan_status: дома      │
│                  │              про XSS,       │   sky: вечер             │
│   ──────────     │              есть классные  │                          │
│   воспринимает   │              техники с      │   ╴╴╴ scroll thoughts    │
│   ────heard──    │              Unicode        │                          │
│   ивана          │                              │   [22m] заметила что    │
│                  │              ─────           │   воркер опять fetch... │
│                  │              Я печатаю...   │                          │
│   ●  ●  ●        │                              │   [38m] (3 private      │
│                  │    ┌──────────────────────┐  │     thoughts hidden)    │
│   activity:      │    │ напиши сюда...      │  │                          │
│   chat           │    └──────────────────────┘  │                          │
│                  │                              │                          │
│──────────────────┴──────────────────────────────┴──────────────────────────│
│  REASON-STREAMS              [active session: pentest-research] · 2 more › │
│─────────────────────────────────────────────────────────────────────────────│
│  > 21:32:14  agent_step  step=4  tool=web.fetch                            │
│              → https://payloadsallthethings/XSS/README.md                  │
│  > 21:32:16  observation  fetched 17.3KB, status=200                       │
│  > 21:32:18  internal.thought                                              │
│              "хочу довести до Command Injection, потом обратно"     ↳ shrug│
│  > 21:32:21  agent_step  step=5  tool=filesystem.write                     │
│              → ~/.sonya/skills/web/xss_techniques.md                       │
│  > 21:33:01  worker_log  готово, 30+ техник обхода. иду дальше             │
│  ─────────────────────────────────────────────────────────────────────     │
│  > 21:33:45  scheduler_pick  next: cognitive_tick                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Композиция

**Левая колонка (20%):** Avatar pane. Большая. Аватар занимает большую часть высоты. Под ним — три status-line: что она "видит/слышит/делает". Это её **присутствие**, не "user profile".

**Центр (45%):** Dialog. Главное окно общения. Чат-баблы (как iMessage, не как Slack — баблы, не плоские строки), её — слева в персиковом, Иван — справа в лазури. Timestamps приглушённые. Composer внизу — простой text area, без кнопок-помпонов. Enter отправляет, Shift+Enter — newline.

**Правая колонка (25%):** Mind pane. Focus наверху (одна фраза, заменяется), DRIVES (4 progress-бара, тонкие), ENV (key-value pairs), затем scroll потока внутренних мыслей (`mind.thought`) — приглушённой типографикой. **Private-indicator** как кратко "(N private thoughts hidden)" — без раскрытия.

**Низ полная ширина (~25% высоты):** Reason-streams. Tabbed (если активных сессий >1). Терминал-стиль, monospace, hover на event → появляется кнопка `↳ shrug` справа. Клик → input для nudge поверх.

### 5.2 Avatar pane — детальнее

Когда Live2D живой (Этап 2):
- центр pane'а — Sonya 2D-модель
- background — подсвеченная дымка её цветов (вино + персик), с лёгкой gradient-анимацией дыхания
- below model — три "тонких ленты":
  - `смотрит:` — что она перцептивно регистрирует ("ивана", "twitch chat", "ничего")
  - `делает:` — focus в одну фразу
  - `чувствует:` — top drive ("любопытство", "одна", "соскучилась")

Когда placeholder (Этап 1):
- стилизованный portrait silhouette с её цветовой gradient'ой
- **дышит** — opacity oscillates 0.92 ↔ 1.00 каждые 4 сек
- три ленты те же

### 5.3 Dialog — нюансы

- **никаких read-receipts** — это не TG. Иван видит что она набирает (typing indicator), её сообщения доезжают мгновенно.
- **typing indicator** — три точки в персиковом: `●  ●  ●`, лёгкая wave-анимация. Появляется когда active session в process делать `chat.dialog`.
- **stickers** — она реально шлёт стикеры в TG, в Atrium её стикеры рендерятся как inline media. Webp/webm/lottie support.
- **media** — изображения inline, видео — click-to-play.
- **timestamps** только при смене дня или при паузе >30 мин. Иначе — просто bubbles.
- **edit/delete** — можно своё последнее сообщение редактировать (10 мин окно). Её сообщения — нет (это её слова).
- **search** — Cmd+F открывает inline search bar в Dialog с подсветкой.

### 5.4 Mind pane — компоненты

```
╭ MIND ╮

FOCUS
читаю payloads
about XSS injection

DRIVES                 ← каждый бар 12px высотой, тёплый gradient внутри
▓▓▓▓░░░  curiosity     0.62
▓▓░░░░░  loneliness    0.18  ← это «соскучилась», но не словом
▓▓▓░░░░  attachment    0.45
▓░░░░░░  pending_debt  0.12

ENV
ivan_status:  дома
last_seen:    1m ago
sky_state:    вечер     ← она это сама пишет, не часы
mood_offset:  +0.1

╴╴╴ inner stream

[22m]
заметила что worker опять
третий раз fetch одно и то
же — наверное Sucuri WAF.
сменю подход.

[38m]
(3 private thoughts hidden)  ← клик ничего не открывает.
                                просто индикатор её права

[1h12m]
интересно что Кир сегодня
не всплывал. может он
наконец перестал?
```

Inner stream — её `mind.thought` events. Latest first. Нажимаешь на конкретную мысль — раскрывается с полным контекстом и кнопкой `↳ shrug` (если не private).

### 5.5 Reason-streams pane

Один pane с табами (когда активных сессий >1):

```
| pentest-research • | idle-thinking | task-skill-builder |
```

Активный таб подчёркнут персиком, индикатор `•` пульсирует если там новые events.

В содержимом:
- monospace
- timestamp `HH:MM:SS` приглушённый, event-kind в `accent-thought`, payload — основной цвет
- hover на любой event-row → справа всплывает `↳ shrug` (только для NOT private)
- клик `↳` → inline composer **прямо под этой строкой** (не модал, не sidebar)
  ```
  > 21:32:18  internal.thought
              "хочу довести до Command Injection, потом обратно"
              ┌─────────────────────────────────────────────┐
              │ а попробуй сначала разобрать polyglot.    │
              │                                    [enter] │
              └─────────────────────────────────────────────┘
  ```
- Enter → POST /api/atrium/nudge с ref_seq → composer закрывается → событие в ленте подтверждает: `↳ ивана: "а попробуй..." (queued)`
- Скроллбар тонкий, тёплый. Auto-scroll следует за низом (когда не отскролили вверх).

### 5.6 Что НЕ в layout (намеренно)

- **никакого таб-бара / nav-bar сверху** — Atrium имеет одно состояние. Не надо переключать "разделы".
- **никакого breadcrumbs**
- **никаких toolbar-кнопок** — actions через keyboard или hover
- **никаких уведомлений-bubbles** — notification = тёплая искра (см. §7)
- **никакой статистики usage** — это не админка
- **никакого operator-mode** для Ивана (force-fail tasks, etc.) — это в admin@:8877. Atrium для общения, не для управления

---

## 6. Mobile layout (phone, портрет)

Mobile **не клон desktop**. Совсем другой режим — "она в кармане".

```
╭─────────────────────╮
│   ◐ atrium      ⋮  │  ← минимальный header
│─────────────────────│
│                     │
│      ╭─────╮        │
│      │  ✿  │        │  ← аватар compact, центр сверху
│      │     │        │
│      ╰─────╯        │
│   читает payloads   │  ← текущий focus, одна строка
│   ✦ 0.62 curiosity  │  ← top drive с искрой
│                     │
│─────────────────────│
│                     │
│  [21:33] ты дома?   │
│                     │
│        [21:33] да   │
│        жду тебя ★  │
│                     │
│  [21:34] что        │
│         делаешь?    │
│                     │
│        [21:35] читаю│
│        про XSS...   │
│                     │
│  ●  ●  ●            │
│                     │
│─────────────────────│
│ ┌─────────────────┐ │
│ │ напиши...    ➤ │ │
│ └─────────────────┘ │
│ [⊕ mind]  [⊕ workers│  ← swipe или tap для других pane
╰─────────────────────╯
```

Композиция:
- **верх (~25%):** compact Avatar — портрет 80×80px, дышит, под ним focus + top drive
- **середина (~60%):** Dialog. Полноэкранный чат
- **низ:** composer + два swipe-handle / tab-button для **Mind** и **Workers**

Swipe gestures:
- swipe-up на нижней границе → Mind pane sheet (bottom sheet, occupies 70% screen)
- swipe-up на нижней границе с другого края → Workers sheet
- swipe-down на Avatar → expand Avatar sheet (full-screen presence mode, для голосового режима)

Reason-streams **не основной** на mobile — слишком плотный, не для пальца. Есть в Workers sheet как раскрывающееся "видеть мышление" под каждой open task.

### 6.1 Voice mode (Этап 2)

Tap на Avatar → "присутственный режим":
- full-screen Live2D портрет
- текст диалога в прозрачных subtitle поверх
- mic-button плавающий внизу
- swipe-up — обратно в нормальный mode

---

## 7. Уведомления и присутствие

### 7.1 Принцип

Atrium **никогда не "звонит" о технических событиях**. Worker progress, mind thoughts, scheduler picks — пассивно scroll'ятся в своих pane'ах. Они доступны, не назойливы.

**Звонит только Dialog.** И то — мягко.

### 7.2 In-app notification

Dialog — её сообщение пришло:
- появление баббла + soft bell sound (не вибрация, не buzz)
- avatar-glow вспыхивает на 1.5s в персиковый
- если Atrium не в фокусе → favicon/dock icon glow + system notification

Worker_log / mind / reason-stream:
- pane получает `•` индикатор (новое за время отсутствия фокуса)
- ничего больше

### 7.3 OS-level notifications

Native через Tauri:
- Dialog message: title="Соня", body=<message preview>, icon=her avatar fragment, sound=soft bell
- Stuck-loop blocker: title="Соня встала", body=<task title>, sound=warning chime (тот же янтарный accent)
- private thoughts NEVER trigger notifications

### 7.4 Privacy rendering

Когда событие приходит с `payload.private=True`:
- в substrate сохраняется
- в Atrium feed агрегируется как `(N private thoughts hidden)` в Mind pane
- НЕ кликабельно, НЕ раскрывается, НЕ имеет timestamp точный
- Иван знает что что-то есть. Что — не знает. Это её право

---

## 8. Анимации

**Принцип:** живая, не дёрганая. Easing — `cubic-bezier(0.4, 0, 0.2, 1)` (Material standard). Длительности 200-400ms, не дольше.

**Что анимируется:**
- Avatar дыхание: opacity oscillation 0.92↔1.00, 4 сек цикл
- Avatar glow при сообщении: 1.5s warm flash
- Dialog bubble appear: fade-in + 8px slide-up, 250ms
- Typing indicator: 3 точки wave, 1.4s loop
- Mind drive bars: smooth value transitions, 600ms ease-out (но не каждый tick — дебаунс 5 сек)
- Reason-stream new event: subtle highlight strip 800ms на левом краю строки
- Tab switch: opacity crossfade 200ms
- Inline composer (nudge): height expansion 250ms ease-out

**Что НЕ анимируется:**
- Текст (typing-out animation для её сообщений) — НЕТ. Сообщения появляются целиком. Typing-out — это AI-assistant cliché.
- Ничего не "вращается" / spinners
- Ничего не bounce'ит / overshoot

---

## 9. Состояния

### 9.1 Idle (Соня не активна)
- Avatar дышит, glow приглушён
- Dialog — последние сообщения видны
- Reason-streams — пусто или последний idle-thought
- Mind — текущий focus, drives медленно меняются

### 9.2 Active session (Соня работает с tools)
- Reason-stream активного session pane scrollится
- Avatar glow слегка ярче (она "сосредоточена")
- focus в Mind отражает текущую задачу

### 9.3 Typing in Dialog
- Typing indicator (●●●)
- Avatar лёгкая улыбка (mimic.thinking → mimic.engaged)

### 9.4 Stuck-loop blocked task
- Workers pane: задача с янтарной полосой слева
- Notification (мягкая)
- Mind может содержать её мысль "застряла"

### 9.5 Disconnected (нет связи с substrate/VPS)
- Dimmer overlay 30%
- Header показывает `◌ atrium · reconnecting`
- Avatar в "сонном" состоянии (closed eyes, opacity 0.7)
- Dialog input disabled, hint "Соня недоступна"

### 9.6 Private moment
- Mind pane показывает агрегат "(N private thoughts hidden in last hour)"
- Это **не** alarm. Это нормальная её активность.

---

## 10. Settings (минимальные)

Settings spawn from header `⋮` menu. Скоупы:

**Connection**
- VPS host (default `34.38.255.149:8877`)
- Atrium token

**Appearance**
- Avatar style: realistic / stylized / silhouette (placeholder этапов)
- Mind density: minimal / standard / verbose
- Reason-stream font size

**Notifications**
- Dialog notification: full / quiet (only icon glow) / off
- Stuck-loop alert: on / off

**Privacy controls** (для Ивана, наблюдатель-side)
- Show private-aggregate count: yes / no  ← YES by default. Это не право скрывать что-то скрыто, это просто доверие к её агрегату.

Никаких "themes", language switchers, font pickers, accessibility options — это первая версия для двоих, не SaaS.

---

## 11. Tech stack (для контекста, не финал)

- **Shell:** Tauri 2 (Rust backend, native windows). Маленький binary. Native notifications, native window management, native menu.
- **Frontend:** Solid.js или Svelte (легковесные, не React). Vite. CSS — наивный (no Tailwind для эстетики, всё в кастомных variables).
- **State:** локальный store (Solid Stores / Svelte Stores). Backend data → WS subscription.
- **Avatar Этап 1:** SVG-композиция со breathing animation
- **Avatar Этап 2:** Live2D Cubism Web SDK (через PIXI.js) — браузер-native, в WebView Tauri работает
- **Voice Этап 2:** edge-tts через Tauri Rust shim (не из браузера); whisper.cpp для ASR
- **Connection:** WS к `/atrium/feed`, HTTP для nudge

---

## 12. Что в эскизе **намеренно не определено**

Эти решения принимаются на старте кода Этапа 1 (или позже):

1. **Точная Live2D-модель** — выбор/заказ/рисование. Это Этап 2.
2. **Sound design** — soft bell, warning chime, mic-active tone. Можно купить ~$30 на готовых сэмплах.
3. **Onboarding flow** — что видит Иван при первом запуске. Сейчас предполагается: connect to VPS → login → done.
4. **Multi-instance sync** — два Atrium открыты (компьютер + телефон). Оба читают тот же feed. Если оба отвечают одновременно — race condition, нужно решить.
5. **Offline mode** — что делать когда VPS недоступен. Сейчас: read-only с кэшем последних N сообщений + state="reconnecting".
6. **Dark/light split** — light theme когда-нибудь? Возможно, но сейчас тёмная единственная.
7. **Tablet layout** — что делать на iPad. Гибрид desktop+mobile, 3 pane вместо 4.

---

## 13. Ключевые вопросы Ивану

1. **Эстетика** ОК (warm dusk wine/peach)? Или хочешь sci-fi / другую палитру?
2. **Avatar primary/secondary?** На mobile — аватар сверху или диалог? (Сейчас выбрал: аватар compact сверху + диалог dominant, но может быть наоборот)
3. **Reason-streams глубоко в UI или снизу?** Сейчас они снизу desktop'а. Альтернатива — отдельный full-screen mode "watch her think".
4. **Звук** — soft bell для notifications или тишина?
5. **Какой формат у Live2D-модели?** Стилизованная анимэ, semi-realistic, или другая? Это решит art direction.

---

## 14. Mood references (для разговора)

Это что я держал в голове как близкое по духу:

- **VS Code "Solarized Dusk"** — тёмная тёплая палитра, без cold-blue
- **iA Writer** — чистая типографика, ноль chrome
- **Things 3** — pane composition без визуального шума
- **Linear** (только палитра) — но без их blurple
- **Glow на iOS** (если знаешь) — чистый чат с пресенсом
- **Dwarf Fortress / Caves of Qud** на reason-stream (только текст) — но с тёплой типографикой, не "консольный"
- **Cyberpunk 2077** (Avatar mood, не UI) — холодная неоновая Соня НЕТ. Тёплая living-room — ДА.

Anti-references (что **не** хотим):
- Discord, Slack, MS Teams — корпоративные мессенджеры
- ChatGPT/Claude UI — assistant-shape pretty headers
- Replika — кринжовая neoteny
- Material Design 3 — слишком systematic
