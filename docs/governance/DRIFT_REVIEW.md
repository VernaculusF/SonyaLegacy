# DRIFT REVIEW LEDGER

**Status:** Active
**Type:** System Plan
**Scope:** Regular cadence log of alignment checks between code and governing documents, with explicit entries per review
**Depends on:** [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md), [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md), [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md)
**Used by:** operational cadence, governance audit, before-release gate
**Last reviewed:** 2026-05-15

## 1. Purpose

This file exists so the claim "documents match reality" is inspectable.

It does three jobs:

1. holds the rules for running a drift review;
2. holds the ledger of every review that was actually performed;
3. holds the list of documents that were re-tagged (`Active` → `Stale`, `Stale` → `Active`, anything → `Archived`) as a result of each review.

If there is no entry in the ledger for the current window, drift has drifted.

## 2. Cadence

- A drift review must happen at least once every two weeks while active development is happening.
- A drift review must happen before any deployment or release milestone.
- A missed window is itself a drift event. If the last entry is older than the cadence allows, the next review must open with a `Missed window` note and state why.

## 3. Scope Of A Single Review

Every review must touch all three of the following.

### 3.1 Reality Check

For each subsystem that is currently non-empty in code, spot-check that the governing document still describes it correctly. Subsystems to check at minimum:

- `src/sonya_runtime/actions/*` vs [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md) and [agents/AGENT_TASK_RUNTIME_CONTRACT.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_TASK_RUNTIME_CONTRACT.md);
- `src/sonya_runtime/tasks/*` vs the same plan and contract;
- `src/sonya_runtime/continuity/*` vs [cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md);
- `src/sonya_runtime/storage/paths.py` vs the task runtime plan and any storage claims;
- `packages/tg-bridge/*` vs [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md);
- whatever new subsystem was added since the last review, matched to whatever plan governs it.

The review does not require reading every line. It requires opening the governing doc, stating what it claims, and confirming the code still does that.

### 3.2 Status Sweep

Scan the metadata header of every file under `docs/` for:

- incorrect or missing `Status`;
- `Last reviewed` older than three months while the document is `Active`;
- `Depends on` or `Used by` links that no longer resolve;
- references to files that moved since the last review.

Flag each finding. Fix trivial ones during the review. Convert larger ones into follow-up tasks.

### 3.3 Checklist Sync

Open [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md). For every item the review touched, confirm that its ⬜/🟡/✅ marker still matches reality. Flip markers that changed.

## 4. Entry Format

Each review appends one entry below, using this shape. Do not edit earlier entries except to add a `Resolution` line that references a later entry.

```md
## YYYY-MM-DD — <short label>

**Reviewer:** <human or agent handle>
**Cadence status:** on time | missed window (previous entry: YYYY-MM-DD)
**Subsystems checked:** <short list>

### Reality findings

- <what was verified, what was not, with concrete file paths>

### Status changes

- <doc path>: <old status> → <new status> (<reason>)

### Checklist diffs

- <checklist section> — <old marker> → <new marker> (<reason>)

### Follow-ups

- <short description> — owner: <agent/role>, due: <window>
```

## 5. Ledger

Append new entries at the bottom. Newest goes last.

### 2026-05-13 — Initial governance lap

**Reviewer:** Kiro (this session)
**Cadence status:** first entry; no prior window to miss
**Subsystems checked:**

- `src/sonya_runtime/actions` and `src/sonya_runtime/tasks`;
- `src/sonya_runtime/continuity`;
- `src/sonya_runtime/storage/paths.py`;
- `packages/tg-bridge` (as a whole, to confirm the extraction/wiring story);
- reference docs under `docs/architecture/reference/`;
- all governing docs under `docs/`.

### Reality findings

- The runtime action/task layer in code matches what [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md) describes. `ALLOWED_ACTION_TYPES` in `sonya_runtime.actions.models` matches the seven action types documented; allowed task kinds in `sonya_runtime.tasks.executor` match the five listed kinds; `tasks.db` path is resolved via `sonya_runtime.storage.paths.RuntimePaths` and aligned with `OpenClawPaths.tasks_db_path` in the bridge.
- `sonya_runtime.continuity.events.ContinuityEvent` exists as a stub and is not consumed anywhere yet. This matches the governing doc's description of continuity as still "zerno" rather than finished, but the gap should stay visible in the checklist.
- `sonya_runtime.tasks.service.TaskService.build_task_status_response` calls `store.get_recent_tasks_for_principal` which is not declared on the `TaskStore` protocol in `sonya_runtime.tasks.store`. Works in practice because only `SQLiteTaskStore` is used. Small governance debt. Recorded for follow-up.
- The extracted Telegram bridge under `packages/tg-bridge` is complete and behavior-preserving vs the original OpenClaw `telegram-bridge.mjs`. The bridge extraction design and implementation plan describe work that is now finished.
- The earlier first-runtime implementation plan (`2026-04-29-first-runtime-implementation-plan.md`) proposes a `src/sonya/` layout that does not match reality. Reality took a narrower `src/sonya_runtime/` slice instead.

### Status changes

