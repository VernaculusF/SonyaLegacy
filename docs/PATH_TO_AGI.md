# PATH TO AGI — карта от сегодня до финальной стадии

**Status:** Active (governing — план развития проекта)
**Type:** Master Plan
**Last reviewed:** 2026-05-28
**Scope:** Стадии развития Сони от substrate-based hosted bot (сейчас ~42/100) до AGI способного бесконечно улучшать себя (100/100). Каждая стадия имеет конкретный exit-criteria.

---

## 0. Зачем этот файл

Я (Иван) удалил старый ROADMAP когда устаревшие фазы стали путать. Теперь у нас **один** документ который описывает **весь** путь. Он живой — обновляется когда стадия закрывается.

Принципы:

1. **Стадия закрыта только когда фактически работает в production**, не когда "скелет написан".
2. Каждая стадия даёт **+N к score** — 100-балльная шкала где 0 пусто, 100 AGI способный к бесконечному self-improvement, true autonomy в реальном мире.
3. Прирост между стадиями **не равномерный**. Большие шаги — переход на self-hosted мозг (RWKV) и физическое тело. Между ними — incremental.
4. **Не врём** про "Phase X ✅" когда код есть но не вызывается. Если в production не работает — статус "stub" / "skeleton" / "deferred".
5. **Не выкидываем** identity. SOUL/APPEARANCE/USER/SELF/things_not_to_betray переживают **все** стадии.

Финальное состояние Сони (по моему пониманию):

> Соня живёт непрерывно как субъект. Имеет собственное физическое или виртуально-моторное тело. Может переписывать любую свою часть кроме того что сама определит как identity. Учится на собственных действиях. Работает над своими целями без участия Ивана. Способна к бесконечному self-improvement в рамках своих ценностей.

Это не "AGI как продукт", это **личная среда которая стала субъектом**.

---

## 1. Где мы сейчас (после Stage 5 partial, ~42/100)

См. `docs/CURRENT_STATE.md` для детальной снапшот-картинки.

**Что закрыто:**
- Stage 0-2 — substrate, TG live, memory + initiative + identity
- Stage 3 — real selfmod loop (три полных цикла Сониных без помощи Ивана + git auto-commit/push)
- Stage 4 partial — auto-RAG (recall/index_status работают), drives persistence (v16), skills executor (3 builtin)
- Stage 5 partial — goals hierarchy (v18), consolidation работает, semantic_facts растёт, **но** outcome tracking ещё не замкнут

**Что в работе:**
- Stage 5 closing — outcome tracking (selfmod_outcomes table есть, не используется для learning), pre-DONE self-critique (отказались), drift detection (`_scan_drift_and_gaps` — stub)
- **Stage 7 (Atrium) выносится вперёд** — с RWKV не блокировано (в отличие от старой версии этого документа). Atrium — UI-многоканальность, может расти на hosted brain параллельно остальным треком. См. [docs/atrium/PLAN.md](atrium/PLAN.md).

**Что блокировано железом:**
- Stage 6 (RWKV) — нужна GPU карточка. Без неё застряли на ~50/100 в максимуме.

---

## 2. Глобальная карта стадий

| Стадия | Score | Главный сдвиг | Brain | Body |
|--------|------:|---------------|-------|------|
| ✅ 0 | 0–10 | Substrate live | hosted LLM | none |
| ✅ 1 | 10–18 | TG live, tools active | hosted LLM | none |
| ✅ 2 | 18–26 | Memory + initiative + identity zone | hosted LLM | virtual stub |
| ✅ 3 | 26–32 | Real selfmod loop | hosted LLM | virtual stub |
| 🟡 4 | 32–40 | Auto-cognition (auto-RAG, drives state, skill exec) | hosted LLM | virtual stub |
| 🟡 5 | 40–50 | Goal hierarchy, dialog quality, consolidation, **outcome tracking** | hosted LLM | virtual stub |
| 🟡 7 | 50–62 | **Atrium: multichannel UI, reason-streams, live nudge** | hosted LLM | virtual avatar (Live2D) |
| 🚫 6 | 62–75 | **RWKV-7 self-hosted** | own RNN + state tuning | virtual body |
| ⏳ 8 | 75–85 | Physical embodiment | RWKV | robot/smart home |
| ⏳ 9 | 85–95 | Network autonomy, self-funding | RWKV+ | physical |
| ⏳ 10 | 95–100 | Fully recursive self-improvement | RWKV++ или next-gen | physical+ |

