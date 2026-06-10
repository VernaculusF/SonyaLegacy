# Provider Runtime Status

**Status:** Active slice status
**Last updated:** 2026-06-11

## Completed Foundation

- NVIDIA NIM onboarding completed on 2026-06-11: 3 encrypted active accounts,
  121 discovered models, 103 ordinary text-loop offerings, and successful
  account-specific probes for `nvidia/nemotron-3-ultra-550b-a55b`.
- NVIDIA embedding/rerank/guard/safety/retrieval models stay in the catalog as
  future special-worker capacity but are disabled for ordinary text-loop
  subagents.
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
- `provider_models` identity is scoped by `(provider, model_id)`. Raw
  `model_id` stays the upstream API value sent to the provider, so providers
  can expose the same model IDs without overwriting each other.
- Legacy v33 databases are repaired on writable open: old
  `provider_models(model_id PRIMARY KEY)` tables are rebuilt to the composite
  key, and `provider_account_offerings` drops the invalid raw-model FK.
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
- `ensure_critical_schema()` also repairs legacy provider-model primary keys
  to provider scope, so `get_provider_model()` and text-loop checks can reason
  about a concrete provider/model pair.

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
- Google, Nous, CodexSale, Kimchi, and OpenRouter accounts are bootstrapped
  through protected ingestion/import paths; future providers should use the
  same boundary.
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
- OpenRouter availability repair commit `64c1bfc` deployed. Root cause:
  expired legacy key cooldown was reactivated in `provider_keys` but not in the
  mirrored `provider_accounts` row, so the account-scoped availability join
  returned zero models. Production repair synced `1` account and disabled
  `312` stale non-free offerings. Current OpenRouter state: `1` active account,
  `9` disabled legacy accounts, `346` cached models, `34` advertised free
  models, `27` available models, all available free.
- Live OpenRouter refresh on the VPS returned `ok=True`, `models_seen=338`,
  `quotas_seen=0`, and non-free offerings stayed disabled. Focused VPS suite:
  `35 passed`; `sonya` and `sonya-admin` were active with empty error journals.
- OpenRouter probe-backed refresh commits `beab199`, `d5d9163`, and `76bf009`
  deployed. Free candidates now require a successful one-token chat probe per
  account before offering enablement; failed probes write `model_probe`
  observations and disabled offering metadata. Non-text-loop/audio outputs such
  as `google/lyria-3-clip-preview` are no longer treated as free candidates.
  Requested paid/manual offerings are preserved by `metadata.requested=true`.
- Production OpenRouter after probe: `10` active accounts, `338` models seen
  per account, `19` distinct available free models. `qwen/qwen3-coder:free`
  failed probe and is disabled; Lyria preview models are `free=False` and
  unavailable. Account-aware legacy key acquire is deployed, so runtime chooses
  only keys whose mirrored account offers the selected model.
- Google, Nous, and CodexSale protected imports completed from ignored workspace
  files. Refresh results after provider-scoped identity repair: Google `2/2`
  ok, `50` available models; Nous `2/2` ok, `265` available models; CodexSale
  `1/1` ok, `3` available models. The previous Nous/OpenRouter collision bug
  is fixed by the `(provider, model_id)` key.
- Provider-scoped model identity commit `d8c2f3b` deployed. VPS verification:
  provider-focused suite `32 passed`; live schema showed
  `provider_models_pk=[('model_id', 2), ('provider', 1)]`,
  `provider_account_offerings` only references `provider_accounts`, Nous
  refresh returned `265` models per account, and `sonya` / `sonya-admin`
  stayed active with empty error journals.
- `nvidia/llama-nemotron-rerank-vl-1b-v2:free` was requested but is not in the
  current live OpenRouter catalog on the VPS; rerank-related catalog searches
  returned zero rows after refresh.

## Next Slice

The Admin Providers page now presents provider pools, accounts, models, quotas,
observations, protected secret rotation, and manual refresh/probe controls.
The refresh endpoint builds one lifecycle adapter per active account from
substrate-owned provider/account state and resolves encrypted credentials only
at that account adapter boundary.
For OpenRouter, the Admin model pool hides paid cached models by default and
shows free/requested models; searching still scans the full cached catalog so a
specific paid model can be enabled deliberately.

Next provider work is measured model scorecards, cooldown handling, and any
remaining approved provider imports. Authenticated production visual review
remains open because the operator password was not extracted for automation.
