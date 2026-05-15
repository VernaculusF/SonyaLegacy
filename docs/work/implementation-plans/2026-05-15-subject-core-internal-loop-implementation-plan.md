# Subject Core, Continuity & Internal Loop Implementation Plan

**Status:** Active
**Type:** Work Doc
**Scope:** Расширить subject core до полноценного живого слоя: CanonicalResponse, PendingIntention, event bus integration, internal continuous loop (heartbeat + deadline check + reflection events). Substrate v3.
**Depends on:** [ROADMAP.md §9](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [CONTINUITY_STREAM_AND_SUBJECT_CORE.md](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md), [SUBSTRATE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md), [SONYA_SYSTEM_CORE.md §7.14, §7.15, §7.16](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md), [OPENCLAW_ANALYSIS.md §2.3](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md), [ARCHITECTURE_PLAN.md §4.1](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
**Used by:** Phase 3 implementation sessions
**Last reviewed:** 2026-05-15

## 1. Goal

После Phase 3 Соня **живёт между сообщениями**:

- **CanonicalResponse** — единый объект «что Соня решила сделать» до channel-specific рендера. Kinds: `reply`, `task_created`, `task_update`, `task_result`, `image_generated`, `clarification`, `limitation`, `silence`, `initiative_proposal`, `self_observation`, `internal_reflection`.
- **PendingIntention** — persistent first-class объект: что Соня обещала сделать, привязка к task_id, deadline, followup.
- **Internal continuous loop** — autonomous coroutine, которая работает без внешних сообщений: heartbeat, deadline check, reflection events в ContinuityStream. Это «основной поток сознания вне выводов» из [CONTINUITY_STREAM_AND_SUBJECT_CORE §6.2](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md).
- **Event bus integration** — `ContinuityStream.append` → `continuity.event_added`; `SubjectStateStore.save` → `subject.state_changed`.
- **SubjectState enrichment** — `emotional_vector`, `drift_signals` (placeholder для Phase 6).

Bridge не трогается. Planner не трогается. Это чисто brain-side substrate + internal loop.

## 2. Architecture Summary

```
src/sonya/
  state/
    canonical_response.py  ← новое
    pending.py             ← новое
    subject_state.py       ← расширить (emotional_vector, drift_signals)
    continuity_stream.py   ← без изменений (event bus wiring — снаружи)
    schema.sql             ← v3
    migrations.py          ← v2 → v3
    __init__.py            ← re-export новых типов
  subject/                 ← новый пакет
    __init__.py
    internal_loop.py       ← autonomous coroutine
    bus_wiring.py          ← wiring: stream/store → event bus publish
  main.py                  ← запускает internal loop, использует bus_wiring
```

Layer boundary: `src/sonya/subject/` — brain layer (как state, providers, harness). Может импортировать `sonya.state` и `sonya.runtime` (event bus). `runtime/` не импортирует `subject/` напрямую. AST-тест расширяется.

## 3. Reference Check

### 3.1 OpenClaw — Operational Truth Preserved

- `HEARTBEAT.md` и связанные routines показывают, что initiative и maintenance tasks реально нужны ([OPENCLAW_ANALYSIS §2.3](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)). Наш internal loop — engineered версия heartbeat: interval-driven, пишет в continuity, проверяет deadlines.
- `telegram-bridge-sessions/<chatId>.json` остаётся транспортным кэшем. `CanonicalResponse` — контракт, который bridge начнёт потреблять в Phase 7. На этой фазе bridge не трогается.

### 3.2 Hermes — Orchestration Boundary Respected

- Internal loop — brain. Event bus — shell. Wiring (`bus_wiring.py`) — composition-level module в `src/sonya/subject/`, не в `runtime/`. AST-тест enforces: `runtime/` не импортирует `subject/`.
- `CanonicalResponse` — brain-side объект. Channel renderers потребляют его через публичный API `sonya.state`, не через internal modules.

### 3.3 OmniAgent — Shortcut Explicitly Rejected

- Отвергаем `context_manager` паттерн из `omniagent/agents/context_evolution.py` (28KB), где context сам интерпретирует user intent. SubjectState пассивен — internal loop пишет events, planner (Phase 7) потом читает.
- Отвергаем `PendingIntention` как in-memory-only queue. Наши intentions persistent в substrate, переживают рестарт.
- Отвергаем heartbeat как cron-job без continuity trace. Каждый heartbeat — `ContinuityEvent` с payload.

### 3.4 Reference Pass Checklist

- [x] 3.1 references concrete OpenClaw artefact (`HEARTBEAT.md`, session files).
- [x] 3.2 names the brain/shell boundary and the modules on each side; layer-boundary test extended.
- [x] 3.3 names specific OmniAgent file being refused (`context_evolution.py` 28KB).
- [x] No copy-paste of governing theory — only links.
- [x] No restated lists from source-of-truth docs.

## 4. Tech Stack

- Python 3.11+;
- стандартный `sqlite3` для миграции v2 → v3;
- `asyncio` для internal loop coroutine;
- `pytest` + `pytest-asyncio` для тестов;
- никаких новых dependencies.

## 5. File Structure

### Create

- `src/sonya/state/canonical_response.py`
- `src/sonya/state/pending.py`
- `src/sonya/subject/__init__.py`
- `src/sonya/subject/internal_loop.py`
- `src/sonya/subject/bus_wiring.py`
- `tests/sonya/test_canonical_response.py`
- `tests/sonya/test_pending_intention.py`
- `tests/sonya/test_schema_v3_migration.py`
- `tests/sonya/test_bus_wiring.py`
- `tests/sonya/test_internal_loop.py`

### Modify

- `src/sonya/state/schema.sql` — v3 additions
- `src/sonya/state/migrations.py` — v2 → v3
- `src/sonya/state/substrate.py` — `WRITABLE_VERSION = 3`, `READABLE_VERSIONS = {1, 2, 3}`
- `src/sonya/state/subject_state.py` — emotional_vector, drift_signals
- `src/sonya/state/__init__.py` — re-export new types
- `src/sonya/main.py` — internal loop + bus wiring
- `tests/sonya/test_layer_boundary.py` — extend to subject/

## 6. Task List

### Task 1: CanonicalResponse + ResponseKind

**Files:**
- Create: `src/sonya/state/canonical_response.py`, `tests/sonya/test_canonical_response.py`
- Modify: `src/sonya/state/__init__.py`

- [ ] **Step 1:** Тесты: `ResponseKind` enum has all 11 kinds; `CanonicalResponse` round-trip; frozen enforcement; default values; `created_at` auto-fills.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `ResponseKind` enum и `CanonicalResponse` frozen dataclass. Export from `__init__.py`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): canonical response with 11 response kinds`.

### Task 2: PendingIntention + PendingIntentionStore

**Files:**
- Create: `src/sonya/state/pending.py`, `tests/sonya/test_pending_intention.py`
- Modify: `src/sonya/state/__init__.py`

- [ ] **Step 1:** Тесты: create → active; get missing → error; list_active returns only active; complete(id) → completed; cancel(id) → cancelled; mark_overdue(id) → overdue; persistent across reopen; status transitions (completed → complete again raises).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `IntentionStatus` enum, `PendingIntention` frozen dataclass, `PendingIntentionStore` с CRUD. Export from `__init__.py`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): pending intention with persistent store`.

### Task 3: Substrate v3 migration

**Files:**
- Modify: `src/sonya/state/schema.sql`, `src/sonya/state/migrations.py`, `src/sonya/state/substrate.py`
- Create: `tests/sonya/test_schema_v3_migration.py`

- [ ] **Step 1:** Тесты: fresh substrate creates v3 with `pending_intentions` table and extended `subject_state`; v2 → v3 migration preserves existing data; v1 → v3 migration chain works; read-only open of v2 succeeds.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Extend `schema.sql` with `pending_intentions` table. Add `emotional_vector_json` and `drift_signals_json` columns to `subject_state`. Migration v2 → v3: `CREATE TABLE` + two `ALTER TABLE ADD COLUMN`. Bump versions.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): substrate v3 with pending intentions and subject state enrichment`.

### Task 4: SubjectState enrichment

**Files:**
- Modify: `src/sonya/state/subject_state.py`

- [ ] **Step 1:** Тесты: `SubjectState` with `emotional_vector` and `drift_signals` round-trips; snapshot/restore includes new fields; defaults are empty dict/tuple.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Add `emotional_vector: dict[str, Any]` and `drift_signals: tuple[str, ...]` to `SubjectState`. Update `SubjectStateStore.save/load` and `create_snapshot/restore_from_snapshot`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/state): subject state with emotional vector and drift signals`.

