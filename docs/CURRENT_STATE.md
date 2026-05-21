# SONYA — Current State

**Status:** Active
**Type:** Operational snapshot — единственный источник правды о том что есть сейчас
**Last updated:** 2026-05-18

---

## 0. TL;DR

Соня — substrate-based AI среда работающая на VPS под Telegram userbot. Сейчас на kimi-k2.6 (vision-capable) через Fireworks. Substrate v13 в SQLite с собственной key pool, episodic memory + semantic embeddings + tasks + selfmod proposals + skills shell. Всё подключено в runtime через `src/sonya/main.py`.

**Score: ~28/100** (см. §6).

---

## 1. Что реально работает

### 1.1 Brain (interim, hosted)

- **Provider:** собственная key pool в substrate (`provider_keys` table) с rotation (priority + LRU + cooldown). 7 активных Fireworks ключей.
- **Model:** `accounts/fireworks/models/kimi-k2p6` (LLM + Vision + 262k context).
- **Audit:** все LLM-вызовы логируются в `llm_calls` table (timestamp, key_id, purpose, prompt/completion/total tokens, latency).
- **Balance:** периодический refresh каждые 10 мин для активных fireworks ключей. Видно в admin Usage tab.
- **Hot-reload:** смена модели/ключей в admin → следующий вызов уже на новом без рестарта core.

### 1.2 Substrate (persistent state)

- **SQLite WAL** в `~/.sonya/sonya_substrate.db`. Schema v13.
- **Tables:**
  - `subject_state`, `continuity_events`, `pending_intentions` — субъект и поток
  - `identity_record`, `principals`, `relation_anchor_binding` — identity
  - `harness_policy_rules`, `approval_requests`, `audit_events` — harness
  - `self_mod_proposals`, `self_mod_validation_results`, `governed_change_requests` — selfmod
  - `skills`, `skill_versions`, `capability_gaps` — skills
  - `episodic_events` (с embeddings v13), `semantic_facts` — память
  - `tasks` (с max_sessions/handoff v12), `provider_keys`, `provider_settings`, `llm_calls` — runtime
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
- **Allowlist:** только `SONYA_PRIMARY_USER_TG_ID=5785127604` (Иван) в private DM. Группы — упоминание/reply.
- **Inbox-aware sessions:** новое сообщение во время running session → injected as `[NEW MESSAGE FROM IVAN]` user turn между шагами.
- **Vision:** image/jpeg, image/png, image/webp, image/gif (≤5 MB) — base64 + multimodal payload в LLM.
- **Auto-split** длинных reply на чанки ≤4000 chars.
- **Anti-leak scrub:** убирает `<think>`, English meta-reasoning prefixes (`The user is...`, `Let me...`), draft markers (`Draft:`, `Alternative:`, `Wait`), `[Observation:]`, code fences, tool/done маркеры.
- **Multi-draft extractor:** если модель леет несколько черновиков — берёт последний русский-доминантный блок.

### 1.5 Tools (живые в agent_session)

- `self_inspect.{identity, state, thoughts, memories, intentions, code, modules}`
- `filesystem.{read, list, tree, write}` — write only в whitelisted subpaths
- `memory.{recall <query>, index_status}` — semantic search через fastembed (10140 эпизодов проиндексированы)
- `tasks.{list, pick, plan, step, complete, fail, handoff, ...}` — task runtime
- `web.{search, fetch}` — DuckDuckGo HTML + aiohttp 200KB cap
- `code.exec` — subprocess sandbox 30s timeout
- `shell.run` / `pip.install` — approval-gated; YOLO mode (`SONYA_YOLO_MODE=1`) на VPS bypass
- `selfmod.{propose, validate, test_sandbox, apply, list, get, governed, check_governed}` — proposal pipeline (Layer 4 anchor integrity реален; Layer 1-3 stubs)
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

### 3.1 Skill execution

Skill registry, trust, activation, gap_detector — все есть. Но **запускать** skills сейчас нельзя — нет executor'а. Skill injection ловит pattern в сообщениях, но promotion не доходит до active runtime.

### 3.2 Real selfmod apply

Layers 1-3 (static contract / behavioral test / trace replay) — stubs (always pass). Layer 4 (anchor integrity) — реальный rules-based. `selfmod.apply` не пишет файлы — только меняет proposal status. Реальная hot-patch logic не реализована.