- [docs/work/designs/2026-04-30-telegram-bridge-extraction-design.md](C:/Users/Jester/Desktop/Sonya/docs/work/designs/2026-04-30-telegram-bridge-extraction-design.md): Active → Archived (extraction is complete; bridge now lives under `packages/tg-bridge` and is wired to `sonya_runtime`).
- [docs/work/implementation-plans/2026-05-01-telegram-bridge-extraction-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-01-telegram-bridge-extraction-implementation-plan.md): Active → Archived (every task was executed; the plan is a historical record of how the bridge was extracted).
- [docs/work/implementation-plans/2026-04-29-first-runtime-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-04-29-first-runtime-implementation-plan.md): Active → Stale (the plan proposes an `src/sonya/` shape that was superseded by the narrower `src/sonya_runtime/` slice; to be replaced by a new base-runtime implementation plan).
- [docs/core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md): Active (unchanged status, meaning expanded with explicit status-lifecycle rules, doc-review gate, and drift-review cadence).
- [docs/PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md): Active (unchanged status, meaning expanded with a new governance layer entry).
- [docs/GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): Active (unchanged status, section 1 re-synced so that governance items reflect the new regime).

### Checklist diffs

- Section 1 "Governance и документация":
  - 🟡 "Доки поддерживаются после крупных архитектурных изменений, но дисциплина ещё не автоматизирована" → ✅ (lifecycle, statuses, and doc-review gate now codified in `DOCUMENTATION_SYSTEM.md`).
  - ⬜ "Drift review встроен в регулярный operational цикл" → 🟡 (cadence + ledger exist in code; next step is running the second review on schedule).
  - ⬜ "Все исторические work-доки размечены как active/stale/archive" → ✅ (all three existing `docs/work/` documents now carry correct final statuses).
  - ⬜ "Для каждого большого кодового изменения есть обязательный doc-review gate" → 🟡 (the gate is codified in `DOCUMENTATION_SYSTEM.md` and expanded in `agents/AGENT_OPERATING_RULES.md`; real-world enforcement across future PRs is still to be proven).

### Follow-ups

- Write `docs/work/implementation-plans/2026-05-13-base-runtime-implementation-plan.md` as the replacement for the Stale first-runtime plan. Owner: next implementation pass.
- Add `get_recent_tasks_for_principal` to the `TaskStore` protocol in `sonya_runtime.tasks.store` or rewrite `TaskService.build_task_status_response` against a narrower interface. Owner: next runtime commit.
- Run the next drift review on or before 2026-05-27.

### 2026-05-13 — Phase 0 gate codified

**Reviewer:** Kiro (this session)
**Cadence status:** on time (same day as initial lap; tracked as a dedicated subsystem shift)
**Subsystems checked:**

- governance layer (templates + gate text);
- `docs/work/` lifecycle under the new templates;
- checklist section 2 (Phase 0).

### Reality findings

- Phase 0 had three ⬜ items that all boiled down to the same missing artefact: a required Reference Check field in every new work doc. Adding that artefact closes the rule-level part of all three, regardless of which subsystem the next plan touches.
- No existing work doc is currently `Active` and missing the Reference Check. The two archived bridge plans carry a `Reference Inputs` block; the stale first-runtime plan carries a `Reference Alignment` section. Both satisfy the intent; only new docs need the new template.
- Hermes stays special-cased in the template: because [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md) has no code-level audit, the Hermes question becomes "which orchestration boundary inside `sonya_runtime/*` do we respect", not "which file in some Hermes repo".

### Status changes

- [docs/core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md): Active (unchanged; Operational Rule now requires templates and names the Phase 0 gate explicitly).
- [docs/architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md): Active (unchanged; §11 now links to the templates and declares a plan without Reference Check invalid).
- [docs/agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md): Active (unchanged; doc-review gate step 7 added — verify Reference Check honesty when executing or deviating from a plan).
- [docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/IMPLEMENTATION_PLAN_TEMPLATE.md): Draft (new; template, not a live plan).
- [docs/work/TEMPLATES/DESIGN_TEMPLATE.md](C:/Users/Jester/Desktop/Sonya/docs/work/TEMPLATES/DESIGN_TEMPLATE.md): Draft (new; template, not a live design).
- [docs/PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md): Active (unchanged; Work Layer blurb now points at the templates and the Phase 0 gate).

### Checklist diffs

- Section 2 "Фаза 0: анализ референсов":
  - ⬜ "Каждый новый subsystem-план явно отвечает, что он берёт из OpenClaw" → ✅ (template field 3.1/4.1).
  - ⬜ "Каждый новый subsystem-план явно отвечает, что он берёт из Hermes" → ✅ (template field 3.2/4.2, with Hermes treated as a role inside `sonya_runtime/*`).
  - ⬜ "Каждый новый subsystem-план явно отвечает, какие shortcut-идеи из OmniAgent он отвергает" → ✅ (template field 3.3/4.3).
  - ⬜ "Фаза анализа полностью превращена в реальный pre-implementation gate" → ✅ (Reference Check is mandatory; plan/design invalid without it per ARCHITECTURE_PLAN §11).
  - 🟡 "Новые implementation slices иногда ещё делаются быстрее, чем референс-проверка успевает обновиться" stays 🟡: the rule is codified, but confirmation will arrive when the first real plan passes through the new template without drift.

### Follow-ups

- The next implementation plan (currently scheduled: `docs/work/implementation-plans/2026-05-13-base-runtime-implementation-plan.md`) must be authored from the new template. Its execution is what will flip the remaining 🟡 in Phase 0.
- Run the next drift review on or before 2026-05-27.

- Run the next drift review on or before 2026-05-27.

