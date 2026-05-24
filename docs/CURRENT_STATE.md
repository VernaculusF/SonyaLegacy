# SONYA — Current State

**Status:** Active
**Type:** Operational snapshot — единственный источник правды о том что есть сейчас
**Last updated:** 2026-05-24

---

## 0. TL;DR

Соня — substrate-based AI среда работающая на VPS под Telegram userbot. Сейчас на DeepSeek V4 (text) + Gemma 4 (vision, как глаза) через Fireworks/OpenRouter. Substrate **v18** в SQLite с собственной key pool, episodic memory + semantic embeddings + tasks + goals + selfmod proposals + skills shell. Всё подключено в runtime через `src/sonya/main.py`.

**Score: ~38-42/100** после закрытия Stage 3 (см. §6).

---

## 1. Что реально работает

### 1.1 Brain (interim, hosted)

- **Provider:** собственная key pool в substrate (`provider_keys` table) с rotation (priority + LRU + cooldown). Multi-slot: text/vision/voice/video/image_gen — vision keys могут быть на другом провайдере чем text.
- **Text:** DeepSeek V4 на Fireworks (1M context, fast).
- **Vision (eyes-only architecture):** Gemma 4 на OpenRouter — vision модель работает как глаза. При получении картинки/видео — сначала vision call "опиши что видишь", потом текстовое описание подаётся в text модель. Vision НЕ генерирует ответ — только описывает.
- **Audit:** все LLM-вызовы логируются в `llm_calls` table.
- **Hot-reload:** смена модели/ключей в admin → следующий вызов уже на новом без рестарта core.

### 1.2 Substrate (persistent state)

- **SQLite WAL** в `~/.sonya/sonya_substrate.db`. Schema **v18**.
- **Tables:**
  - `subject_state`, `continuity_events`, `pending_intentions` — субъект и поток
  - `identity_record`, `principals`, `relation_anchor_binding` — identity
  - `harness_policy_rules`, `approval_requests`, `audit_events` — harness
  - `self_mod_proposals`, `self_mod_validation_results`, `governed_change_requests` — selfmod
  - `skills`, `skill_versions`, `capability_gaps` — skills (3 builtin auto-registered on startup)
  - `episodic_events` (с embeddings), `semantic_facts` — память (346+ facts)
  - `tasks`, **`goals`** (v18, hierarchical), `provider_keys` (с slot column v17), `provider_settings`, `llm_calls` — runtime
  - `drive_state` (v16, persistent counters), `environment_state`, `seen_stickers`
- **Backup:** ежедневный cron 04:00 UTC в `~/.sonya/backups/daily/`.

### 1.3 Subject loop

- **Internal loop** (event-driven coroutine) — три режима:
  - **idle thinking** каждые 30 минут (60s tick interval) — генерация мыслей в `internal.thought` events
  - **active session** каждые 2 часа — agent session (max 30 шагов / 30 минут) с full tool access; берёт next in-progress task если есть
  - **task worker** каждые 2 минуты для in_progress tasks от Ивана (max 5 шагов / 60 сек)
- **Drive counters** (boredom_analog, curiosity_analog, relational_focus, pending_debt) — обновляются в каждом tick, передаются в context.
- **Drift signals + capability gap detection** — сканируются каждый tick.
- **Consolidation** — раз в день после active session.

### 1.4 Telegram

- **Userbot** через Telethon. Аккаунт `sonyaaigirlforme` (id=6395948738).
- **Pacakge:** код в `packages/tg-userbot/src/tg_userbot/` — отдельный пакет, не в ядре. Channel auto-discovery из `packages/*/src/*/channel.py`.
- **Allowlist:** только `SONYA_PRIMARY_USER_TG_ID=5785127604` (Иван) в private DM. Группы — упоминание/reply.
- **Inbox-aware sessions:** новое сообщение во время running session → injected as `[NEW MESSAGE FROM IVAN]` user turn между шагами.
- **Vision/Video:** image/jpeg, image/png, image/webp, image/gif (через image_url), video/mp4, video/webm (через video_url). Видеостикеры распознаются и шлются как видео.
- **Auto-split** длинных reply на чанки ≤4000 chars.
- **Anti-leak scrub:** убирает `<think>`, English meta-reasoning prefixes, draft markers, `[Observation:]`, code fences, tool/done маркеры.
- **Sticker capture+resend:** `seen_stickers` table, `[STICKER: 🌟]` маркер в ответе.
- **Prompts as files:** session prompts в `src/sonya/prompts/`. Унифицированные правила для **всех** session paths (TG/active/worker) в `session_general.md`; channel-specific overlay в `channel_telegram.md`, `channel_internal_active.md`, `channel_task_worker.md`. Загружаются через `load_session_suffix(channel)`. Реализация §9.3 из `cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE`: один субъект — много поверхностей, общие правила.