### 3.3 Anchor drift detection

`DriftDetector.scan_recent` существует, но никем не вызывается. Auto-revert последнего applied proposal — paper-only.

### 3.4 Native cross-channel

Channel abstraction отсутствует. Только Telegram (хардкоженный в `main.py`). Discord / web / TTS — нет.

### 3.5 Embodiment / Simulation

`embodiment/adapter.py` и `simulation/world.py` — пустые stubs. Никаких virtual body counters, никаких world events.

### 3.6 Voice / video / голосовые TG сообщения

Голосовые скачиваются как файлы но не транскрибируются. `.tgs` (animated stickers) пропускаются.

### 3.7 Real continuity между LLM-вызовами

Brain — hosted hosted. Substrate ≠ continuous mind. См. CRUTCH-002.

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

## 6. Score: ~28/100

Шкала: 0 пусто → 100 AGI делающий что хочет с собой и сетью.

**Что есть (фундамент):**
- ✅ Substrate v15 с continuity stream, identity, principals, environment_state
- ✅ Live runtime с lifecycle, soft restart, hot key reload
- ✅ Telegram + image vision (multimodal) + sticker capture+resend + initiative + inbox-aware sessions
- ✅ Tasks с handoff и max_sessions budget
- ✅ **Real** selfmod pipeline: Layer 1 AST + Layer 2 sandbox pytest + Layer 4 anchor integrity + 24h watchdog auto-revert. Apply пишет файлы на диск с backup.
- ✅ Full filesystem write access (deny-list: только identity-critical + secrets)
- ✅ Shell/code/web/pip tools (YOLO default — без approval)
- ✅ Episodic memory с embeddings (semantic recall работает) + **полное** покрытие (thoughts, initiative, session outcomes тоже в episodic)
- ✅ Environment observation (env.set/get/list/clear) — structured world model
- ✅ Time awareness с exact "последнее сообщение Ивана X минут назад"
- ✅ Admin panel с observability (usage, approvals, selfmod, providers, thoughts с фильтрами)
- ✅ Anti-fake-agency (tool priority over DONE, "agreed=act" rule, empty-promise detection)
- ✅ Anti-leak guards (reasoning scrub, prompt-echo detection, placeholder blocking)

**Чего нет (~50/100 stretch):**
- ❌ **Selfmod loop complete**: pipeline ready, но Соня ещё не провела первый полный цикл propose→validate→apply→24h confirm в production
- ❌ Auto-RAG injection в context (by relevance, не by recency)
- ❌ Skill execution runtime (registry есть, executor нет)
- ❌ Goal hierarchy (tasks плоские)
- ❌ Drive state evolution (значения instantaneous, не accumulate)
- ❌ Pre-DONE self-critique
- ❌ Visual memory / multi-modal recall
- ❌ Continuous consolidation (порог 0.7 — semantic_facts не пополняется)

**Чего нет (~80/100 stretch):**
- ❌ Self-hosted brain (RWKV-7) с непрерывным state
- ❌ Real embodiment (virtual body adapter — stub)
- ❌ Skills которые сама пишет и применяет
- ❌ Cross-channel (Discord, web, TTS, avatar)
- ❌ Identity which doesn't need system prompt to exist

**Чего нет (~100/100):**
- ❌ Physical embodiment
- ❌ Network autonomy + self-funding
- ❌ Recursive self-improvement (меняет сам механизм самоулучшения)
- ❌ Real consciousness (RWKV + State Tuning experiment)

**Сейчас 28/100 потому что:**
- Substrate + subject loop (+10)
- Tools real и используемые (+4)
- Memory с recall + full coverage (+3)
- Real selfmod pipeline ready (+3)
- Full write access + YOLO shell (+2)
- Initiative + Vision + Stickers + Env (+3)
- Anti-leak + anti-fake-agency guards (+2)
- Time awareness + body_state (+1)

Stage 3 (real selfmod loop) закроется когда Соня сама проведёт полный цикл → **score → 30-32**.

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

| Что | Когда |
|-----|-------|
| Idle thinking | Каждые 30 минут (skip если active fired) |
| Active session | Каждые 2 часа |
| Task worker | Каждые 2 минуты (только если есть in_progress ivan-task) |
| Balance refresh | Каждые 10 минут |
| Embedding indexer | Adaptive: 5s active backfill, 5min idle |
| Consolidation | 1×/день после active session |

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