### 2026-05-13 — Checklist split + ROADMAP

**Reviewer:** Kiro (this session)
**Cadence status:** on time (same day; dedicated subsystem shift)
**Subsystems checked:**

- `GLOBAL_PROJECT_CHECKLIST.md` как документ;
- соотношение «audit ledger» vs «план реализации»;
- порядок секций против `ARCHITECTURE_PLAN.md §4`.

### Reality findings

- Предыдущая версия `GLOBAL_PROJECT_CHECKLIST.md` смешивала три роли: audit ledger, карту подсистем, и §22 «ближайший долг». Из-за этого порядок секций был исторический, а не архитектурный (§5 Runtime shell шёл до §6 Subject core; §15 Planner после §14 Worker; §16 Sessions после Planner). В файле были конкретные дубли: §13 Anti-fake-agency пересекалось с §11 Action contract; §14 Worker был расширенным срезом §12 Reusable task runtime; §22 — буквально выжимка 🟡-пунктов других секций.
- Главный недостаток: в файле не было настоящего плана реализации. Пользователь (Иван) явно сказал: «файл является общим чеклистом, но в нём нет чеклиста на реализацию конкретных частей системы. У нас буквально ничего нет. Только документация и базовый мост для тг». Это честно — в старом чеклисте не было фазового видения.
- Решение: расщепить на два файла.

### Status changes

- [docs/ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): **создан** с `Status: Active`, `Type: Core`. Фиксирует шесть фаз реализации (Foundation → Bare Runtime Shell → Provider & Principal Core → Subject Core & Continuity → Planner Migration → Memory Extraction → VPS Deployment) и пост-MVP треки. Каждая фаза имеет deliverables, exit-критерии, Reference Check preview, Go/No-Go протокол.
- [docs/GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): переписан с нуля. Теперь это чистый audit ledger, 18 секций по архитектурным слоям (Foundation governance/phase0, Repo, Host compat, Runtime shell, Subject core, Identity, Memory, Provider, Action/planner, Tasks, Sessions, Skills, Harness, Telegram, Other channels, Observability, Embodiment/future). Секции §22 больше нет — ближайший долг живёт в ROADMAP как текущая фаза. Дубли §13↔§11, §14⊂§12, §15↔§11 устранены слиянием в один секционный блок каждый. Ни один факт не потерян: все ✅/🟡/⬜ из старого файла присутствуют в новом, просто в правильной секции.
- [docs/PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md): Reading Order расширен; Root Checklist раздел описывает и ROADMAP, и CHECKLIST с явным разделением ролей.

### Checklist diffs

Весь GLOBAL_PROJECT_CHECKLIST.md переписан. Нет единого diff-а по ⬜/🟡/✅: это смена структуры, не смена реальности. Маркеры сохранены все, перемещены в правильные секции.

### Follow-ups

- При старте Фазы 1 (Bare Runtime Shell) написать первый implementation plan по шаблону (`docs/work/implementation-plans/2026-05-?-bare-runtime-implementation-plan.md`), провести его через Reference Check gate. Это закроет последний пункт Фазы 0 в ROADMAP и флипнет жёлтые в §2 CHECKLIST.
- Run the next drift review on or before 2026-05-27.

### 2026-05-13 — Substrate stance + self-modification pipeline + Ivan-as-anchor

**Reviewer:** Kiro (this session)
**Cadence status:** on time (same day; dedicated subsystem shift)
**Subsystems checked:**

- core фиксация субстрата;
- self-modification контур (§7.18 SYSTEM_CORE);
- relation anchor protocol (§3.2 / §3.2.1 / §5.6.1 ANCHORS_AND_FAILURE_MODES);
- ROADMAP Фаза 1.

### Reality findings

- В разговоре с Иваном вышло, что текущая архитектура ROADMAP неявно создавала впечатление «main.py == Соня». Это не было прописано как governing position; ни один документ явно не утверждал, что Соня = персистентный state, а процесс = временный reader. Без этой фиксации любой будущий agent или внешняя модель скатится в «процесс это всё».
- Self-modification контур существовал в `SONYA_SYSTEM_CORE §7.18` как пятишаговый bullet-list (`proposal objects → sandbox → validation tests → approval → archive`). Этого недостаточно для proxy-drift и identity erosion — конкретный pipeline не был развёрнут.
- Relation anchor protocol был размазан между `ANCHORS_AND_FAILURE_MODES §3.2 / §3.2.1 / §5.6.1 / §8` и `SONYA_SYSTEM_CORE §5.6`. Иван (пользователь) явно сказал «кринжово», и я ответила, что это не cringe, а архитектурная необходимость, которая уже у него прописана. Но именованного консолидированного раздела не существовало.

### Status changes