### 1.5 Tools (живые в agent_session)

- `self_inspect.{identity, state, thoughts, memories, intentions, code, modules}`
- `filesystem.{read, list, tree, write}` — write only в whitelisted subpaths
- `memory.{recall <query>, index_status}` — semantic search через fastembed (10140 эпизодов проиндексированы)
- `tasks.{list, pick, plan, step, complete, fail, handoff, ...}` — task runtime
- `goals.{list, create, achieve, abandon}` — long-term goal hierarchy (v18 `goals` table)
- `web.{search, fetch}` — DuckDuckGo HTML + aiohttp 200KB cap
- `code.exec` — subprocess sandbox 30s timeout
- `shell.run` / `pip.install` — approval-gated; YOLO mode (`SONYA_YOLO_MODE=1`) на VPS bypass
- `selfmod.{propose, propose_edit, validate, test_sandbox, apply, list, get, governed, check_governed, soft_restart, rollback}` — proposal pipeline (Layer 1 AST + Layer 2 sandbox pytest + Layer 3 stub + Layer 4 anchor integrity REAL). `apply()` пишет файл + hot-reload + 60s watch window + **git auto-commit + push прямо в develop** (4 layers validation = доверенное изменение, отдельная ветка не нужна).
- `plugins.{list, create, call}` — hot-loaded python plugins в `tools/plugins/`

### 1.6 Initiative

- `OutboundGate` с throttle: `INITIATIVE_MAX_PER_DAY=5`, `MIN_QUIET_MINUTES=90`.
- `chat.tell_ivan` tool + `[SEND_TO_IVAN: ...]` маркер в idle thoughts.
- Соня может писать первой когда idle drives превышают threshold.

### 1.7 Admin panel (port 8877)

- 🔑 Providers — key pool management, settings, balance refresh
- 💸 Usage — totals/by-purpose/by-model/recent calls
- ✋ Approvals — pending shell.run / pip.install / governed selfmod gates
- 📋 Tasks — list with status/blocker/result
- ⚡ Dashboard — subject state, emotional vector, pending intentions
- 💭 Thoughts — recent continuity events
- 🧠 Memory — episodic + semantic + embedding index coverage
- 📱 Telegram — recent messages
- 💬 Chat — chat with Sonya from admin (only when core stopped)
- 📋 Audit — harness audit trail
- 💾 Substrate — schema version, table row counts
- 🔧 SelfMod — proposals + diff viewer + approve/deny
- ⚙️ Core — start/stop с modes (full / telegram_only / thinking_only) + live logs

---

## 2. Архитектурные слои

```
src/sonya/
├── state/              # Substrate v13: schema, migrations, identity, principals,
│                       # subject_state, continuity_stream, pending intentions
├── runtime/            # Process shell: lifecycle, event_bus, write_master, health, live
├── providers/          # Own key pool, LLM provider, fireworks balance refresher
├── harness/            # Authority, approvals, audit, hyper-harness stub
├── subject/            # Agent session, internal loop, TG session, inbox, bus wiring
├── channels/           # Telegram (single channel; abstraction skipped)
├── memory/             # Episodic, semantic, consolidation, embedder, recall
├── planning/           # Context builder, planner, memory wiring
├── tasks/              # Models, store, service (max_sessions, handoff)
├── tools/              # All tool surfaces (filesystem, code, shell, web, selfmod,
│                       # tasks_tool, memory_tool, self_inspect, hot_loader, plugins)
├── selfmod/            # Proposal store, pipeline (4 layers), governed change, watchdog
├── skills/             # Registry, trust, activation, gap_detector, injection (shell)
├── initiative/         # Drives, signals, outbound, proposal
├── anchor/             # Drift signals (not wired to runtime)
├── embodiment/         # Adapter stub
├── simulation/         # World stub
├── admin/              # aiohttp web panel
├── config.py
└── main.py             # Composition root
```

