# Web Proxy Model Bridge

**Status:** Design parked; not implemented
**Last updated:** 2026-06-11

## Purpose

Give Sonya a unified way to use browser-backed web model accounts as cheap,
probe-gated worker capacity without binding Sonya herself to any single web
service. This is a provider tier for disposable subagents, one-shot code
examples, scratch reasoning, draft generation, and other low-cost work.

This layer is not the main Sonya loop. Sonya remains one environment with one
memory and one continuity stream. Web bridges are internal capacity adapters.

## Target Shape

Create a local Sonya-owned gateway over multiple web proxy projects:

- `freeqwen` from local `C:\Users\Jester\Desktop\Абузы\FreeQwenApi`
- `free-glm-kimi` from `ForgetMeAI/FreeGLMKimiAPI`
- `free-deepseek` from `ForgetMeAI/FreeDeepseekAPI`
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

## Known Candidate Bridges

### FreeQwenApi

Local source already exists at:

`C:\Users\Jester\Desktop\Абузы\FreeQwenApi`

Relevant observed facts:

- OpenAI-compatible endpoint is documented as `http://localhost:3264/api`.
- Supports `/api/chat/completions`, `/api/models`, `/api/health`.
- Has multi-account session state under `session/`.
- Current local tree contains secrets/session artifacts:
  `session/auth_token.txt`, `session/cookies.json`,
  `session/tokens.json`, `src/Authorization.txt`.
- Should be copied to VPS only as a protected runtime artifact, never through
  Git or documentation.

Phase 1 should make this a localhost-only VPS service.

### FreeGLMKimiAPI

Repository:

`https://github.com/ForgetMeAI/FreeGLMKimiAPI`

Observed public README facts:

- OpenAI-compatible `/v1/chat/completions`.
- Anthropic Messages shim `/v1/messages`.
- `/v1/models`, `/health`, `/sessions`.
- GLM/Z.ai and Kimi backends.
- Sticky sessions by `user` or agent id.
- Round-robin accounts and cooldown after provider errors.
- Prompt-based tool-use shim that normalizes tool calls.
- Mock mode for local tests.

Phase 2 should fork or vendor this into the Sonya web-bridge contract.

### FreeDeepseekAPI

Repository:

`https://github.com/ForgetMeAI/FreeDeepseekAPI`

Observed public README facts:

- OpenAI-compatible `/v1/chat/completions`.
- Anthropic Messages shim `/v1/messages`.
- OpenAI Responses shim `/v1/responses`.
- SSE streaming and non-stream JSON.
- Reasoning output through `reasoning_content`.
- Tool calling normalization.
- Agent sessions, session recovery, and multi-account pool.
- Headless VPS flow based on copied auth files with `0600` permissions.

Phase 3 should integrate this after Qwen and GLM/Kimi prove stable.

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

## Streaming Strategy

Some web bridges return text only after the upstream page finishes. The gateway
must expose progress even when true upstream streaming is unavailable:

- `queued`
- `account_selected`
- `upstream_loading`
- `generating`
- `final`

If the bridge supports real SSE, pass it through. If it does not, use synthetic
events and optionally chunk-replay the final answer. Do not pretend synthetic
chunking is real first-token streaming in telemetry.

Long-term improvement: capture browser DOM/network deltas in bridge-specific
adapters when practical, then expose them as real incremental output.

## Routing Policy

Recommended initial roles:

- `cheap_worker`
- `scratch_reasoner`
- `code_example`
- `subagent_executor`
- `bulk_draft`

Avoid by default:

- main Sonya answer loop
- memory consolidation
- irreversible selfmod apply
- security-critical autonomous actions
- tasks requiring guaranteed latency or availability

The picker can use these bridges when:

- task is disposable or retryable
- account/model probe is fresh
- no paid/premium capacity is needed
- failure can fall back to normal provider pools

## Account Lifecycle

Account/session automation belongs to Sonya's environment lifecycle, not to a
hardcoded provider hack. The bridge should expose hooks and state, but Sonya
decides when to refresh, relogin, retire, replace, or expand account capacity.

This document does not implement account creation or account recovery. Future
work must treat that as a governed Sonya capability tied to:

- `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md`
- `docs/core/SUBSTRATE_STANCE.md`
- protected secret storage
- truthful operator-visible telemetry

No bridge code may silently hide auth failures or fake capacity.

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

### Phase 2 - Unified Gateway

- Add Sonya-owned gateway in front of FreeQwenApi.
- Normalize `/health`, `/v1/models`, `/v1/chat/completions`.
- Normalize errors and account cooldowns.
- Record probe observations into substrate.
- Add synthetic progress events for non-streaming upstreams.

### Phase 3 - GLM/Kimi

- Fork or vendor `FreeGLMKimiAPI`.
- Map GLM and Kimi models into provider offerings.
- Verify tool-use shim with subagent tasks.
- Add account/session telemetry.

### Phase 4 - DeepSeek

- Fork or vendor `FreeDeepseekAPI`.
- Preserve reasoning output separately when available.
- Validate actual SSE streaming.
- Integrate multi-account pool only after auth-file handling is proven.

### Phase 5 - Atrium Visibility

Atrium should show high-level work traces:

- web proxy backend selected
- progress stage
- retries/cooldowns
- final result

Atrium must not become the account admin surface. Detailed account controls stay
in Admin.

## Open Technical Decisions

- Whether to vendor bridge repos into `third_party/` or deploy them as separate
  runtime directories.
- Whether the gateway is Python/aiohttp inside Sonya or Node/HTTP sidecar.
- How much synthetic streaming Atrium should display before it becomes
  misleading.
- Whether bridge-specific browser automation should be run on the same VPS or a
  separate worker host with GUI/browser support.

## Acceptance Criteria

- FreeQwenApi runs on VPS as localhost-only service.
- No bridge secret appears in Git, docs, logs, prompts, or continuity.
- Sonya can discover and probe web-proxy models.
- At least one Qwen model completes a tiny chat request through provider
  runtime.
- Failed models/accounts enter cooldown instead of being selected.
- Subagent picker can select `web_proxy` only for eligible low-cost roles.
- Normal provider pools remain available as fallback.
