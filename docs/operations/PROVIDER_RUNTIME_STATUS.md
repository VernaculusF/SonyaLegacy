# Provider Runtime Status

**Status:** Active slice status
**Last updated:** 2026-06-10

## Completed Foundation

- substrate v32: providers, provider accounts, account offerings, quota windows,
  and observations.
- substrate v33: encrypted provider secrets and masked account metadata.
- legacy `provider_keys` remain compatible until old inference routing is
  migrated.
- `resolve_account_secret()` is the explicit raw-secret boundary for adapter
  code.
- Provider/model/account selection lives in substrate, not in environment
  variables or process config.
- Legacy `SONYA_LLM_MODEL`, `SONYA_LLM_API_BASE`, and provider-specific
  API-key loading were removed from `AppConfig`; admin chat now uses the same
  substrate-backed `LLMProvider` as the runtime.

## Adapter Contract

- `src/sonya/providers/adapters/` contains the lifecycle adapter contract,
  separate from the older completion `ProviderBackend`.
- `OpenAICompatibleAdapter` supports structured `/models`,
  `/chat/completions`, health checks, and optional quota endpoints.
- `GoogleNativeAdapter` supports Gemini native `models` and
  `generateContent`.
- Adapter tests use mocked HTTP only; no live API key was used.

## Discovery Refresh

- `src/sonya/providers/refresh.py` implements `ProviderRefreshService` over
  the adapter contract.
- `ProviderRefreshCoordinator` runs from the core runtime every ten minutes and
  refreshes active accounts whose last successful discovery is older than
  provider `metadata.refresh_ttl_seconds` (six hours by default).
- Pools without active first-class accounts are skipped quietly until secure
  account import makes them lifecycle-ready.
- Refresh records provider health, model discovery observations, and quota
  windows with `account_id` on the observation.
- Successful discovery upserts `provider_models` and enables offerings for
  the refreshed account only. One working key no longer marks models available
  for every account in the provider pool.
- Discovery failure preserves the last-good cached model pool.
- `providers.list_models` now reads substrate model pools and account
  offerings. It no longer uses Fireworks live catalog calls or hardcoded
  Kiro/OpenRouter/CodexSale model lists.

## Evidence-Driven Subagent Routing

- `pick_subagent_model()` now scores only currently available substrate
  offerings from active provider accounts.
- Hardcoded `_PROFILES` no longer carries routing candidates.
- `_PURPOSE_MODEL_HINT` is empty; purpose names no longer force Fireworks or
  any fixed model.
- `LLMProvider` fallback provider order is derived from available offerings and
  eligible keys, not from a fixed provider list.
- `SubagentTool` checks `text_loop_ok` through substrate when possible, so
  special-worker models stay out of text-loop subagents.
- `ensure_critical_schema()` repairs legacy v33 `provider_models` tables that
  missed `text_loop_ok`, `last_checked_at`, `discovery_source`, or
  `metadata_json`.

## Management Surfaces

- `ProvidersTool` can create/update/delete providers, create/update/delete
  accounts, enable/disable account offerings, list provider pools, and inspect
  provider quota/health observations.
- New account secrets go through the encrypted provider secret boundary; tool
  and admin responses return only references/masks.
- `/api/providers` now returns provider registry, accounts, model pool,
  available models, quota windows, observations, and legacy keys.
- Admin POST endpoints exist for provider registry, provider accounts, and
  account offerings.
- Atrium only classifies `provider.*` events as system/status stream entries;
  detailed CRUD controls remain in Admin.

## Protected Secret Ingestion

- Provider/account metadata is created separately from credential material.
- Authenticated Admin
  `PUT /api/providers/accounts/{account_id}/secret` accepts an opaque
  `application/octet-stream` body and immediately encrypts/rotates it.
- Rotation deactivates previous account secrets; adapter resolution returns
  only the latest active secret.
- Responses, account reads, and audit entries contain only a secret reference
  and mask.
- Ordinary account JSON/tool actions and legacy key-add JSON/tool actions
  reject plaintext credentials.
- Nous and other newly supplied accounts have not been bootstrapped yet.
- Production OpenRouter main account is now bootstrapped through a
  `provider-secret` reference; its legacy plaintext value was cleared.
- `sonya.tools.import_provider_accounts` imports ignored local key files into
  encrypted provider accounts. It prints only counts and masks; raw keys are
  read from file/stdin and never from argv.

## Latest Verification

- local focused provider/routing/management/secret-ingestion suite:
  `126 passed`
- local compile smoke: `python -m compileall src\sonya\admin\server.py src\sonya\providers src\sonya\tools\providers_tool.py`
- local Atrium build: `npm run build` in `packages/atrium` passed
- local repository secret-prefix scan: no pasted credential prefixes found
- local substrate-owned provider-binding slice: `65 passed`; runtime grep
  confirms no `SONYA_LLM_*`, provider-specific API-key env loading, or
  `load_provider_secret`.
- local routing/default grep: no Fireworks DeepSeek or fixed fallback references
  remain in the routing/default files.
- VPS isolated focused provider/routing/management suite: `113 passed`
- VPS isolated substrate-owned provider-binding slice: `65 passed`; runtime
  grep confirms no env model/provider binding.
- VPS isolated provider/routing/management/secret-ingestion suite:
  `122 passed`.
- VPS live-substrate-copy protected-ingestion smoke passed
  (`schema_version=33`, old secret `inactive`, new secret `active`, plaintext
  absent from SQLite dump).
- VPS real-substrate backup migration/import smoke: passed
  (`schema_version=33`, `4 providers`, `10 accounts`, `10 keys`,
  `10 masked_accounts`, `17 models`; live-copy active provider still comes from
  production substrate settings and was not changed)
- production VPS provider runtime deployed with rollback backup at
  `/home/jester-sonya/backups/sonya-provider-20260610-050736`
- production substrate migrated to schema v33
- production OpenRouter discovery: `339` models observed, `27` free after
  nested pricing normalization
- production live adapter and `LLMProvider` inference succeeded with
  `google/gemma-4-31b-it:free`
- `sonya` and `sonya-admin` services are active; core reports
  `thinking_provider_ready` for the OpenRouter pool
- production-source provider verification: `126 passed` (`119` regular plus
  `7` async tests rerun with explicit `asyncio_mode=auto`)
- periodic refresh commits `11dbc04` and `37e8e72` deployed; focused
  production-source suite passed (`18 passed`), both services active, and the
  corrected first cycle emitted no false failures for pools without active
  accounts
- account-scoped refresh commit `9066eed` deployed; production-source provider
  suite passed (`68 passed`), both services active, and journal error scan was
  empty
- safe importer commit `2fe185a` deployed; production-source importer/provider
  suite passed (`72 passed`) and journal error scan was empty
- Kimchi was imported from the ignored workspace key file on the VPS:
  `15` encrypted active accounts, `0` full plaintext leaks in SQLite dump,
  account-scoped refresh `15/15` ok, `8` cached/available models, `0` failed

## Next Slice

The Admin Providers page now presents provider pools, accounts, models, quotas,
observations, protected secret rotation, and manual refresh/probe controls.
The refresh endpoint builds one lifecycle adapter per active account from
substrate-owned provider/account state and resolves encrypted credentials only
at that account adapter boundary.

Bootstrap Nous, Google, AgentRouter, CodexSale, and remaining approved
providers through protected secret ingestion/import files, confirm periodic
lifecycle observations, then add measured model scorecards and cooldown
handling. Authenticated production visual review remains open because the
operator password was not extracted for automation.
