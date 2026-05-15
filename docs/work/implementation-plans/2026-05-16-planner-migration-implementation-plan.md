# Planner Migration & CanonicalResponse Adoption Implementation Plan

**Status:** Active
**Type:** Work Doc
**Scope:** Move planner from tg-bridge into src/sonya/planning/. Bridge becomes thin adapter consuming CanonicalResponse. Planner reads subject_state, skills, initiative signals.
**Depends on:** [ROADMAP.md §13](C:/Users/Jester/Desktop/Sonya/docs/ROADMAP.md), [ARCHITECTURE_PLAN.md §4.2](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [CONTINUITY_STREAM_AND_SUBJECT_CORE.md §6.3](C:/Users/Jester/Desktop/Sonya/docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md)
**Used by:** Phase 7 implementation sessions
**Last reviewed:** 2026-05-16

## 1. Goal

After Phase 7:
- `src/sonya/planning/planner.py` — `plan_next(principal, subject_state, user_input, attachments) -> CanonicalResponse`
- Bridge calls `sonya.planning.plan_next` instead of its own `_plan_text_action_with_fallback`
- Bridge renders `CanonicalResponse` into Telegram messages (thin adapter)
- Planner reads initiative signals and can produce `CanonicalResponse(kind="initiative_proposal")`

## 2. Reference Check

### 2.1 OpenClaw
Anti-fake-agency rules from `sonya_runtime/actions/policy.py` migrate into `sonya.planning.policy`.

### 2.2 Hermes
Planner = brain. Bridge = shell. Boundary becomes physically correct.

### 2.3 OmniAgent
Reject 89KB single-file reflexion. Planner = 3-4 small modules.

## 3. Task List

### Task 1: Core planner module
- Create: `src/sonya/planning/__init__.py`, `src/sonya/planning/planner.py`, `src/sonya/planning/policy.py`
- `plan_next(context: PlannerContext) -> CanonicalResponse` — calls provider, parses action, returns CanonicalResponse
- `PlannerContext` dataclass: principal_id, subject_state, user_input, attachments, recent_continuity, initiative_signals, active_skills
- Policy: action validation (migrated from sonya_runtime/actions/policy.py)
- Tests with mocked provider

### Task 2: Bridge adapter
- Modify: `packages/tg-bridge/src/tg_bridge/app.py`, `handlers.py`
- Replace `_plan_text_action_with_fallback` with call to `sonya.planning.plan_next`
- Bridge renders CanonicalResponse → Telegram messages
- All existing bridge tests must pass (regression)

### Task 3: Initiative integration
- Planner checks `initiative_signals` from Phase 6
- Can produce `CanonicalResponse(kind="initiative_proposal")` for outbound messages
- Bridge renders initiative proposals same as replies

### Task 4: Layer boundary + closure
- Extend AST test for planning/
- Update docs, archive plan

## 4. Verification
- All bridge tests pass (regression)
- `grep "plan_text_action" packages/tg-bridge/` → only API call, not own implementation
- New tests in `tests/sonya/test_planner.py`
