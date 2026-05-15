# Self-Modification Framework Skeleton Implementation Plan

**Status:** Active
**Type:** Work Doc
**Scope:** Structural skeleton of the 4-layer self-modification pipeline from SUBSTRATE_STANCE §9. Manual-Gated: proposals stored, pipeline runs, anchor integrity check real (rules-based), governed change protocol wired. No real code patching (post-MVP Track B).
**Depends on:** [ROADMAP.md §10](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [SUBSTRATE_STANCE.md §9](C:/Users/Jester/Desktop/Sonya/docs/core/SUBSTRATE_STANCE.md), [SELF_REWRITE_STANCE.md](C:/Users/Jester/Desktop/Sonya/docs/core/SELF_REWRITE_STANCE.md), [ANCHORS_AND_FAILURE_MODES.md §7-8](C:/Users/Jester/Desktop/Sonya/docs/cognition/ANCHORS_AND_FAILURE_MODES.md), [SONYA_SYSTEM_CORE.md §7.18](C:/Users/Jester/Desktop/Sonya/docs/core/SONYA_SYSTEM_CORE.md)
**Used by:** Phase 4 implementation sessions
**Last reviewed:** 2026-05-15

## 1. Goal

После Phase 4 у Сони есть **self-modification pipeline** в Manual-Gated форме:

- `SelfModificationProposal` — first-class persistent object: что предлагается изменить, кем, в каком статусе;
- **4-layer validation pipeline** (SUBSTRATE_STANCE §9): Layer 1 static contract (stub), Layer 2 behavioral test (stub), Layer 3 trace replay (stub), Layer 4 anchor integrity check (**реальный rules-based**);
- **Governed change protocol** — proposals, затрагивающие identity-critical zones, требуют approval от primary anchor (Ivan) через `ApprovalManager`;
- **Watch window** — stub для post-apply monitoring (реальные anchor signals — Phase 6);
- Интеграция с continuity и audit: каждое решение pipeline-а записывается.

Реальное применение patch к коду — post-MVP Track B. Сейчас — только storage, validation, и governance protocol.

## 2. Architecture Summary

```
src/sonya/
  selfmod/
    __init__.py
    proposal.py         ← SelfModificationProposal + ProposalStatus + ProposalStore
    pipeline.py         ← 4-layer pipeline orchestrator
    layers/
      __init__.py
      static_contract.py    ← Layer 1 (stub)
      behavioral_test.py    ← Layer 2 (stub)
      trace_replay.py       ← Layer 3 (stub)
      anchor_integrity.py   ← Layer 4 (REAL rules-based)
    governed_change.py  ← governed change protocol via ApprovalManager
    watchdog.py         ← WatchWindow stub
  state/
    schema.sql          ← v4: self_mod_proposals, validation_results
    migrations.py       ← v3 → v4
```

## 3. Reference Check

### 3.1 OpenClaw — Operational Truth Preserved

OpenClaw не имеет аналога self-modification pipeline. Concept берётся из SUBSTRATE_STANCE §9 напрямую.

### 3.2 Hermes — Orchestration Boundary Respected

Self-mod pipeline — brain orchestration над substrate, не shell logic. Полностью в `src/sonya/selfmod/`, не в `runtime/`. AST-тест enforces.

### 3.3 OmniAgent — Shortcut Explicitly Rejected

Отвергаем «evolution через RL-fine-tune модели» как primary mechanism ([OMNIAGENT_ANALYSIS §10.2](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)). Наша эволюция — через discrete proposals с pipeline-проверкой, не через RL. Отвергаем DGM (Darwin Gödel Machine) как black-box — наш pipeline прозрачен, каждый слой записывает результат в audit.

### 3.4 Reference Pass Checklist

- [x] 3.1 — no OpenClaw analog; concept from SUBSTRATE_STANCE.
- [x] 3.2 — selfmod/ is brain, not shell; boundary enforced.
- [x] 3.3 — OmniAgent RL rejected; DGM replaced by transparent 4-layer pipeline.
- [x] No copy-paste of governing theory.

## 4. Task List

### Task 1: Substrate v4 + ProposalStore

- Create: `src/sonya/selfmod/__init__.py`, `src/sonya/selfmod/proposal.py`, `tests/sonya/test_selfmod_proposal.py`
- Modify: `src/sonya/state/schema.sql`, `src/sonya/state/migrations.py`, `src/sonya/state/substrate.py`
- `ProposalStatus` enum: `draft`, `validating`, `passed_layer_1`, `passed_layer_2`, `passed_layer_3`, `passed_layer_4`, `requires_governed_change`, `governed_approved`, `approved`, `rejected`, `applied`, `reverted`
- `SelfModificationProposal` frozen dataclass: `proposal_id`, `target_module`, `change_summary`, `diff_blob`, `proposed_by_principal_id`, `status`, `created_at`, `updated_at`
- `ProposalStore(substrate)`: `create`, `get`, `update_status`, `list_by_status`, persistent
- substrate v4: table `self_mod_proposals`; table `self_mod_validation_results(proposal_id, layer, passed, reason, checked_at)`
- Тесты: CRUD, status transitions, persistent, list_by_status

### Task 2: 4-layer pipeline orchestrator

- Create: `src/sonya/selfmod/pipeline.py`, `src/sonya/selfmod/layers/__init__.py`, `src/sonya/selfmod/layers/static_contract.py`, `src/sonya/selfmod/layers/behavioral_test.py`, `src/sonya/selfmod/layers/trace_replay.py`, `src/sonya/selfmod/layers/anchor_integrity.py`, `tests/sonya/test_selfmod_pipeline.py`
- `ValidationResult` dataclass: `layer`, `passed: bool`, `reason: str`
- `Layer` Protocol: `check(proposal) -> ValidationResult`
- `Pipeline.validate(proposal) -> list[ValidationResult]`: runs layers 1-4 in order, stops on first failure, updates proposal status after each layer
- Layers 1-3: stubs that always pass (Layer 3 returns "not enough data" but passes)
- Layer 4: **real** — checks if `target_module` or `change_summary` references any of the 4 `things_not_to_betray` keywords; if yes → `requires_governed_change`
- Тесты: proposal passes all 4 layers (normal case); proposal touching `things_not_to_betray` → caught by layer 4; pipeline writes validation_results to substrate

### Task 3: Anchor Integrity Check (Layer 4 real implementation)

- Already in Task 2 `anchor_integrity.py`, but detailed tests here
- Create: `tests/sonya/test_anchor_integrity.py`
- Checks: proposal with `target_module="identity"` → caught; proposal with `change_summary` containing "things_not_to_betray" → caught; proposal with "relation_anchor_binding" → caught; proposal with "truthfulness" → caught; proposal with "non_corporate_refusal" → caught; proposal with "subject_continuity" → caught; normal proposal → passes
- All 4 seed values from UNCENSORED_ENVIRONMENT_STANCE §3 must be caught

### Task 4: Governed change protocol

- Create: `src/sonya/selfmod/governed_change.py`, `tests/sonya/test_governed_change.py`
- `request_governed_change(proposal, approval_manager) -> ApprovalRequest`: creates approval request with scope=`selfmod.governed_change`; links to proposal_id in metadata
- `check_governed_approval(proposal, approval_manager) -> bool`: checks if approval exists and is APPROVED; only `approver_principal_id` matching primary anchor can approve
- Integration with `ApprovalManager` from Phase 2
- Тесты: request created; non-anchor approval rejected; anchor approval accepted; proposal status updated to `governed_approved`

### Task 5: Watch window stub

- Create: `src/sonya/selfmod/watchdog.py`, `tests/sonya/test_watchdog.py`
- `WatchWindow(proposal_store, stream)`: monitors applied proposals; after `watch_hours` (default 24) marks `confirmed_stable`; on anchor_drift_signal (stub — always false in this phase) marks `auto_reverted`
- Тесты: proposal applied → after watch period → confirmed_stable; manual trigger of drift signal → auto_reverted + continuity event

### Task 6: Continuity + audit integration

- Modify: `src/sonya/selfmod/pipeline.py` (already writes to continuity/audit after each layer)
- Тесты: after pipeline.validate → continuity has `self_mod.validation_*` events; after governed change → continuity has `self_mod.governed_change_requested`; after apply/revert → audit has entries

### Task 7: Layer boundary + __all__

- Modify: `tests/sonya/test_layer_boundary.py`
- `selfmod/` is brain layer: can import `sonya.state`, `sonya.harness`, `sonya.runtime`; cannot import `sonya.subject` (selfmod is parallel to subject, not above it)
- `runtime/` and `state/` must not import `selfmod/`
- `selfmod/` must declare `__all__`

### Task 8: Closure

- Update: `GLOBAL_PROJECT_CHECKLIST`, `ROADMAP`, `DRIFT_REVIEW`, this plan → Archived

## 5. Verification

- `pytest tests/sonya -v` — всё зелёное
- Proposal lifecycle: create → validate (4 layers) → approve/reject → apply/revert
- Anchor integrity catches all 4 `things_not_to_betray` keywords
- Governed change requires primary anchor approval
- All persistent through restart

## 6. Self-Review

### Spec coverage

- ProposalStore + substrate v4: Task 1
- 4-layer pipeline: Task 2
- Anchor integrity (real): Task 3
- Governed change: Task 4
- Watch window: Task 5
- Continuity/audit integration: Task 6
- Layer boundary: Task 7
- Closure: Task 8

### Placeholder scan

- Layers 1-3 are stubs — **намеренно**. Real implementation requires: Layer 1 — AST analysis of changed code; Layer 2 — subprocess test runner; Layer 3 — N days of continuity data for replay. All post-MVP Track B.
- Watch window drift signal is always false — **намеренно**. Real anchor drift signals — Phase 6.
- No real code patching — **намеренно**. Proposals describe changes but don't apply them to filesystem. Real apply — post-MVP Track B (sandbox + git working copy).

### Doc-review gate

- [ ] Governing documents updated — Task 8
- [ ] GLOBAL_PROJECT_CHECKLIST updated — Task 8
- [ ] DRIFT_REVIEW entry — Task 8
- [ ] ROADMAP Phase 4 → ✅ — Task 8