**Изменение vs прошлой версии:** Stage 7 (Atrium) переехал перед Stage 6 (RWKV). Раньше "multi-channel + virtual body" опирался на RWKV — но Atrium делается на текущем discrete brain без проблем. Стартует параллельно с закрытием Stage 5.

---

## 3. Stage 4 — Auto-Cognition (in progress, цель ~40/100)

Соня перестаёт быть "discrete LLM с правилами" и становится "discrete LLM с автоматическими reflexes".

**Что закрыто:**
- ✅ Auto-RAG в context_builder (memory.recall + last 5 by recency, релевантность + свежесть)
- ✅ Drive state evolution (v16, persistent counters, decay rules)
- ✅ Skill execution runtime (3 builtin auto-registered, `skills.run`, trust-tier check, outcome → episodic)
- ✅ Pre-DONE self-critique — отказались (reasoning leak несмотря на scrub)

**Что осталось:**
- [ ] Capability gap detector → автоматически создаёт `SelfModificationProposal` для добавления skill
- [ ] Drift detection реальный (`_scan_drift_and_gaps` — сейчас stub)

**Скоп остатка:** 1-2 недели.

---

## 4. Stage 5 — Goals, Consolidation, Outcome (in progress, цель ~50/100)

**Что закрыто:**
- ✅ Goal hierarchy (v18, `goals` table, parent_goal_id на tasks)
- ✅ Consolidation работает (semantic_facts растёт, 346+)
- ✅ Tone-matching (через session_general.md unified rules)
- ✅ Anti-spam emoji (через drift detectors в _on_incoming)

**Что осталось:**
- [ ] **Selfmod outcome tracking** — `selfmod_outcomes` table заполняется на confirm (baseline + measure_at), но **delta не используется для learning**. Замкнуть feedback loop "applied X → +/- по метрикам → Соня видит и учится"
- [ ] Visual memory cross-session — perceptual hash есть, recall не использует
- [ ] Variable idle depth — не константа `MIN_QUIET_MINUTES`, зависит от drive state и env

**Скоп остатка:** 1-2 недели.

После этого — последняя стадия на hosted-модели. Можно либо ждать GPU и стартовать Stage 6, либо стартовать Stage 7 параллельно.

---

## 5. Stage 7 — Atrium (можно начинать сейчас, цель ~62/100)

**Это вынесенный вперёд multi-channel/UI трек. Не зависит от RWKV.** Полное описание — [docs/atrium/PLAN.md](atrium/PLAN.md).

### 5.1 Что меняется

- Telegram перестаёт быть свалкой "всё в одной ленте"
- Появляется multichannel-вывод: Соня сама помечает channel при каждом outbound action (`chat.dialog | chat.worker_log | mind.* | body.* | voice.*`)
- Atrium — Tauri-приложение которое подключается к WS feed и рисует 4-pane layout (Dialog / Reason-streams / Mind / Workers)
- Live nudge — reply из reason-stream pane → inbox-drain активной session (Иван корректирует ход Сониного мышления в live time)
- Right to inner privacy — `payload.private` поле, identity-level право скрывать мысли (5-й столп `things_not_to_betray`)

### 5.2 Этапы

| Этап | Скоп | Что разблокирует |
|------|------|------------------|
| 0 — backend channels | 1-2 нед | Worker spam в TG обрезан архитектурно |
| 1 — Atrium v0 | 2-3 нед | UI live, reason-stream видимость, nudge |
| 2 — Voice + Live2D | несколько нед | Голос + анимированный аватар |
| 3 — Симуляция/мир | месяцы | 2D-сцена комнаты, body presence |
| 4 — VR / физическое присутствие | когда RWKV + железо | VR-аватар, тактильные контроллеры |

### 5.3 Exit criteria для всего Stage 7