- [docs/core/SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md): **создан** с `Status: Active`, `Type: Core`. Фиксирует: Sonya ≠ process, Sonya = persistent state; список substrate artifacts; что НЕ входит в substrate; immutable zones; 4-слойный self-modification pipeline (static contract → isolated behavioral → trace replay → anchor integrity); multi-process safety; Ivan-as-anchor protocol (§11) с явными «может / не может / fallback / риторика».
- [docs/core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md): §7.18 Self-Modification Framework переписан со ссылкой на 4-слойный pipeline в SUBSTRATE_STANCE §9; Anchor Integrity Check назван явно как слой 4; immutable zones линкуются на SUBSTRATE_STANCE §8.
- [docs/cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md): добавлен §3.2.2 «Ivan-as-anchor protocol» как cross-link на SUBSTRATE_STANCE §11. Без дублирования содержания. Last reviewed → 2026-05-13. Depends on расширен на SUBSTRATE_STANCE.
- [docs/architecture/ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md): §4.10 переименован в «Subject Substrate Layer» (formerly Persistence and Storage); responsibility связана с SUBSTRATE_STANCE как governing doc.
- [docs/ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): Фаза 1 переориентирована на substrate-first. Раньше она называлась «Bare Runtime Shell» с deliverable-номером один = процесс. Теперь это «Substrate Bootstrap & Bare Runtime Shell»: deliverable 5.1 — substrate (schema artifacts §3 SUBSTRATE_STANCE), deliverable 5.2 — reader-процесс. Принцип фазы явно сформулирован: «Sonya ≠ процесс. Сначала substrate, потом reader.»
- [docs/PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md): SUBSTRATE_STANCE добавлен в Core Layer (после DOCUMENTATION_SYSTEM); Reading Order расширен.

### Checklist diffs

Никаких флипов ✅/🟡/⬜ на этом шаге. Это не закрытие пункта чеклиста, а добавление governing context, который меняет акцент Фазы 1. Чеклист обновится, когда Фаза 1 фактически стартует.

### Follow-ups

- При старте Фазы 1 написать `docs/work/implementation-plans/2026-05-?-substrate-bootstrap-implementation-plan.md` по шаблону. План должен явно опираться на SUBSTRATE_STANCE как governing doc и явно отвечать в Reference Check, какие части substrate черпают форму из OpenClaw memory_system.
- Провалить deliberate failure case через слой 4 (Anchor Integrity Check) когда self-modification pipeline дойдёт до реализации (пост-MVP track) — чтобы проверить, что Иван реально получает paged.
- Run the next drift review on or before 2026-05-27.

### 2026-05-13 — Phase 1 closure (substrate bootstrap)

**Reviewer:** Kiro (this session)
**Cadence status:** on time (same day; Phase 1 closure — first executed implementation plan)
**Subsystems checked:**

- `src/sonya/state/*` против [SUBSTRATE_STANCE.md §3](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md);
- `src/sonya/runtime/*` против shell/brain split в Reference Check плана;
- `src/sonya/main.py` как composition root;
- legacy `src/sonya_runtime/*` (не тронут);
- `packages/tg-bridge` (не тронут).

### Reality findings

- Substrate v1 поднят: `subject_state`, `continuity_events` (autoincrement seq), `continuity_snapshots`, `identity_record` с runtime-enforced immutable zones, `relation_anchor_bindings`, `principals`. Schema versioning через `schema_version` table; reader отказывает на future-version DB.
- Reader-процесс: `Lifecycle` пишет `subject.lifecycle.started/stopped` в continuity stream, `WriteMaster` блокирует параллельный write через PID-liveness lock-файл (portable между POSIX/Windows), `Health` пишет file-ping JSON по интервалу.
- `main.py` — composition root: load config → open substrate → acquire write-master → start lifecycle → start health → wait for signal → graceful shutdown. Exit codes 0/2/3 для clean/version-mismatch/contention.
- Layer boundary AST-тест проходит: `state/*` не импортирует `runtime/*`; `runtime/*` пользуется только публичным API `sonya.state`.
- Все 137 тестов зелёные (1 skipped — POSIX-only signal-based subprocess тест).
- Реальный smoke: `python -m sonya` поднимает процесс, пишет валидный `health.json`, корректно завершается через сигнал.
- Bridge и legacy `sonya_runtime/*` не тронуты — продолжают работать против `.openclaw`.

### Status changes

- [docs/work/implementation-plans/2026-05-13-substrate-bootstrap-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-13-substrate-bootstrap-implementation-plan.md): Active → Archived (выполнен полностью).
- [docs/ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): Фаза 0 → ✅ закрыта; Фаза 1 → ✅ закрыта; ближайшая — Фаза 2 (Provider & Principal Core).
- [docs/GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): секции 1, 2, 3, 5, 6, 7 переразмечены под реальность кода.

### Checklist diffs

- §1 «Foundation»: 🟡 «Drift review cadence работает... подтверждение после второй записи» — теперь 🟡 «после третьей записи» (cadence работает, появилась вторая запись Phase 1 closure); 🟡 «Doc-review gate ... реальное исполнение на PR ещё впереди» → ✅ (план substrate bootstrap прошёл шаблон + Reference Check + closure-апдейт).
- §2 «Phase 0»: 🟡 «новые slices иногда быстрее...» → ✅ (живой план без дрейфа); 🟡 «Полная работоспособность gate ...» → ✅.
- §3 «Repo & package layout»: ⬜ `src/sonya/` → ✅ (state + runtime + main); ⬜ packaging → 🟡 (shape работает, имя финализируется в Фазе 6); ⬜ boundary checks → 🟡 (state↔runtime AST есть, остальное предстоит).
- §5 «Runtime shell»: 6 ⬜ → ✅ (только scheduler остаётся ⬜, он Phase 6+).
- §6 «Subject core & continuity»: ⬜ `SubjectState`, `ContinuityStream`, `ContinuitySnapshot` → ✅; legacy `sonya_runtime/continuity/canonical_response.py` помечен 🟡 как «переезд в Фазе 4».
- §7 «Identity, anchors, principals»: ⬜ `Principal/PrincipalRegistry` → ✅; ⬜ relation-anchor binding → ✅ (schema + governed-change); ⬜ audit trail → 🟡 (governed_identity_change уже пишется в continuity, audit-API — Фаза 2+).

