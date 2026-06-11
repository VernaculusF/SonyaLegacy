# Atrium Hosted Stack Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Atrium a proven end-to-end project workspace where the one Sonya can plan, execute, supervise, pause, resume, learn from, and complete project work through internal disposable subagents.

**Architecture:** Keep orchestration inside Sonya's project runtime. A model produces a small dependency graph when decomposition is useful; the executor persists the raw plan and parsed steps, schedules only dependency-ready workers, and synthesizes their results. Provider/account outcomes and project outcomes feed the shared substrate, while Atrium only exposes project progress and controls and Admin remains the provider operator surface.

**Tech Stack:** Python asyncio, SQLite substrate, aiohttp Admin/Atrium API, existing disposable subagent runtime, pytest, production VPS services.

---

## Fixed Boundaries

- Sonya remains one continuous environment and subject.
- Project chats are scoped work contexts, not new Sonyas.
- Subagents remain disposable internal tools and never become direct chat actors.
- Planning is model-driven with a minimal JSON envelope and safe single-task fallback, not a hard-coded rule engine.
- In-flight provider requests cannot be honestly paused; pause stops new scheduling, retries, and synthesis until resume.
- Production semantic dedup requires explicit approval. Non-destructive shared-memory proof does not.
- No local execution. Every red/green verification and substantial slice runs on the VPS after commit and push.

### Task 1: Autonomous dependency-aware project executor

**Files:**
- Modify: `tests/sonya/test_project_executor.py`
- Modify: `src/sonya/tools/projects_tool.py`
- Modify: `docs/ATRIUM_PROJECT_PLAN.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/STATE.md`

- [ ] Add a failing test proving `auto_plan=true` stores raw planner output and starts only dependency-ready steps.
- [ ] Push the test-only commit and verify the focused test fails on the VPS for the missing behavior.
- [ ] Make project execution methods async and call the existing provider with `purpose=project_planner`.
- [ ] Parse only a strict JSON object containing `steps[{id, task, depends_on}]`; fall back to one task on malformed output.
- [ ] Persist dependency state in `project_runs.steps_json` and preserve the raw planner response in an execution trace.
- [ ] On harvest, start newly-ready steps only after dependencies complete; propagate terminal dependency failures honestly.
- [ ] Synthesize successful planned runs with `purpose=project_synthesis`, while retaining every raw worker result.
- [ ] Verify focused and project/Atrium regression suites on the VPS, then deploy and record proof.

### Task 2: Measured scorecards and provider/account cooldowns

**Files:**
- Modify: `src/sonya/memory/tool_experience.py`
- Modify: `src/sonya/providers/keystore.py`
- Modify: `src/sonya/providers/llm_provider.py`
- Modify: provider and routing tests under `tests/sonya/`
- Modify: provider operations documentation

- [ ] Add failing tests proving worker outcomes update model scorecards and repeated account failures create a bounded cooldown.
- [ ] Preserve account identity in project/subagent outcome records.
- [ ] Aggregate success, error, latency, and recency into substrate-owned scorecards.
- [ ] Exclude cooling accounts during acquisition without disabling the provider or model.
- [ ] Clear or shorten cooldown after a successful probe.
- [ ] Verify routing and provider suites on the VPS and record live evidence.

### Task 3: Honest pause, approval, and resume

**Files:**
- Modify: `src/sonya/tools/projects_tool.py`
- Modify: `src/sonya/admin/project_api.py`
- Modify: Atrium project runtime frontend files
- Modify: project executor and Atrium tests

- [ ] Add failing tests for pause, approval-needed, decision submission, and resume.
- [ ] Persist orchestration pause state and stop new dependency scheduling, retries, and synthesis.
- [ ] Let already-running workers finish and label this behavior explicitly.
- [ ] Persist approval requests and decisions in project traces.
- [ ] Add Atrium controls and decision UI without exposing subagents as actors.
- [ ] Verify API, frontend build, and live VPS project flow.

### Task 4: Shared-memory production proof

**Files:**
- Modify: project outcome compiler/memory integration files discovered during implementation
- Modify: memory and project tests
- Modify: `docs/operations/MEMORY_KNOWLEDGE_MIGRATION_STATUS.md`

- [ ] Add a failing test proving a completed project's synthesized outcome enters shared Sonya memory with project provenance.
- [ ] Ensure raw subagent chatter does not enter long-term behavior memory.
- [ ] Run the existing non-destructive migration manifest and retrieval proof against a production backup.
- [ ] Verify project-scoped recall and global continuity from the same substrate.
- [x] Leave production semantic dedup unapplied until explicit approval.

### Task 5: Atrium project-chat end-to-end proof

**Files:**
- Modify: Atrium project frontend/API files only where the proof exposes gaps
- Modify: Atrium E2E tests
- Modify: `docs/ATRIUM_PROJECT_PLAN.md`
- Modify: `docs/FINAL_STATE_TODO.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/STATE.md`

- [x] Prove create/open project chat, folder binding, separate project history, execution progress, dependency steps, approval, pause/resume, completion, and shared-memory outcome.
- [x] Fix only gaps exposed by that proof.
- [x] Confirm the main chat remains the single home chat and Admin remains separate.
- [x] Run the full relevant VPS suite, deploy, inspect service journals, and record the final live scenario.

Live proof 2026-06-11:

- project: `proj-a83c1c3657`
- `GET /api/atrium/history?workspace_id=<project>` returned only the project
  proof message; main history returned the main proof message and no project
  workspace rows.
- project executor runtime showed dependency execution, pause/resume,
  approval-deny, completion, traces, and synthesized result through hosted API.
- shared memory contained one project-scoped semantic fact for the live proof.
- exposed and fixed two real gaps: initial history pagination returned old
  rows instead of newest rows, and `MemoryCompiler` could miss a completed
  `project_executor` run when newer subagent runs occupied the small run window.
