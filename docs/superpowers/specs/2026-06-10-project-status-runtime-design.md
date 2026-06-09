# Project Status Runtime Design

**Status:** Approved
**Date:** 2026-06-10

## Goal

Make project statuses affect runtime behavior without turning statuses into a
hard orchestration rule engine or creating separate Sonya actors.

## Semantics

- `in_progress`: project chat accepts messages and work can continue.
- `waiting_choice`: the next user message is treated as the requested choice
  and automatically resumes the project to `in_progress`.
- `waiting`: project chat is read-only until an explicit status change.
- `completed`: project chat is read-only until explicitly reopened.
- `cancelled`: project chat is read-only until explicitly reopened.
- A project policy consent block changes an active project to
  `waiting_choice`.

## Architecture

`ProjectStore` owns the valid status set and status transitions. A transition
updates the project row and records a `project.status_changed` continuity event.
The API, project tool, Atrium dialog endpoint, and agent policy gate all call
the same transition method.

The status layer only controls whether project work may start or resume. Sonya
still decides how to perform work, whether to delegate, and which tools or
models to use.

## Error Handling

- Unknown status values are rejected.
- Messages to `waiting`, `completed`, or `cancelled` projects return HTTP 409.
- Messages to missing projects return HTTP 404.
- Main chat behavior is unchanged.

## Verification

- Unit tests cover valid/invalid transitions and transition events.
- Atrium tests cover automatic `waiting_choice` resume and read-only gates.
- Agent-session tests cover consent block -> `waiting_choice`.
- Production live proof covers all five statuses and cleanup.