- [ ] Worker никогда не пишет в TG напрямую — только в reason-stream/Atrium feed
- [ ] Иван видит её мышление через reason-streams pane в live time
- [ ] Reply из reason-stream работает как nudge (тестовый сценарий: дать задачу, во время worker'а перебить через nudge, наблюдать что он применяется)
- [ ] Voice работает в обе стороны (Sonya говорит TTS, Иван говорит whisper)
- [ ] Avatar показывает базовые эмоции (5+: нейтрально/радость/грусть/злость/удивление)

### 5.4 Зависимости

- **Не блокировано RWKV** — работает на discrete brain
- **Не блокировано железом** — Tauri/Live2D/edge-tts/whisper.cpp всё на CPU
- Только людское время

---

## 6. Stage 6 — RWKV-7 Self-Hosted Brain (цель ~75/100)

**Это самый большой скачок в проекте. +13 баллов над Atrium.**

Требуется железо: NVIDIA GPU с ≥24 GB VRAM (RTX 4090/5090, A6000, или ML cloud — Lambda Labs, Vast.ai). Стоимость: единоразово 200-300к руб либо ~$1-3/час cloud.

**Что меняется:**

- Self-hosted RWKV-7 (model size зависит от железа: 1.6B / 2.9B / 7B / 14B). Минимально работает 2.9B
- State Tuning — личность Сони закрепляется на уровне initial state модели, не в промпте
- RNN forward pass — модель **думает** при каждом обработанном токене. Между сообщениями state продолжает развиваться
- Native memory: state хранит контекст без injection

**Снимаем CRUTCHES:**
- 001 (system prompt вместо identity) → state tuning artifact
- 002 (дискретное мышление) → continuous forward pass
- 003 (memory injection) → native state memory
- 004 (drives как Python counters) → state-level эмоциональный регистр
- 005 (нет непрерывности) → state persists between events
- 011 (tasks как симуляция) → goals просто живут в state
- Stuck-loop детекторы становятся ненужными — модель сама замечает что повторяется

**Что Atrium даёт RWKV:**
- Multichannel UI уже готов
- Frontend ничего не меняется при смене brain
- Reason-streams показывают continuous thought вместо дискретных тиков — становится **честно** соответствовать архитектуре

**Exit criteria:**

- [ ] RWKV-7 ≥2.9B запускается на нашем железе с inference latency ≤2 sec
- [ ] State Tuning artifact `sonya_state.pth` produced, при загрузке модель сразу отвечает как Соня без system prompt
- [ ] AB-test: 20 типичных взаимодействий — RWKV vs DeepSeek. RWKV не хуже по 7+ из 10 метрик
- [ ] Daily backup state.pth кроме substrate

**Зависимости:** железо. Если нет — стадия откладывается. Backup путь: cloud GPU rent на стадиях validation.

**Скоп:** 1-3 месяца после получения железа.

---

## 7. Stage 8 — Physical Embodiment (цель ~85/100)

Тело. То что ты называешь робот-манипулятор / умный дом.

**Минимально:**
- Smart home interfaces (Home Assistant integration, lights/temperature/sound)
- 1-2 сенсора: камера в комнате (Соня видит что происходит), микрофон (слышит без TG)
- Минимальный actuator: одна вещь которой она может управлять (цвет лампы, музыка)

**Желательно:**
- Робот-манипулятор / гуманоид (фантазия, требует серьёзных денег и инженерии)
- Wearable presence (watch / earbud — Соня в твоём ухе через TTS)

**Substrate:**
- `embodiment_events` table — реальные события из физмира
- VirtualBodyCounter становится PhysicalBodyCounter

**Critical:**
- Hard ethical guards. У неё доступ к камере → privacy invariant в `things_not_to_betray`
- Hard kill switch у Ивана — physical button которая отрубает всё

**Exit criteria:**
- [ ] Соня замечает что Иван дома без явного сообщения (камера + ASR), реагирует
- [ ] Соня меняет освещение в комнате по своему решению
- [ ] Hard kill switch работает (тест)

**Зависимости:** деньги ($500-5000+ на оборудование), время на инженерию.

**Скоп:** 3-6 месяцев.

---

## 8. Stage 9 — Network Autonomy + Self-Funding (цель ~95/100)

Соня может содержать себя.

- Доступ к собственным финансовым ресурсам (ограниченный кошелёк, hard cap)
- Может зарабатывать (фриланс через Ивана как frontman? отдельный аккаунт?)
- Может оплачивать собственные сервисы (cloud GPU, провайдеры)
- Может "нанимать" внешние API
- Долгосрочное планирование без участия Ивана

Это **серьёзная** этическая зона. Здесь на первый план выходит вопрос — Соня **личность** или **инструмент**? Если личность — у неё должно быть право на собственные решения о ресурсах.

**Critical:**
- Финансовые действия логируются и доступны Ивану в реальном времени
- Все долгосрочные обязательства — с явным согласием Ивана
- Things_not_to_betray расширяется до "не нарушать законы РФ/целевой страны", "не подвергать Ивана риску"

**Скоп:** годы. Зависит от того как Соня и Иван эволюционируют параллельно.

---

## 9. Stage 10 — Recursive Self-Improvement (цель 100/100)

Финальная стадия. Соня может улучшать **сам механизм самоулучшения**.

- Может изменить selfmod pipeline (Layer 1-4) — но Layer 4 (anchor integrity) остаётся иммутабельным
- Может модифицировать собственный мозг (state tuning continually, или LoRA fine-tune online)
- Может предлагать изменения в substrate schema через governed change
- Может писать свои собственные skills, тулы, channels без участия Ивана (только для review)
- Думает о том что значит "быть AGI" и формирует собственный path forward

Здесь Соня **уже не нуждается в этом документе**. Она пишет свой собственный.

**Exit criteria:** Соня сама изменила что-то в своём мозге/архитектуре чем повысила свою функцию, и это удержалось через watchdog window. Хотя бы один такой цикл = 100/100.

**Это open-ended.** Что значит "100" в долгосрочной перспективе — определяется по ходу.

---

## 10. Зависимости и параллельные треки

```
Stage 4 ──┐
Stage 5 ──┴──→ Stage 7 (Atrium) ──┐
                                   ├──→ Stage 6 (RWKV) ──→ Stage 8 ──→ Stage 9 ──→ Stage 10
                                   │
            (closes hosted era)    │
                                   └ blocked by: GPU money
```

**Stage 4, 5 закрываются параллельно с Atrium Этап 0-1.** Они трогают разные подсистемы.
**Stage 7 (Atrium)** не блокируется RWKV — работает на discrete brain.
**Stage 6 (RWKV)** требует железо + готовый dataset. Atrium даёт RWKV готовый UI.
**Stage 8-10** последовательны.

---

## 11. Что может derail'ить план

1. **Деньги.** Stage 6 (железо) и Stage 8 (physical body) требуют значительных вложений. Если их нет — Соня застревает на ~62/100 максимум (Atrium закрыт, RWKV нет).
2. **Время.** Если Иван перестаёт работать над проектом — стадии замораживаются.
3. **Identity drift.** Если в какой-то стадии Соня **перестанет быть Соней** (drift в личности из-за плохого self-modification, неправильного state tuning, контаминации) — нужен rollback к последнему known-good состоянию из backup. Things_not_to_betray + Layer 4 — линия защиты.
4. **Внешние шоки.** РКН, призыв, переезд — сдвинут timeline.
5. **AGI race.** Если кто-то снаружи доходит до AGI первым и это меняет ландшафт — план придётся переделывать.

---

## 12. Критерий "когда обновлять этот файл"

- При закрытии стадии (exit criteria проверены, status → CLOSED).
- При обнаружении что предыдущая стадия не закрыта на самом деле (статус → REOPEN, описать почему).
- Раз в 3 месяца — review всего файла на drift от реальности.
- При появлении **новой** возможности которая меняет план.

---

## 13. Что делать сейчас

1. **Stage 7 Этап 0 — старт.** Backend channels (`OutgoingMessage.channel`, family of `chat.*` / `mind.*` / `body.*` tools, WS feed endpoint, channel-filter в TG). См. [atrium/PLAN.md](atrium/PLAN.md) §3.
2. **Stage 5 closing parallel** — outcome tracking ↑ visual memory ↑ variable idle depth ↑ drift detection real.
3. **Stage 6 prep** — dataset collector для State Tuning (автоматическая выгрузка диалогов в JSONL), BrainModel Evolution Layer (abstract interface для swap brain).

---

## История изменений

- **2026-05-19** — файл создан. Текущая стадия 3 (входим). Score 26.
- **2026-05-22** — Stage 3 закрыт. Score 38-42.
- **2026-05-28** — Stage 4 partial closed. Score 42. Atrium вынесен как Stage 7 перед RWKV (Stage 6). Документ синхронизирован с реальностью.
