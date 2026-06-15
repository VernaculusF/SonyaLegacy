# Web Proxy Model Bridge

**Status:** Active design — promoted from parked to primary provider strategy
**Last updated:** 2026-06-15
**Parent audit:** [`docs/SONYA_RUNTIME_COHERENCE_AUDIT.md`](../SONYA_RUNTIME_COHERENCE_AUDIT.md) §6

## Purpose

Give Sonya access to high-quality models through browser-backed web model
accounts. This is no longer just a cheap worker tier — it is the primary path
to models significantly better than OpenRouter free-tier, which is the root
cause of selfmod failures, weak cognition, and project execution unreliability.

Web bridges are internal capacity adapters. Sonya remains one environment with
one memory and one continuity stream. Web bridges are provider accounts, not
separate UX actors.

## Strategic Shift (2026-06-15)

The original routing policy restricted webProxy to low-cost roles only. This
is updated:

- Web proxy models (DeepSeek, Z.ai/GLM, Kimi, Qwen) are **significantly
  stronger** than free-tier OpenRouter models.
- The weak-model problem directly causes selfmod pipeline deadlocks, reduces
  cognitive quality, and makes project execution unreliable.
- Web proxy bridges should be **preferred** for cognition-heavy roles
  (reasoning, planning, code generation, selfmod) where latency tolerance
  exists and model quality matters more than guaranteed uptime.
- OpenRouter free-tier becomes the **fallback** for roles requiring guaranteed
  availability or low latency.

### Updated Routing Policy

| Role | Preferred tier | Fallback |
|---|---|---|
| Main cognition (planning, reasoning) | web_proxy (DeepSeek, GLM) | OpenRouter |
| Selfmod proposal generation | web_proxy (DeepSeek) | — |
| Selfmod validation | OpenRouter (fast, stateless) | web_proxy |
| Subagent executor | web_proxy (cheapest available) | OpenRouter |
| Code generation | web_proxy (DeepSeek) | OpenRouter |
| Quick responsive chat | OpenRouter (low latency) | — |
| Memory consolidation | web_proxy (reasoning models) | OpenRouter |
| Irreversible selfmod apply | **Both** (dual validation) | — |

## API vs Web Chat: Key Engineering Differences

Web scraping is fundamentally different from API calls. The bridge must handle
these differences transparently:

| Aspect | API | Web chat (scraping) |
|---|---|---|
| Authentication | Bearer token | Session cookies, browser auth state |
| Request format | JSON POST | DOM interaction via Puppeteer / CDP |
| Streaming | SSE chunks | Progressive text rendering in DOM |
| Context window | Explicit token limit | Same backend model, but web UI may silently truncate early context on long conversations |
| Rate limiting | HTTP 429 headers | CAPTCHA, session expiry, invisible throttling, page changes |
| Error signals | Status codes | Page structure changes, blank responses, redirect to login, CAPTCHA page |
| Session persistence | Stateless | Stateful — conversation history in browser session |
| Tool calling | Structured JSON | Prompt-injected patterns, often unreliable or unavailable |
| Latency | Predictable (100ms-2s first token) | Variable (1s for real streaming, 5-60s for non-streaming bridges) |
| Availability | High (provider SLA) | Low-medium (account bans, CAPTCHA, session expiry) |

### Context Window Details

Web chat interfaces (DeepSeek, Z.ai, ChatGPT) use the same backend models as
their API counterparts, so the **effective context window is the same**. However:

- Web UIs may silently truncate early context when the page conversation grows
  too long, without any explicit signal.
- There is no reliable API to detect when truncation has occurred. The bridge
  must implement:
  1. **Proactive context summarization:** Before sending a long conversation,
     summarize the earliest turns and carry the summary forward as a system
     message, similar to how humans "forget" the exact wording of early
     conversation but retain the gist.
  2. **Truncation detection heuristics:** If the model's response references
     information from early context that was just provided, but ignores mid-
     context information, the bridge should flag potential truncation.
  3. **Context budget tracking:** The bridge maintains a running token estimate
     per conversation. When it exceeds 70% of the known context window, it
     triggers proactive summarization.

## Target Shape

Create a local Sonya-owned gateway over multiple web proxy projects:

- `freeqwen` from local `C:\Users\Jester\Desktop\Абузы\FreeQwenApi`
- `free-glm-kimi` from `ForgetMeAI/FreeGLMKimiAPI`
- `free-deepseek` from `ForgetMeAI/FreeDeepseekAPI`
- **new:** `free-chatgpt` — ChatGPT web interface bridge (to be built or
  found)