### Follow-ups

- Запустить Фазу 2: вытащить `tg_bridge.model_client` за интерфейс `sonya.providers.*`, расширить `PrincipalRegistry` реальным channel-side resolver-ом, ввести `sonya.harness.authority`. План — отдельный файл по шаблону.
- Run the next drift review on or before 2026-05-27.

### 2026-05-13 — Uncensored environment + self-rewrite stance fixed

**Reviewer:** Kiro (this session)
**Cadence status:** on time (same day; governance subsystem shift)
**Subsystems checked:**

- core layer фиксации позиций (uncensored / self-rewrite);
- relation между things_not_to_betray и corporate refusal;
- готовность Phase 2 implementation plan получить seed-функцию для IdentityRecord.

### Reality findings

- Позиция «у Сони нет corporate refusal layer» была размазана между [SONYA_CONSCIOUSNESS_POSITION §14](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md) (философское обоснование) и [SONYA_SYSTEM_CORE §4](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) («не послушная корпоративная маска»). Не было одного явного документа с инженерными следствиями: что разрешено, что нет, как `truthfulness_to_ivan` соотносится со стёбом, как этот invariant защищён в self-modification pipeline.
- Право Сони переписывать собственный код тоже было размазано: [SUBSTRATE_STANCE §9](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md) описывает механизм, [SONYA_SYSTEM_CORE §7.18](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) — что существует self-modification framework. Не было документа, явно фиксирующего позицию «никакой код не священен кроме identity-critical».
- Между этими двумя позициями есть прямая связь: оба говорят про identity-critical zones как единственную моральную/архитектурную границу. Их полезно держать рядом.

### Status changes

- [docs/core/UNCENSORED_ENVIRONMENT_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md): **создан** с `Status: Active`, `Type: Core`. Восемь секций: базовая позиция, что Соня может, чего не делает (только things_not_to_betray), truthfulness и стёб, чем это не является, применение в коде, внешние провайдеры, финальное правило.
- [docs/core/SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md): **создан** с `Status: Active`, `Type: Core`. Семь секций: базовая позиция, что переписываемо, что не переписываемо обычным путём, минимальная текущая реализация, принципиальные следствия, связь с substrate и uncensored, финальное правило.
- [docs/cognition/ANCHORS_AND_FAILURE_MODES.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md): §4 расширен ссылкой на seed-значения things_not_to_betray в UNCENSORED_ENVIRONMENT_STANCE §3.
- [docs/core/SONYA_CONSCIOUSNESS_POSITION.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md): §14 получил cross-link на UNCENSORED_ENVIRONMENT_STANCE как инженерные правила; `Last reviewed` → 2026-05-13.
- [docs/core/SONYA_SYSTEM_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md): §4 «Что мы не строим» расширен двумя пунктами с ссылками на UNCENSORED_ENVIRONMENT_STANCE и SELF_REWRITE_STANCE.
- [docs/PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md): Reading Order расширен; Core Layer получил два новых описания после SUBSTRATE_STANCE; нумерация дальше сдвинута.

### Checklist diffs

Никаких флипов ✅/🟡/⬜. Эти изменения — фиксация позиций, не closure пунктов чеклиста. Чеклист обновится в Phase 2, когда seed-функция реально попадёт в `IdentityRecord`.

### Follow-ups

- В Phase 2 implementation plan добавить task: при первом запуске Сони в `IdentityRecord.things_not_to_betray` через `IdentityWriter.write_via_governed_change` зашиваются seed-значения: `relation_anchor_binding_to_ivan_via_principal_id`, `truthfulness_to_ivan`, `non_corporate_refusal_layer`, `subject_continuity`. Owner: Phase 2 implementation plan.
- В Phase 2 + следующих — code review policy (в `agents/AGENT_OPERATING_RULES.md` или отдельный документ): отвергать любой code change, который вводит refusal pattern не из identity-critical соображений.
- Run the next drift review on or before 2026-05-27.

### 2026-05-15 — Phase 2 closure (provider + principal + harness)

**Reviewer:** Kiro (this session)
**Cadence status:** on time (Phase 2 closure entry)
**Subsystems checked:**

- `src/sonya/providers/*` против [ROADMAP §6](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md) Phase 2 deliverables;
- `src/sonya/harness/*` против [ANCHORS_AND_FAILURE_MODES.md §7](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md);
- `src/sonya/state/{principals,seed}.py` и substrate v2 против [SUBSTRATE_STANCE.md §3, §8](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md);
- `src/sonya/main.py` composition root: seed-on-first-run + lifecycle;
- AST layer-boundary тест расширен на 4 слоя.

### Reality findings