### Task 5: Event bus wiring

**Files:**
- Create: `src/sonya/subject/__init__.py`, `src/sonya/subject/bus_wiring.py`, `tests/sonya/test_bus_wiring.py`

- [ ] **Step 1:** Тесты: `BusAwareContinuityStream.append` → event `continuity.event_added` published with event kind in payload; `BusAwareSubjectStateStore.save` → event `subject.state_changed` published; underlying stream/store still works normally.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `BusAwareContinuityStream(stream, bus)` и `BusAwareSubjectStateStore(store, bus)` как thin wrappers. Export from `src/sonya/subject/__init__.py`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/subject): event bus wiring for continuity and subject state`.

### Task 6: Internal continuous loop

**Files:**
- Create: `src/sonya/subject/internal_loop.py`, `tests/sonya/test_internal_loop.py`

- [ ] **Step 1:** Тесты: heartbeat events accumulate in continuity after N intervals; deadline-overdue intention detected and marked + event emitted; stop cancels loop cleanly; no events after stop; reflection event contains tick count and active intention count.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Реализовать `InternalLoop(stream, intention_store, interval_seconds=30)` с `async start()`, `async stop()`. Each tick: write `internal.heartbeat`; check deadlines → mark_overdue + write `internal.intention_overdue`; write `internal.reflection` with summary payload.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya/subject): internal continuous loop with heartbeat and deadline check`.