- later: other web accounts if they can be wrapped behind the same contract

The gateway exposes a normal provider surface:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`
- optional `POST /v1/responses`
- optional `POST /v1/messages`
- account status without raw credentials
- model probe status
- cooldown and failure observations

Sonya then sees one provider tier: `web_proxy`. Individual bridges are
accounts/backends inside that tier, not separate UI actors.

## Streaming Implementation

### Real streaming bridges (DeepSeek, GLM/Kimi via FreeDeepseekAPI/FreeGLMKimiAPI)

These bridges support SSE streaming natively through their OpenAI-compatible
endpoints. Pass through directly.

### DOM-based streaming (for raw web scraping when API bridges are unavailable)

When connecting directly to a web interface that renders text progressively:

1. Connect via Chrome DevTools Protocol (CDP) or Puppeteer.
2. Observe DOM mutations on the response container element.
3. Extract incremental text deltas as they appear.
4. Expose deltas as real SSE chunks to Sonya's provider layer.
5. Signal completion when DOM stabilizes (no new text for 2+ seconds) or when
   the "stop generating" / "regenerate" button appears.

### Non-streaming bridges (bulk response after waiting)

Some web bridges return text only after the upstream page finishes. The gateway
must expose synthetic progress events:

- `queued`
- `account_selected`
- `upstream_loading`
- `generating`
- `final`

Do not pretend synthetic chunking is real first-token streaming in telemetry.

## Account Pool Design

### Minimum pool size: 10 accounts per service

Each service (DeepSeek, Z.ai, Qwen, ChatGPT, Kimi) must have at least 10
accounts provisioned by Ivan. Accounts are consumable resources.

### Account lifecycle

- **New:** Account created by Ivan, credentials stored as protected secrets
  under `~/.sonya/web-proxy-secrets/` with `0600` permissions.
- **Active:** Account passes health check and has fresh auth state. Eligible
  for routing.
- **Cooldown:** Account hit a rate limit or transient error. Not selected for
  N minutes. Automatically promoted back to Active after cooldown expires.
- **Auth_required:** Session expired or CAPTCHA detected. Requires manual
  intervention (Ivan relogs in browser, or自动化 re-auth via stored credentials).
- **Broken:** Account is permanently disabled (banned, credentials revoked).
  Must be replaced by Ivan.
- **Disabled:** Operator explicitly disabled the account.

### Rotation strategy

- Round-robin among Active accounts.
- On failure: mark current account as the appropriate failure state, select
  next Active account, retry.
- No account should be used more than 2x consecutively if alternatives exist.
- Cooldown duration scales with failure class:
  - Rate limit: 5-15 minutes
  - CAPTCHA: until manual intervention
  - Auth expired: until re-auth
  - Upstream error: 30 seconds
  - Timeout: 1 minute

### Account provisioning by Ivan

Ivan provides accounts. The bridge must NOT auto-create accounts. Account
creation automation belongs to Sonya's environment lifecycle, not to the
bridge:

- `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`
- `docs/core/SUBSTRATE_STANCE.md`
- protected secret storage
- truthful operator-visible telemetry

No bridge code may silently hide auth failures or fake capacity.

## Deployment Rule

Default deployment is localhost-only:

- bind to `127.0.0.1`
- no public firewall opening
- systemd service per bridge or one supervised gateway
- secrets under `~/.sonya/web-proxy-secrets/` or equivalent
- `0600` secret files
- logs must not include cookies, bearer tokens, auth JSON, or raw prompts when
  prompt logging is not explicitly enabled for debugging

If Ivan later wants external access, it must go through a separate authenticated
operator gateway, not by exposing the raw bridge ports.

## Remote Browser Worker

The Google VPS cannot run browser-facing bridges directly (anti-bot challenges
block Puppeteer). The solution is a remote browser worker:

1. Run the browser-facing bridge on a connected machine/network where the web
   application works normally (Ivan's PC, a residential proxy, or a VPS with
   residential IP).
2. Expose only a Sonya-owned authenticated gateway over the existing remote
   workspace/worker transport.
3. Keep provider discovery on the VPS, but enable account offerings only after
   end-to-end live probes through that remote worker.
4. Add synthetic progress events only after completion is reliable.

Do not solve this by publishing bridge ports, marking catalog entries available,
or weakening probe requirements.

## Provider Runtime Contract

Each bridge backend must report:

- backend id, e.g. `freeqwen`, `free-glm-kimi`, `free-deepseek`
- account id or session id, masked
- current status: `active`, `cooldown`, `auth_required`, `broken`, `disabled`
- model list
- last probe result per model/account
- latency estimate
- failure class: auth, rate limit, captcha/manual-login required, upstream
  changed, timeout, malformed response

Offerings are enabled only after probe. The provider runtime must not trust a
static model list.

## Interface to Subagents

Subagents do not talk to bridge accounts directly. Sonya selects a model through
the normal provider picker and receives traces:

- requested role
- selected backend/model/account
- probe freshness
- failure/cooldown if any
- output summary

Raw bridge logs stay operational. Only useful summaries and lessons enter
shared memory.

## Implementation Phases

### Phase 1 - FreeQwenApi VPS Service

- Copy local FreeQwenApi to VPS outside the Sonya repo.
- Copy `session/` and auth files as protected runtime secrets.
- Install Node dependencies on VPS.
- Run as `127.0.0.1:3264` under systemd.
- Verify `/api/health`, `/api/models`, and one tiny chat completion.
- Register provider `freeqwen` as `web_proxy` / OpenAI-compatible local bridge.
- Probe every advertised model before enabling offerings.

**Status:** Infrastructure deployed, inference blocked by anti-bot on Google
VPS. Remote browser worker required.

### Phase 2 - Remote Browser Worker

- Set up a remote browser worker on a machine with residential IP (or Ivan's
  PC with port forwarding).
- Bridge connects to the worker via authenticated transport.
- Provider discovery stays on VPS; live probes route through the worker.
- Verify end-to-end: VPS → gateway → remote worker → web service → response.

### Phase 3 - Unified Gateway

- Add Sonya-owned gateway in front of all bridges.
- Normalize `/health`, `/v1/models`, `/v1/chat/completions`.
- Normalize errors and account cooldowns.
- Record probe observations into substrate.
- Implement context budget tracking and proactive summarization.
- Add synthetic progress events for non-streaming upstreams.

### Phase 4 - DeepSeek (highest priority after gateway)

- Fork or vendor `FreeDeepseekAPI`.
- Preserve reasoning output separately when available.
- Validate actual SSE streaming.
- Integrate multi-account pool with 10+ accounts.
- Prove reasoner-quality model access for Sonya's main cognition.

### Phase 5 - GLM/Kimi

- Fork or vendor `FreeGLMKimiAPI`.
- Map GLM and Kimi models into provider offerings.
- Verify tool-use shim with subagent tasks.
- Add account/session telemetry.

### Phase 6 - Additional Services

- ChatGPT web interface bridge (if feasible).
- Any future services that can be wrapped behind the same contract.

### Phase 7 - Atrium Visibility

Atrium should show high-level work traces:

- web proxy backend selected
- progress stage
- retries/cooldowns
- final result

Atrium must not become the account admin surface. Detailed account controls
stay in Admin.

## Acceptance Criteria

- At least one web proxy bridge completes a live inference probe end-to-end
  through the remote browser worker.
- No bridge secret appears in Git, docs, logs, prompts, or continuity.
- Sonya can discover and probe web-proxy models.
- At least one DeepSeek model completes a reasoning-quality chat request
  through provider runtime.
- Failed models/accounts enter cooldown instead of being selected.
- Provider picker can route cognition-heavy roles to web_proxy.
- Web proxy models are available for selfmod proposal generation.
- Normal provider pools remain available as fallback.
- Context budget tracking prevents silent truncation.
- Account pool has at least 10 accounts per service.

## Production Status - 2026-06-15

Phase 1 infrastructure is deployed, but FreeQwen inference is blocked on the
current Google VPS:

- FreeQwenApi runtime is outside Git at
  `/home/jester-sonya/.sonya/web-proxy/freeqwen`.
- `sonya-freeqwen.service` runs as `jester-sonya`, binds only
  `127.0.0.1:3264`, and has a bounded 20-second shutdown.
- existing Qwen session artifacts are mode-protected; the local proxy API key
  exists only in the runtime and encrypted provider substrate.
- provider `freeqwen` is registered with adapter kind `web_proxy`.
- every advertised web-proxy model must pass a live tiny inference probe before
  its account offering becomes eligible.
- `/api/health` and `/api/models` return `200`; the bridge advertises 27 models.
- live completion is not proven. `chat.qwen.ai` serves an anti-bot AES
  challenge page to the Google VPS instead of the current application/API.
  The old bridge then stalls inside Puppeteer and its obsolete
  `/api/v2/chats/new` call returns HTML rather than JSON.
- no FreeQwen model is enabled in Sonya. This is deliberate.

The next step is Phase 2 (remote browser worker). DeepSeek integration (Phase
4) is the highest-value target once the gateway is ready.