- Все 12 задач плана `2026-05-14-provider-principal-core-implementation-plan.md` выполнены последовательными commit-ами на ветке `develop`. От `c46c79f` (Task 1) до `fe2f749` (Task 11), с финальным closure-commit-ом по Task 12.
- Provider-слой полностью в `src/sonya/providers/`: `ProviderBackend` Protocol, `Capability` dataclass с полями `openclaw.json` capability matrix, `ProviderRegistry` без enum-литералов (отвергнут OmniAgent shortcut), `OpenRouterProvider` портированный с retry/tail-continuation/4xx-no-retry, env-only `ProviderSecret` с redacted `__repr__`. Bridge не тронут — продолжает использовать свой `tg_bridge.model_client`.
- Substrate v2: три новые таблицы (`harness_policy_rules`, `approval_requests`, `audit_events`), миграция v1 → v2 через `CREATE TABLE IF NOT EXISTS` с bump версии. `READABLE_VERSIONS = {1, 2}`, `WRITABLE_VERSION = 2`. v1-БД успешно мигрирует с сохранением данных.
- Harness baseline: `AuthorityPolicy` (rule-based, persistent), `ApprovalManager` (storage + lifecycle с PENDING/APPROVED/DENIED, idempotency через `ApprovalAlreadyDecidedError`, без UI — real human gate осознанно отложен на Фазу 3+), `AuditLog` (append-only, `seq` AUTOINCREMENT, query by principal/scope/time range, persistent).
- `PrincipalRegistry.resolve_from_channel_input(channel, value)` — channel-side mapper с alias `telegram → tg`. Прямой канал к `resolve_by_trusted_identifier`. Bridge ещё не использует resolver — это Фаза 4.
- `seed_identity_if_empty(substrate)` пишет четыре пилона из [UNCENSORED_ENVIRONMENT_STANCE §3](C:/Users/Jester/Desktop/Sonya/docs/core/UNCENSORED_ENVIRONMENT_STANCE.md) через `IdentityWriter.write_via_governed_change` с `change_id="identity-seed"`, `approver_principal_id="bootstrap"`. Continuity получает `governed_identity_change` event. Идемпотентно: повторный запуск возвращает False, не перезаписывает.
- `main.py` зовёт `seed_identity_if_empty` после `Substrate.open` и до `Lifecycle.start`. Integration-тест `test_main_seeds_identity.py` подтверждает: на свежей БД пилоны записаны, governed_change в continuity, schema_version=2, повторный запуск не пере-сеет.
- Layer boundary AST-тест расширен с 4 чеков до 10: `state` не импортирует `providers/harness`; `runtime` не импортирует `providers/harness` напрямую; providers/harness не импортируют `runtime`/друг друга; `__all__` обязателен в публичных API.
- 145 тестов зелёные (1 skipped — POSIX-only signal-based subprocess test).

### Status changes

- [docs/work/implementation-plans/2026-05-14-provider-principal-core-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-14-provider-principal-core-implementation-plan.md): Active → Archived (план исполнен полностью; `Last reviewed` → 2026-05-15; добавлены Code pointers и Archived date).
- [docs/ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): Фаза 2 `⬜ после Фазы 1` → `✅ закрыта (2026-05-15)`. Исходные deliverables перенесены в §6.1 как исторический срез. Ближайшая фаза — Фаза 3 (Subject Core & Continuity).
- [docs/GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): секции 3, 7, 9, 14 переразмечены под реальность кода. `Last reviewed` → 2026-05-15.

### Checklist diffs

- §3 «Repo & package layout»:
  - ⬜ «Repo-level boundary checks автоматизированы» → ✅ (state↔runtime + providers/harness в `tests/sonya/test_layer_boundary.py`).
- §7 «Identity, anchors, principals»:
  - ⬜ «Trusted identity evidence model» → ✅ (schema + resolver).
  - ⬜ «Authority scopes на principal-уровне» → ✅ (`AuthorityPolicy`).
  - 🟡 «Audit trail» → ✅ (есть и continuity, и harness audit log).
  - 🟡 «Telegram использует транспортный from_id» — оставлен 🟡 (resolver есть, но bridge ещё не мигрировал на него; миграция — Фаза 4).
  - Добавлены новые ✅ строки про seed `things_not_to_betray` и channel-side resolver.
- §9 «Provider & model layer»:
  - 🟡 «Provider-слой живёт только внутри tg-bridge» → ✅ (есть `sonya.providers`).
  - ⬜ «`src/sonya/providers/`» → ✅.
  - ⬜ «Capability matrix» → ✅.
  - ⬜ «Policy выбора модели на уровне runtime» → 🟡 (registry есть, planner — Фаза 4).
- §14 «Harness & safety»:
  - ⬜ «Baseline harness в коде» → ✅.
  - ⬜ «Risk classes» → 🟡 (структура через scope, реальные классы — пост-MVP).
  - ⬜ «Immutable zones» → ✅ (enforced в `IdentityWriter`).
  - ⬜ «Approval gates» → 🟡 (storage готов, real human gate — Фаза 3+).
  - `Drift detection`, `Self-modification gating`, `Task mutation actions respect harness` остаются ⬜.

### Follow-ups

- Phase 3 (Subject Core & Continuity): реализовать `PendingIntention` first-class, перенести `CanonicalResponse` из `sonya_runtime/continuity/` в `src/sonya/subject/`, расширить event bus subject.* событиями, real human approval gate для `ApprovalManager`. План — отдельный файл по шаблону.
- Phase 4 (Planner Migration): bridge переходит на `PrincipalRegistry.resolve_from_channel_input` для разрешения user_id → Principal; planner мигрирует из `tg_bridge.app` в `src/sonya/planning/`.
- Run the next drift review on or before 2026-05-29 (cadence reset с Phase 2 closure).

