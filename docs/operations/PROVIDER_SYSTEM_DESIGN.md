# Provider and Model Runtime Design

**Status:** Approved target design
**Last updated:** 2026-06-10

## Decision

Do not load the newly supplied credentials into the current runtime yet.
First migrate away from the remaining fixed-model key assumptions, then
bootstrap a minimal provider set through a secret-safe management path.

Provider/model choice is not process configuration. Environment variables must
not bind Sonya to a provider, account, or model. Provider definitions,
accounts, offerings, preferences, observations, and routing state live in the
substrate and remain manageable by Sonya.

Deployment configuration may supply reader-level unlock material for encrypted
secret storage, but that unlock material is not a provider credential and does
not select a model.

New provider credentials enter through a protected secret-ingestion action
that writes an encrypted provider-account secret into substrate. They must not
be passed as command-line arguments, provider-specific environment variables,
continuity payloads, or ordinary tool traces.

Implemented protected path:

- first create provider/account metadata without a raw credential;
- authenticated Admin `PUT /api/providers/accounts/{account_id}/secret`
  accepts only an opaque `application/octet-stream` body;
- the handler immediately encrypts and rotates the account secret;
- response and audit records contain only `secret_ref` and masked metadata;
- ordinary account JSON, `providers.add_account`, legacy
  `providers.add_key`, and legacy `/api/providers/keys` reject raw credentials.

The runtime must model this chain:

`provider definition -> accounts/credentials -> account model offerings -> observations -> routing decision`

## Data Boundaries

### Provider Definition

Non-secret integration metadata:

- `provider_id`, display name, operational status
- adapter kind: `openai_compatible`, `google_native`, `anthropic_compatible`,
  `cli_bridge`, or `browser_bridge`
- base endpoints and supported API modes
- discovery, balance, usage, and health capabilities
- provider-wide constraints and refresh TTL

### Provider Account

An account or credential, not a model:

- `account_id`, `provider_id`, label, priority, status
- encrypted secret reference
- account-specific restrictions and model access
- observed balance and quota windows
- cooldown, failure counters, last successful probe

One provider may have many accounts. Different accounts may expose different
models or quotas.

### Model Identity and Offering

A model identity describes a model family. A provider offering describes one
way to call it:

- provider + model API ID + eligible account set
- context, modalities, API modes, tool/stream/structured-output support
- advertised pricing and limits
- discovery source, last verified time, enabled state

Offerings are many-to-many with accounts because access can differ by account.

### Observations

Runtime truth must be timestamped:

- quota/balance windows and reset times
- request success, latency, usage, errors, refusal/constraint signals
- evaluation and production scorecards by task class

Historical observations must not overwrite provider-advertised metadata. Both
remain inspectable.

## Sonya Management Contract

Ivan should be able to say: "add this provider, these accounts, and these
models." Sonya interprets the request and uses typed internal capabilities.
Natural language is the UX; typed service/tool calls are the reliable execution
boundary.

Required capabilities:

- create/update/disable/delete provider definitions
- securely add/rotate/disable/delete accounts and credentials
- discover/refresh model offerings
- inspect balances, quotas, health, and account-specific access
- pin preferences or constraints without fixed model bindings
- run probes and evaluations

Raw database writes and smart parsing of conversational text are not management
interfaces.

## Secret Rules

- Never store raw credentials in Git, docs, traces, continuity, or prompts.
- Do not use provider-specific environment variables as runtime account/model
  configuration.
- Persist encrypted secrets or references to an external secret store.
- Mask secrets in every read surface.
- Separate credential metadata from secret material.
- Audit secret-changing actions without logging the secret.
- Require an authenticated protected ingestion action; refuse ingestion when
  the Admin authentication secret is not configured.
- Treat credentials pasted into chat as exposed and rotate them when practical.

## Discovery and Refresh

Each adapter declares capabilities. A scheduler refreshes supported metadata
with per-provider TTL and preserves the last good snapshot on failure.

- OpenRouter: live models/endpoints discovery.
- Google AI Studio: native model discovery; quotas are account/project
  observations.
- OpenAI-compatible providers: probe `/models` when supported.
- Bridges: adapter-specific structured discovery.
- Manual-only providers: explicit offerings marked `manual`.

Documentation is bootstrap/reference material. Substrate is runtime truth.

## Routing

Routing is two-stage:

1. Filter by required capability, eligible account, health, context, and budget.
2. Rank by evidence: task scorecards, latency, cost, remaining quota, and
   Sonya's stated preferences.

Remove hard-coded purpose-to-model maps and permanent provider fallback chains.
Keep emergency defaults only as explicit, visible recovery configuration.

## Current Runtime

The substrate v33 runtime now has first-class providers, accounts,
account-offering access, quota windows, observations, encrypted secrets,
lifecycle adapters, discovery refresh, and substrate-backed routing.
`provider_keys` remains only as a compatibility source while old accounts are
migrated. New accounts do not own one fixed model.

Remaining work is operational: import approved accounts through protected
ingestion, schedule refresh/probes, collect scorecards, finish legacy-key
retirement, and expose the existing management contract clearly in Admin.

## Surfaces

- Atrium: Sonya may report provider status and perform requested management
  actions conversationally.
- Admin: detailed operator view and manual controls.
- Do not turn Atrium into an admin-panel clone.

## VPS Gate

Every substantial provider change requires:

- local migration and focused tests
- isolated adapter probe without exposing secrets
- VPS migration/rollback proof
- VPS provider discovery/health probe
- one routed subagent smoke test before production enablement
