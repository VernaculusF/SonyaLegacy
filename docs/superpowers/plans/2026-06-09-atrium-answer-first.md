# Atrium Answer-First Reply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve explicit Atrium answers while keeping reasoning and protocol noise out of the visible dialog.

**Architecture:** Add a minimal sanitizer dedicated to explicit answer bodies and use it for `[DONE: body]` dispatch. Keep the existing heuristic scrubber and thought stitching only for legacy Telegram fallback extraction.

**Tech Stack:** Python, pytest, Solid/Vite frontend verification, systemd VPS deployment

---

### Task 1: Explicit Answer Sanitizer

**Files:**
- Modify: `src/sonya/subject/channel_session.py`
- Test: `tests/sonya/test_tool_result_echo_leak.py`

- [x] Add a failing test proving an explicit answer keeps fenced code while
  removing `<think>` and protocol markers.
- [x] Run the focused test and confirm it fails because the sanitizer does not
  exist.
- [x] Implement `_sanitize_explicit_answer(text: str) -> str` using only
  protocol-marker removal and whitespace normalization.
- [x] Run the focused test and existing reply-extraction regression tests.

### Task 2: Explicit DONE Dispatch

**Files:**
- Modify: `src/sonya/subject/agent_session.py`
- Test: `tests/sonya/test_agent_session_inbox_gate.py`

- [x] Add a failing agent-session test where `[DONE: body]` contains fenced
  code and `<think>`.
- [x] Run the focused test and confirm current `_scrub()` removes the code.
- [x] Replace `_scrub()` with `_sanitize_explicit_answer()` only in the
  explicit `[DONE: body]` dispatch path.
- [x] Run inbox-gate, auto-ack, reply-extraction, and Atrium tests.

### Task 3: Verification and Handoff

**Files:**
- Modify: `docs/ATRIUM_PROJECT_PLAN.md`
- Modify: `docs/STATE.md`
- Modify: `docs/HANDOFF.md`

- [x] Run the full Python test suite.
- [x] Build `packages/atrium`.
- [ ] Deploy to VPS with `bash ~/Sonya/deploy/update.sh`.
- [ ] Verify `sonya.service` and `sonya-admin.service`.
- [x] Verify the focused suite in an isolated VPS repository copy.
- [ ] Perform a live Atrium fenced-code reply smoke test.
- [ ] Record completed scope, verification evidence, and next Workstream A
  step in the three active project documents.