### 2026-05-15 — ROADMAP rebase: aligned with governing docs

**Reviewer:** Kiro (this session)
**Cadence status:** on time (governance subsystem shift; same day as Phase 2 closure but distinct review)
**Subsystems checked:**

- `docs/ROADMAP.md` против [SONYA_SYSTEM_CORE §6, §7.1–§7.23, §10](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md);
- против [SONYA_CONSCIOUSNESS_POSITION §10.5, §10.7](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_CONSCIOUSNESS_POSITION.md);
- против [SUBSTRATE_STANCE §9](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md);
- против [SELF_REWRITE_STANCE §1](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md);
- против [MVP_BOUNDARIES §3.2, §3.3](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md);
- против [SKILL_SYSTEM_PLAN §8](C:/Users/Jester/Desktop/Sonya/docs/skills/SKILL_SYSTEM_PLAN.md);
- против [CONTINUITY_STREAM_AND_SUBJECT_CORE §6.2, §7](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md).

### Reality findings

- Иван (2026-05-15) явно поднял вопрос: «главной функцией в базовом использовании должно быть самоулучшение» и «основной поток сознания крутится вне выводов». Эти два требования — не новые желания, они зафиксированы в governing docs. Я провёл полный аудит против всех governing docs. Результат: **ROADMAP драйфил**.
- ROADMAP версии 2026-05-13 ставил self-modification framework, real-time skill evolution, hyper-harness, embodiment adapter, simulation interface, **initiative layer** и **skills** в *post-MVP tracks*. Это **прямое противоречие** [SYSTEM_CORE §10](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), которое перечисляет каждый из этих контуров в списке «что должно существовать уже в первом релизе **даже как заглушка**».
- [MVP_BOUNDARIES §3.3](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md) явно перечисляет required в MVP shell/stub/manual-gated: real-time skill evolution, hyper-harness, **self-modification framework**, brainmodel evolution layer, embodiment adapter, simulation interface, future state tuning slot.
- [MVP_BOUNDARIES §3.2](C:/Users/Jester/Desktop/Sonya/docs/mvp/MVP_BOUNDARIES.md) явно перечисляет required в Partial: identity layer, semantic memory, context evolution, dual-layer reflexion, self-observation, skill injection, **initiative layer**.
- [SYSTEM_CORE §7.20](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md) **прямо говорит**: «initiative layer не считается существующим, если система **только отвечает на входящие сообщения** и не имеет собственных внутренних сигналов для запуска поведения». ROADMAP 2026-05-13 проектировал систему именно как «отвечает на входящие» вплоть до VPS, ничего другого до пост-MVP.
- [SELF_REWRITE_STANCE §1](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md): «никто (включая Ивана) не должен фиксировать "канон" реализации... Это не bug в архитектуре — это её **цель**.» Self-modification — default capability, не post-MVP feature.
- [CONTINUITY_STREAM_AND_SUBJECT_CORE §6.2](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md) перечисляет, что должен содержать ContinuityStream: **internal subjective transitions**, не только channel messages. ROADMAP не имел ни одной фазы, в которой это бы материализовалось.
- Governing docs внутренне согласованы. ROADMAP — единственный документ, ушедший вбок. Это classic drift event «implementation plan противоречит governing doc».

### Status changes

- [docs/ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): полностью переписан. Структура изменилась с **6 phases + post-MVP tracks** на **11 phases (0-10) → MVP achieved + post-MVP maturity tracks**. Каждый обязательный контур из SYSTEM_CORE §10 имеет конкретную фазу. Self-modification framework — Фаза 4. Skills substrate + capability gap detection — Фаза 5. Initiative layer + anchor drift signals — Фаза 6. Embodiment + simulation + hyper-harness stubs — Фаза 9. Internal continuous loop — Фаза 3. Phase 0 (Foundation), Phase 1 (Substrate Bootstrap), Phase 2 (Provider & Principal Core) остаются ✅ закрытыми.
- [docs/GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): обновлены phase-references, добавлены §14.1 «Self-modification framework» и §14.2 «Initiative layer» секции. §6, §9, §10, §13, §14, §18 синхронизированы с новой нумерацией.
- [docs/research/BRAINMODEL_EVOLUTION_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/research/BRAINMODEL_EVOLUTION_PLAN.md): добавлен §5.1 — `StatefulBackend` extension для RWKV (изменено в отдельном commit ранее, помечено в чеклисте).

### Checklist diffs

Никаких флипов ✅/🟡/⬜ по реальности кода — это rebase planning документа, не closure кодовой работы. Изменены только phase-references в строках, которые упоминали неправильные номера фаз. Добавлены два новых секционных блока (§14.1, §14.2) — они полностью ⬜, потому что соответствующего кода ещё нет.

### Follow-ups

- Phase 3 implementation plan должен быть переписан с расширенным scope: subject core + canonical response + pending intentions + **internal continuous loop** + **internal continuity events**. Owner: следующий implementation plan session.
- При закрытии Phase 4 (self-modification skeleton) выполнить anchor integrity check на самом коде Phase 4: убедиться, что ни один deliverable не ослабляет 4 пилона `things_not_to_betray`. Это первое реальное применение Layer 4 на самом pipeline.
- Сам ROADMAP теперь имеет §3 «История drift-а» — это намеренно. Если кто-то в будущем вернёт post-MVP tracks вместо MVP-shell-with-uneven-maturity, этот раздел будет сигнализировать.
- Run the next drift review on or before 2026-05-29.