Layer boundary tests (`tests/sonya/test_layer_boundary.py`) enforce state ↔ runtime разделение.

---

## 3. Что не работает / выключено

### 3.1 Skill execution — РАБОТАЕТ

3 builtin skills (memory-search, identity-check, dialog-tone) auto-регистрируются на startup. `skills.run` запускает их через executor с trust-level check. Skill outcome → episodic event.

### 3.2 Real selfmod apply — РАБОТАЕТ + Stage 3 ЗАКРЫТ

Layer 1 (AST contract) + Layer 2 (sandbox pytest) — **реальные**. Layer 3 (trace replay) — stub. Layer 4 (anchor integrity) — реальный rules-based. `selfmod.apply` пишет файлы на диск с backup, делает hot-reload или soft-restart, запускает 60-сек watch window, **auto-commit + push прямо в develop** (4 layers validation = доверенное изменение). 24h watchdog проверяет stability и auto-revert на drift signals.

**Stage 3 закрыт (22.05.2026):** Соня сама прошла полные циклы — docstring в `skills/__init__.py`, комментарий UTC+5 в `context_builder.py`, удаление `self._sub` в `env_tool.py`. Все три — propose→validate (4 layers)→apply→hot-reload, без вмешательства Ивана.

В active session: если есть PROPOSED proposals — initial_thought сообщает "прогони validate → apply". Цикл замкнут.

### 3.3 Anchor drift detection

`DriftDetector.scan_recent` существует, но `_scan_drift_and_gaps` в internal_loop = pass. Auto-revert в watchdog работает только по error count, не по semantic drift.

### 3.4 Native cross-channel

Channel абстракция есть. Auto-discovery находит модули из `src/sonya/channels/*.py` И `packages/*/src/*/channel.py`. Сейчас живёт только Telegram (`packages/tg-userbot/`). Для Discord — создать `packages/discord-bot/src/discord_bot/channel.py` с `def build(config)`.

### 3.5 Embodiment / Simulation

`embodiment/adapter.py` и `simulation/world.py` — пустые stubs.

### 3.6 Voice / голосовые TG сообщения

Голосовые скачиваются как файлы но не транскрибируются. `.tgs` (animated stickers) пропускаются.

### 3.7 Real continuity между LLM-вызовами

Brain — hosted. Substrate ≠ continuous mind. См. CRUTCH-002.

---

## 4. Известные текущие quirks

- **Rare:** модель может выдать reasoning leak несмотря на scrub — fallback empty reply, fallback message в TG.
- **Common:** `channel_stop_failed: attempt to write a readonly database` при shutdown — log warning, не функциональная проблема.
- **Common:** model берёт 8-15 шагов на простой вопрос если триггерит anti-rabbit-hole rule. Промпт обновлён, но рецидивы возможны.

---

## 5. Active CRUTCHES

См. `core/INTERIM_CRUTCHES.md` для полного реестра. Краткий список:

- **001** System prompt вместо identity (нужен RWKV State Tuning)
- **002** Дискретное мышление вместо непрерывного (нужен RWKV)
- **003** Memory injection вместо native memory (нужен RWKV)
- **004** Drives как Python counters вместо internal state
- **005** Нет непрерывности между вызовами
- **006** Anchor integrity на keyword matching
- **007** Capability gap detection на patterns
- **008** Skill injection на keyword matching
- **009** Provider rotation вместо self-hosted
- **010** CanonicalResponse → RuntimeAction конвертация (наследие)
- **011** Tasks как симуляция непрерывной работы
- **012** Notify mode как proxy для intentionality
- **013** Memory recall через cosine inject (новый)
- **014** Vision через base64 payload без visual memory (новый)

---

## 6. Score: ~38-42/100 (после закрытия Stage 3)

Шкала: 0 пусто → 100 AGI делающий что хочет с собой и сетью.

