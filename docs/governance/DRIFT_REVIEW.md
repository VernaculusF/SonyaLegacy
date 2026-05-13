# DRIFT REVIEW LEDGER

**Status:** Active
**Type:** System Plan
**Scope:** Regular cadence log of alignment checks between code and governing documents, with explicit entries per review
**Depends on:** [core/DOCUMENTATION_SYSTEM.md](C:/Users/Jester/Desktop/Sonya/docs/core/DOCUMENTATION_SYSTEM.md), [GLOBAL_PROJECT_CHECKLIST.md](C:/Users/Jester/Desktop/Sonya/docs/GLOBAL_PROJECT_CHECKLIST.md), [PROJECT_DOCUMENTATION_MAP.md](C:/Users/Jester/Desktop/Sonya/docs/PROJECT_DOCUMENTATION_MAP.md), [agents/AGENT_OPERATING_RULES.md](C:/Users/Jester/Desktop/Sonya/docs/agents/AGENT_OPERATING_RULES.md)
**Used by:** operational cadence, governance audit, before-release gate
**Last reviewed:** 2026-05-13

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