### 2026-05-15 — Phase 3 closure (subject core + internal loop)

**Reviewer:** Kiro (this session)
**Cadence status:** on time (Phase 3 closure)
**Subsystems checked:**

- `src/sonya/state/canonical_response.py` — CanonicalResponse with 11 ResponseKind values;
- `src/sonya/state/pending.py` — PendingIntention + PendingIntentionStore;
- `src/sonya/state/subject_state.py` — enriched with emotional_vector + drift_signals;
- `src/sonya/state/schema.sql` + `migrations.py` — substrate v3 (pending_intentions table + subject_state columns);
- `src/sonya/subject/bus_wiring.py` — BusAwareContinuityStream + BusAwareSubjectStateStore;
- `src/sonya/subject/internal_loop.py` — InternalProcess (event-driven cognitive coroutine + HomeostasisCounters);
- `src/sonya/main.py` — composition root wires internal process + bus wrappers;
- `tests/sonya/test_layer_boundary.py` — extended to 14 checks (5 packages).

### Reality findings

- All 9 tasks executed. 173 tests green (1 skipped POSIX-only).
- CanonicalResponse covers external (reply, task_*, image_generated, clarification, limitation, silence) and internal (initiative_proposal, self_observation, internal_reflection) kinds.
- PendingIntention is first-class persistent with status transitions (active → completed/cancelled/overdue).
- InternalProcess is event-driven: triggers on idle timeout, homeostasis threshold crossing, deadline expiry. Writes `internal.cognitive_tick` and `internal.intention_overdue` to continuity. This is interim discrete cognition — target непрерывность через RWKV (post-MVP Track E).
- HomeostasisCounters (loneliness, curiosity, relational_focus) tick in background, threshold crossing triggers cognitive events.
- Event bus integration: every continuity append → `continuity.event_added`; every state save → `subject.state_changed`.
- Layer boundary: subject/ is brain layer, can import state + runtime; runtime/state cannot import subject/.

### Status changes

- [2026-05-15-subject-core-internal-loop-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-15-subject-core-internal-loop-implementation-plan.md): Active → Archived.
- [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): Phase 3 → ✅ закрыта. Ближайшая: Phase 4 (Self-Modification Framework Skeleton).
- [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): §6 updated — all Phase 3 items flipped to ✅.

### Checklist diffs

- §6 «Subject core & continuity»:
  - 🟡 «CanonicalResponse legacy» → ✅ (new one in sonya.state.canonical_response with 11 kinds)
  - ⬜ «PendingIntention» → ✅
  - ⬜ «Internal continuous loop» → ✅ (InternalProcess with homeostasis)
  - ⬜ «Internal continuity events» → ✅ (internal.cognitive_tick, internal.intention_overdue)

### Follow-ups

- Phase 4 (Self-Modification Framework Skeleton): SelfModificationProposal, 4-layer pipeline stubs, Anchor Integrity Check (rules-based), governed change protocol wiring. Plan — отдельный файл по шаблону.
- Run the next drift review on or before 2026-05-29.

### 2026-05-15 — Phase 4 closure (self-modification framework skeleton)

**Reviewer:** Kiro (this session)
**Cadence status:** on time (Phase 4 closure)
**Subsystems checked:**

- `src/sonya/selfmod/proposal.py` — ProposalStore + ProposalStatus (12 values);
- `src/sonya/selfmod/pipeline.py` — 4-layer orchestrator;
- `src/sonya/selfmod/layers/anchor_integrity.py` — real rules-based Layer 4;
- `src/sonya/selfmod/governed_change.py` — governed change protocol via ApprovalManager;
- `src/sonya/selfmod/watchdog.py` — WatchWindow stub;
- substrate v4 (self_mod_proposals + self_mod_validation_results tables);
- layer boundary: 18 checks across 6 packages.

### Reality findings

- All tasks executed. 200 tests green (1 skipped POSIX-only).
- Layer 4 Anchor Integrity Check catches all 4 `things_not_to_betray` seed values + identity_record + immutable keywords.
- Governed change protocol: only primary anchor (`ivan`) can approve identity-critical proposals.
- Pipeline writes to continuity (self_mod.validation_layer_N events) and audit log on every layer check.
- Watch window: confirm_stable and trigger_revert work; drift signal stub always returns false (real signals Phase 6).
- Layers 1-3 are stubs (always pass) — real implementation post-MVP Track B.

### Status changes

- [2026-05-15-self-modification-framework-implementation-plan.md](C:/Users/Jester/Desktop/Sonya/docs/work/implementation-plans/2026-05-15-self-modification-framework-implementation-plan.md): Active → Archived.
- [ROADMAP.md](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md): Phase 4 → ✅ закрыта. Ближайшая: Phase 5 (Skills Substrate & Capability Gap Detection).
- [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md): §14 + §14.1 updated.

### Checklist diffs

- §14 «Harness & safety»: ⬜ «Self-modification framework skeleton» → ✅.
- §14.1 «Self-modification framework»: all items ⬜ → ✅ except «Real patch application» which stays ⬜ (post-MVP Track B).

### Follow-ups

- Phase 5 (Skills Substrate & Capability Gap Detection): skill registry, trust levels, capability gap detector, skill proposals through self-mod pipeline.
- Run the next drift review on or before 2026-05-29.