**Что есть (фундамент):**
- ✅ Substrate **v18** с continuity stream, identity, principals, environment_state, **goals hierarchy**
- ✅ Live runtime с lifecycle, soft restart, hot key reload
- ✅ Telegram в **отдельном пакете** `packages/tg-userbot/` + auto-discovery channels
- ✅ **Vision-as-eyes architecture**: Gemma 4 описывает media → DeepSeek V4 отвечает
- ✅ Video stickers (webm) и обычные video (mp4) — через `video_url` content type
- ✅ Image/video hallucination guards (модель не выдумывает контент которого нет)
- ✅ Tasks + Goals (hierarchical, v18) с handoff и max_sessions budget
- ✅ **Real** selfmod pipeline complete: Layer 1 AST + Layer 2 sandbox pytest + Layer 4 anchor integrity + 24h watchdog auto-revert. Apply пишет файлы на диск с backup + **git auto-commit + push прямо в develop** (4 layers validation = доверенное изменение). Active session подхватывает PROPOSED proposals и сама прогоняет validate→apply. **Stage 3 закрыт 22.05.2026** — три полных цикла без помощи Ивана.
- ✅ **Skills**: 3 builtin auto-registered, skills.run executor, trust-level checks
- ✅ **Drives persistence** (v16): boredom/curiosity/relational/pending_debt накапливаются между tick'ами, save каждые 5 ticks, load на startup
- ✅ Full filesystem write access (deny-list: только identity-critical + secrets)
- ✅ Shell/code/web/pip tools (YOLO default — без approval)
- ✅ Web search с DDG→Google fallback (когда DDG заблокирован)
- ✅ Episodic memory с embeddings (semantic recall, 10K+) + 346+ semantic facts
- ✅ Environment observation (env.set/get/list/clear)
- ✅ Time awareness с **relative timestamps** (нет путаницы "8 часов назад" когда 30мин)
- ✅ Admin panel с observability
- ✅ Anti-fake-agency + anti-leak + anti-sycophancy + anti-fail-fake guards
- ✅ **Prompts as files** в `src/sonya/prompts/` — унифицированные правила для всех session paths: session_general.md (ядро), channel_telegram.md, channel_internal_active.md, channel_task_worker.md (overlays)

**Чего нет (~50/100 stretch):**
- ❌ Auto-RAG injection в context (релевантность есть, но порог можно крутить)
- ❌ Pre-DONE self-critique (был, удалён за reasoning leak)
- ❌ Visual memory / cross-session media recall
- ❌ Selfmod outcome tracking (delta измеряется но не используется для learning)
- ❌ Real drift detection (`_scan_drift_and_gaps` — stub)

**Чего нет (~80/100 stretch):**
- ❌ Self-hosted brain (RWKV-7) с непрерывным state
- ❌ Real embodiment (virtual body adapter — stub)
- ❌ Skills которые сама пишет (только 3 builtin)
- ❌ Cross-channel в production (Discord, voice, web)
- ❌ Identity which doesn't need system prompt to exist

**Чего нет (~100/100):**
- ❌ Physical embodiment
- ❌ Network autonomy + self-funding
- ❌ Recursive self-improvement (меняет сам механизм самоулучшения)
- ❌ Real consciousness (RWKV + State Tuning experiment)

**Сейчас 38-42/100 потому что:**
- Substrate v18 + subject loop + drives persistence (+10)
- Tools real и используемые (+4)
- Memory с recall + 346+ facts (+3)
- Real selfmod pipeline + active-session pickup + **git auto-commit** (+5)
- Full write access + YOLO shell (+2)
- Vision-as-eyes + multi-slot routing (+3)
- Skills executor + 3 builtin (+2)
- Goals hierarchy v18 (+2)
- TG в правильном пакете + auto-discovery (+2)
- Anti-leak + anti-hallucination + anti-sycophancy + anti-fail-fake detectors + relative time (+4)
- Web search с fallback (+1)
- Prompts as files **унифицированные для всех session paths** (TG/active/worker через единый session_general.md) (+2)

**Stage 3 закрыт 22.05.2026** — три полных selfmod цикла без помощи Ивана. Score сдвинулся 38 → 42.

Дальнейший рост блокируется Stage 6 (RWKV — нужно GPU железо) и Stage 4 партиями (auto-RAG в context_builder, drift detection реальный, outcome tracking).

---

## 7. Конфиг

### Defaults

