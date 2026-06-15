# Atrium Activity Plan

**Status:** Active — not yet implemented
**Last updated:** 2026-06-15
**Parent audit:** [`docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`](../SONYA_RUNTIME_COHERENCE_AUDIT.md) §5

## 1. Problem Statement

Atrium is currently a non-functional shell:

1. **No Atrium channel identity.** All messages from Atrium arrive as
   `channel="telegram_userbot"`. Sonya does not know she is talking to Ivan
   through Atrium.
2. **Shared code with admin.** Atrium backend endpoints (WS feed, dialog,
   upload, heartbeat, history, workshop, repo) live in `src/sonya/admin/`
   alongside operator-only endpoints (provider CRUD, selfmod governance,
   substrate inspection). No architectural boundary exists.
3. **States, emotions, and UI are frozen.** Avatar expression does not
   reliably reflect Sonya's emotional state. Mind pane, reason stream, and
   project workspace are connected to the event feed but Sonya does not
   produce enough internal events to make them alive. No read-receipt or
   delivery-confirmation path from Atrium back to Sonya.

## 2. Fixes Required

### 2.1 Atrium channel identity

**Current state:** When Ivan sends a message from Atrium, the frontend POSTs
to `/api/atrium/dialog`. The backend handler records `incoming.atrium_dialog`
but the channel resolution in Sonya's inbox treats it as `telegram_userbot`.

**Target state:**

- Messages from Atrium carry `channel="atrium"` through the entire pipeline
  (inbox → agent session → outbound → continuity stream).
- Sonya's outbound routing respects the channel: Atrium-originated messages
  get Atrium-visible responses, Telegram-originated messages get
  Telegram-visible responses.
- The history endpoint filters by source channel.

**Implementation:**

- Verify `incoming.atrium_dialog` events set `channel="atrium"` (not
  `channel="telegram_userbot"`).
- Verify `ChannelRegistry` routes outbound messages with `channel="dialog"`
  to both Telegram and Atrium when the conversation originated in Atrium.
- Verify Atrium's `/api/atrium/history` returns only Atrium-sourced dialog.
- Add Atrium-specific read-receipt: when Ivan opens a message in Atrium, fire
  `incoming.atrium_read_receipt` so Sonya knows the message was seen.

### 2.2 Atrium backend separation from admin

**Current state:** All Atrium endpoints live in `src/sonya/admin/server.py`
(~3145 lines). The admin SPA HTML is in `src/sonya/admin/static.py` (~1439
lines). Atrium frontend is at `packages/atrium/` but its backend is entangled
with admin.

**Target state (after monorepo split):**

- Atrium backend endpoints move out of `admin/server.py` into their own
  module or package.
- Admin endpoints stay in `SonyaAdmin/`. Atrium backend endpoints become part
  of `Atrium/` or a new backend package.
- Shared concerns (auth, substrate access) are extracted into dependency
  injection rather than direct import.

**Short-term (before monorepo split):**

- Separate Atrium route definitions from admin route definitions within
  `server.py`. Use separate `aiohttp.web.Application` sub-apps mounted at
  `/atrium/api/` vs `/api/admin/`.
- Move inline admin HTML to static files or a separate module.
- Ensure admin-only endpoints (provider CRUD, selfmod governance, substrate
  raw access) are not accessible from the Atrium auth flow.

### 2.3 Living UI — states, emotions, and feedback

**Current state:** Expression updates and internal thoughts reach the WS feed.
The UI components receive them but:

- Avatar expression changing in the feed does not reliably update the avatar
  component (stale state).
- Mind pane shows thoughts but Sonya produces them rarely because the model
  does not reliably emit `internal.thought` events.
- Reason stream shows tool calls but Sonya's tool usage is sparse in normal
  conversation.

**Target state:**

- Sonya's cognitive loop emits structured internal events at every step:
  `internal.thought` (what she's thinking), `internal.agent_step` (what she's
  doing), `internal.observation` (what she noticed). These feed the mind pane
  and reason stream.
- Expression classification runs on every response and updates the avatar
  state atomically. The WS client applies expression changes immediately.
- Read-receipts flow from Atrium to Sonya. She knows when Ivan has seen her
  messages.

**Implementation:**

- Require the agent session to emit `internal.thought` events at each ReAct
  step (thinking → acting → observing). Currently only tool-use actions emit
  events.
- Verify the `expression_classifier` output reaches the WS feed as
  `internal.expression_update` events.
- Add Atrium frontend: `onMessageRead` handler that POSTs to
  `/api/atrium/read-receipt`.
- Add backend: `/api/atrium/read-receipt` records `incoming.atrium_read`
  event and makes it available to Sonya's next cognitive tick.

## 3. Execution Order

These fixes must happen **after** the monorepo split (audit §2) and **before**
the marketer package (audit §8):

1. **Channel identity fix (2.1):** This is a backend code change in
   `src/sonya/channels/`, `src/sonya/subject/inbox.py`, and
   `src/sonya/initiative/outbound.py`. Can be done immediately.
2. **Route separation (2.2):** Restructure within `admin/server.py` before the
   full monorepo split. Separate Atrium and admin into sub-apps.
3. **Living UI (2.3):** Requires the agent session to produce more events.
   This is a prompt engineering + runtime change. Depends on web proxy models
   being available (audit §6) because weak models produce less coherent
   internal thought.

## 4. Acceptance Criteria

- [ ] Message sent from Atrium arrives in Sonya's inbox as
      `channel="atrium"`, NOT `channel="telegram_userbot"`.
- [ ] Sonya's reply to an Atrium message is visible in Atrium's dialog pane.
- [ ] Sonya's reply to an Atrium message does NOT appear in Telegram
      (unless the conversation explicitly requires both channels).
- [ ] Atrium history contains only Atrium-sourced messages.
- [ ] When Ivan reads a message in Atrium, Sonya receives a read-receipt
      event within one cognitive tick.
- [ ] Sonya emits at least one `internal.thought` event per cognitive step.
- [ ] Avatar expression updates when Sonya's emotional state changes.
- [ ] Admin endpoints and Atrium endpoints are served by separate sub-apps
      with separate auth scopes.