### Task 7: Composition root update

**Files:**
- Modify: `src/sonya/main.py`
- Create: `tests/sonya/test_main_internal_loop.py`

- [ ] **Step 1:** Integration test: after short run, continuity contains `internal.heartbeat` events; substrate is v3.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** In `main.py` after seed + lifecycle.start: create `BusAwareContinuityStream`, `BusAwareSubjectStateStore`, `PendingIntentionStore`, `InternalLoop`. Start loop after lifecycle. Stop loop before lifecycle.request_stop.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(sonya): internal loop in composition root, substrate v3`.

### Task 8: Layer boundary extension

**Files:**
- Modify: `tests/sonya/test_layer_boundary.py`

- [ ] **Step 1:** Extend: `subject/` is brain layer (can import `sonya.state` and `sonya.runtime`); `runtime/` must not import `subject/`; `state/` must not import `subject/`; `subject/` must declare `__all__`.
- [ ] **Step 2:** Run → PASS (if code is correct) or FAIL (fix violations).
- [ ] **Step 3:** Fix any violations.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `test(sonya): extend layer boundary to subject package`.

### Task 9: Closure

**Files:**
- Modify: `docs/GLOBAL_PROJECT_CHECKLIST.md`, `docs/ROADMAP.md`, `docs/governance/DRIFT_REVIEW.md`, this plan.

- [ ] **Step 1:** In `GLOBAL_PROJECT_CHECKLIST.md`: §6 flip `⬜ PendingIntention` → ✅; `⬜ Internal continuous loop` → ✅; `⬜ Internal continuity events` → ✅; `🟡 CanonicalResponse legacy` → ✅ (new one exists, legacy still used by bridge).
- [ ] **Step 2:** In `ROADMAP.md`: Phase 3 → ✅ закрыта.
- [ ] **Step 3:** In `DRIFT_REVIEW.md`: new entry.
- [ ] **Step 4:** This plan → `Status: Archived`.
- [ ] **Step 5:** Commit `docs(phase3): close phase 3, mark subject core + internal loop complete`.

## 7. Verification

- `pytest tests/sonya -v` — всё зелёное
- `python -m sonya` на свежей substrate → v3, seed, health, heartbeat events в continuity
- `python -m sonya` на v2 substrate → мигрирует в v3 без потерь
- Bridge тесты не тронуты (`packages/tg-bridge/tests/`)

## 8. Self-Review

### Spec coverage

- CanonicalResponse: Task 1
- PendingIntention: Task 2
- Substrate v3: Task 3
- SubjectState enrichment: Task 4
- Event bus wiring: Task 5
- Internal loop: Task 6
- Composition root: Task 7
- Layer boundary: Task 8
- Closure: Task 9

### Placeholder scan

- no `TODO`, no `TBD`
- Internal loop без LLM calls — **намеренно**. LLM-driven reflection — Phase 5+ через skill. Сейчас loop работает на фиксированных правилах (heartbeat + deadline check).
- `emotional_vector` и `drift_signals` — **placeholder fields**. Реальная логика заполнения — Phase 6 (initiative + anchor drift). Сейчас — пустые dict/tuple, но schema готова.

### Type consistency

- `intention_id` — `str` (UUID-based, `intn-<hex>`).
- `principal_id` — `str` (same as everywhere).
- `deadline` — `str | None` (ISO-8601).
- `status` — `IntentionStatus` enum.
- `emotional_vector` — `dict[str, Any]` (free-form, Phase 6 defines keys).
- `drift_signals` — `tuple[str, ...]` (list of signal names, Phase 6 defines vocabulary).

### Doc-review gate

- [ ] Governing documents updated
- [ ] GLOBAL_PROJECT_CHECKLIST updated — Task 9
- [ ] DRIFT_REVIEW entry — Task 9
- [ ] ROADMAP Phase 3 → ✅ — Task 9

## 9. Promotion Note

План создан как `Status: Active` после одобрения Иваном 2026-05-15. После закрытия Phase 3 — `Status: Archived` с пойнтером на код.