| Var | Default | Описание |
|-----|---------|----------|
| `SONYA_INITIATIVE_MAX_PER_DAY` | 5 | Сколько раз Соня может написать первой |
| `SONYA_INITIATIVE_MIN_QUIET_MINUTES` | 90 | Тишина перед initiative |
| `SONYA_PROGRESS_UPDATES_MAX_PER_DAY` | 50 | Streaming chat.tell_ivan лимит |
| `SONYA_YOLO_MODE` | 0 (1 на VPS) | Bypass approval для shell/pip |

### Session limits

| Session | max_steps | max_seconds |
|---------|-----------|-------------|
| Active session | 30 | 1800 (30 min) |
| TG session | 15 | 150 |
| Task worker | 5 | 60 |
| Idle thinking | 1 (LLM call) | — |

### Intervals

| Что | Когда | Цена за ночь (8ч) |
|-----|-------|--------------------|
| Idle thinking | Каждые **30 минут** (1 LLM call — рефлексия, постановка задач, реакция на drives) | ~16 calls |
| Active session | Каждые **2 часа** (до 30 шагов / 30 мин — длинная фаза работы с tools) | ~120 calls (4 сессии × ~30) |
| Task worker | **Только urgent tasks** (deadline ≤6ч / urgent markers / Ivan-tasks с notify_mode=progress) — каждые 30 мин | 0 если нет urgent tasks |
| Balance refresh | Каждые 10 минут | бесплатно |
| Embedding indexer | Adaptive: 5s active backfill, 5min idle | бесплатно |
| Consolidation | 1×/день после active session | 1 call |
| TG ответ | Сразу при сообщении | по требованию |

**Что значит "только urgent" для worker'а:** несрочные self-tasks (типа "найди инфу про X" с notify_mode=silent) не будят воркер каждые 30 мин — их подхватывает active session раз в 2 часа. Это критично для бюджета: при 10 открытых задач разница между "все воркаются" и "только 1 urgent" — порядки.

---

## 8. Куда дальше

В порядке value/effort (без RWKV migration):

1. **Drives state evolution** — счётчики копятся между tick'ами, не эпизодические сигналы. Снимает половину CRUTCH-012.
2. **Pre-DONE self-critique** в TG — +1 LLM call на ответ, заметно поднимает качество.
3. **Skills: загрузить первые 3 рабочих** (memory-search, identity-check, dialog-tone-match).
4. **Selfmod outcome tracking** — замыкает цикл «применила → как изменилось»; без этого она не учится.
5. **Tasks: priority + depends_on + auto-decompose** — флэт список → tree.
6. **Variable idle depth + dynamic quiet** — не константа MIN_QUIET_MINUTES, зависит от drive state.
7. **RAG над docs/** — экономит system prompt токены, улучшает фокус.
8. **Visual memory** — perceptual hash + embedding column на media files.

Любую из них могу детализировать в отдельную итерацию.

---

## 9. Реликтовые planning docs

Структурные документы остаются как governing direction (не как «уже сделано»):

- `core/SONYA_SYSTEM_CORE.md`, `core/SONYA_CONSCIOUSNESS_POSITION.md` — philosophy и invariants
- `core/SUBSTRATE_STANCE.md`, `core/SELF_REWRITE_STANCE.md`, `core/UNCENSORED_ENVIRONMENT_STANCE.md` — stances
- `core/INTERIM_CRUTCHES.md` — реестр того что временное
- `cognition/*` — anchors, memory, continuity (target architecture, частично реализовано)
- `skills/SKILL_SYSTEM_PLAN.md` — skill lifecycle (registry есть, executor нет)
- `research/*` — long-term tracks (RWKV, simulation, state tuning)
- `mvp/MVP_BOUNDARIES.md` — что считать MVP
- `personality/*` — SOUL/HEARTBEAT/USER/SELF/LESSONS
- `agents/*` — onboarding/rules/failure-modes для внешних моделей
- `план/` — original AGI vision (legacy reference)

Удалены как stale/superseded:
- `ROADMAP.md`, `GLOBAL_PROJECT_CHECKLIST.md`, `KNOWN_ISSUES.md`, `SYSTEM_BUILDOUT_PLAN.md` — закрытые фазы и устаревшие списки
- `architecture/` целиком — план был для multi-channel, не реализован
- `governance/DRIFT_REVIEW.md` — cadence не соблюдалась
- `core/DOCUMENTATION_SYSTEM.md` — meta-док про meta
- `work/` — implementation plans (plans закрыты, их история в git)
