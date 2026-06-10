# Atrium Answer-First Reply Design

**Status:** Approved
**Date:** 2026-06-09
**Scope:** First vertical slice of `ATRIUM_PROJECT_PLAN.md` Workstream A

## Goal

Make explicit Sonya answers reach Atrium as answers without rebuilding them
from internal reasoning or deleting useful answer content.

## Decision

- `chat.dialog` remains the primary explicit answer path and is dispatched
  immediately.
- `[DONE: body]` remains the explicit final-answer fallback.
- Explicit answer bodies receive only minimal protocol sanitization:
  internal `<think>` blocks, tool markers, observation echoes, and terminal
  markers are removed.
- Markdown and fenced code inside explicit answers are preserved.
- Internal `thoughts` remain reason-stream / trace data and are never joined
  into an explicit Atrium answer.
- The existing heuristic `_scrub()` and thought-stitching behavior remain only
  as a compatibility fallback for the Telegram channel path.
- Provider-native reasoning fields are out of scope for this slice.

## Data Flow

1. The model calls `chat.dialog`, or closes an active/project session with
   `[DONE: body]`.
2. `chat.dialog` sends its body directly through the outbound gate.
3. `[DONE: body]` passes through the minimal explicit-answer sanitizer.
4. The sanitized body is dispatched to `outgoing.dialog`.
5. Internal thoughts continue to be recorded as `internal.agent_step` and
   execution traces.

## Failure Handling

- If an explicit body becomes empty after removing internal-only content, it
  is not dispatched.
- Existing inbox/report gates continue to require a real answer.
- The legacy heuristic extractor remains available for malformed non-explicit
  Telegram output.

## Verification

- Unit test: explicit answer sanitizer preserves fenced code.
- Agent-session test: `[DONE: body]` dispatch preserves fenced code and removes
  `<think>`.
- Regression suite: reply extraction, inbox gate, Atrium dialog, and frontend
  build.
- VPS smoke test: deploy, verify services, send a live Atrium prompt that asks
  for a fenced code response.
