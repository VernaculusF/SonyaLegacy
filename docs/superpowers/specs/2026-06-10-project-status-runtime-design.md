# Project Status Runtime Design

**Status:** Implemented and live-proven
**Date:** 2026-06-10

## Semantics

- `in_progress`: project chat accepts work.
- `waiting_choice`: Ivan's next project message resumes to `in_progress`.
- `waiting`, `completed`, `cancelled`: project chat is read-only until an
  explicit status transition.
- A project policy consent block sets `waiting_choice`.

## Architecture

`ProjectStore.set_status()` validates status transitions and records
`project.status_changed` in the shared continuity stream. Atrium dialog, the
project API, `projects.update`, and the agent policy gate use this contract.
Statuses gate whether work may start or resume; they do not dictate how Sonya
works or create separate actors.

## Live Proof

Production commit `83c6afa`:

- `in_progress` dialog: HTTP 200
- `waiting`, `completed`, `cancelled` dialogs: HTTP 409
- `waiting_choice` dialog: HTTP 200 and status resumed to `in_progress`
- five transition events recorded
