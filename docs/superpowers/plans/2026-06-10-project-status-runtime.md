# Project Status Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make project statuses control whether project chat work can start or resume.

**Architecture:** Centralize status validation and transition-event persistence in `ProjectStore`. Route Atrium dialog, project API/tool updates, and policy consent blocks through that contract.

**Tech Stack:** Python, SQLite, aiohttp, pytest

---

### Task 1: Central Status Contract

**Files:**
- Modify: `src/sonya/project/model.py`
- Test: `tests/sonya/test_atrium_e2e_reality_check.py`

- [ ] Add failing tests for accepted statuses, invalid status rejection, and `project.status_changed`.
- [ ] Run the focused tests and verify the new tests fail.
- [ ] Add `PROJECT_STATUSES`, `ProjectStatusError`, and `ProjectStore.set_status()`.
- [ ] Run the focused tests and verify they pass.

### Task 2: Atrium Dialog Status Gate

**Files:**
- Modify: `src/sonya/admin/server.py`
- Test: `tests/sonya/test_atrium_etap1.py`

- [ ] Add failing tests for `waiting_choice` auto-resume and read-only statuses.
- [ ] Run the focused tests and verify the new tests fail.
- [ ] Gate project dialog before writing incoming events.
- [ ] Run the focused tests and verify they pass.

### Task 3: Shared Explicit Updates And Consent Transition

**Files:**
- Modify: `src/sonya/admin/project_api.py`
- Modify: `src/sonya/tools/projects_tool.py`
- Modify: `src/sonya/subject/agent_session.py`
- Test: `tests/sonya/test_atrium_e2e_reality_check.py`

- [ ] Route explicit API/tool updates through `set_status()`.
- [ ] On a project consent block, set `waiting_choice`.
- [ ] Run project/Atrium/agent-session focused tests.

### Task 4: Deploy And Live Proof

**Files:**
- Modify: `docs/ATRIUM_PROJECT_PLAN.md`
- Modify: `docs/STATE.md`
- Modify: `docs/HANDOFF.md`

- [ ] Run focused tests and `git diff --check`.
- [ ] Commit and push the isolated status slice.
- [ ] Deploy with `deploy/update.sh`.
- [ ] Prove all five status behaviors over live HTTP.
- [ ] Record the exact result and remaining gaps.
