# Provider and Model Catalog

**Status:** Active reference catalog
**Last updated:** 2026-06-10
**Runtime truth:** substrate discovery and observations

This file records known providers, candidate models, and operational notes. It
contains no credentials. Claims from Ivan are marked `user_observed`; provider
documentation is `advertised`; neither is benchmark truth.

## Provider Inventory

| Provider | Adapter | Status | Accounts | Discovery / notes |
|---|---|---:|---:|---|
| OpenRouter | OpenAI-compatible | production active | main encrypted account + legacy disabled pool | Live `/api/v1/models`; offerings change frequently |
| Nous Research | OpenAI-compatible | bootstrap priority | credential available | Base `https://inference-api.nousresearch.com/v1`; user reports 50 RPM / 500k TPM |
| Google AI Studio | Google native | bootstrap priority | project credential available | Native model discovery; quota is per project/model and dynamic |
| kimchi.dev | OpenAI-compatible | production imported fallback | 15 encrypted accounts | Base `https://llm.kimchi.dev/openai/v1`; account budgets must be observed |
| agentrouter.org | Anthropic/bridge candidate | experimental | test credential available | Official docs show Claude Code/Anthropic setup; latency and content constraints reported |
| FreeQwenApi | browser bridge with local OpenAI API | experimental | browser sessions | Local endpoint `http://localhost:3264/api`; must prove on VPS |
| NVIDIA NIM | official OpenAI-compatible API | onboarding | 3 operator-supplied keys | Free model pool; preferred carrier candidate `nvidia/nemotron-3-ultra-550b-a55b` |
| freemodel.dev | CLI bridge candidate | research | account available | Transport/model/quota contract must be verified |
| codex.sale | OpenAI-compatible/special modes | premium last resort | credential available | Paid; use only after budget/risk decision |
| Fireworks | OpenAI-compatible | unavailable | all known accounts banned | Remove from defaults and routing assumptions |

## Bootstrap Candidate Offerings

These are initial candidates, not a permanent routing table.

| Provider | Model / group | Initial note | Evidence |
|---|---|---|---|
| Nous | `nvidia/nemotron-3-ultra:free` | 1M-context carrier candidate; coding weakness reported | user_observed |
| OpenRouter | `openrouter/owl-alpha` | capable but very slow | user_observed |
| OpenRouter | `google/gemma-4-31b-it:free` | main-account free candidate | user_observed |
| OpenRouter | `z-ai/glm-4.5-air:free` | coding candidate | user_observed |
| OpenRouter | `moonshotai/kimi-k2.6:free` | coding/agentic candidate | user_observed |
| OpenRouter | free catalog group | Laguna, GPT-OSS, Nemotron, Gemma, Kimi, Qwen, Llama, Riverflow, Hermes, Liquid candidates | user_observed; live IDs required |
| Google | Gemma 4 26B / 31B; available Gemini text models | account-visible candidates; exact API IDs and quotas require discovery | user_observed |
| kimchi.dev | `kimi-k2.6`, `kimi-k2.5`, `minimax-m2.7`, `minimax-m2.5`, `nemotron-3-super-fp4` | low-cost fallback pool | advertised/user_observed |
| agentrouter | `glm-5.1`, possible Claude offerings | GLM reportedly usable; provider latency/constraints require probes | user_observed |
| FreeQwenApi | `qwen3.7-max`, `qwen3.7-plus`, `qwen3.6-plus` | browser-backed coding/multimodal experiment | local catalog |
| codex.sale | `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.5` | paid critical-path text pool | user_observed |
| codex.sale | `gpt-image-2`, `gpt-4o-transcribe` | special non-text workers, not normal text subagents | user_observed |

OpenRouter candidates supplied on 2026-06-10 also include Laguna M.1/XS.2,
GPT-OSS 120B/20B, Nemotron Nano variants, Gemma 4 26B, Qwen3 Next 80B,
Llama 3.3 70B, Riverflow 2.5, Hermes 3 405B, and others. Exact IDs,
availability, context, and free status must come from live discovery.

## Capability Category Rules

Catalog rows must keep model category separate from provider/account identity:

- text/code/planner/reviewer models are eligible for `text_loop` only when
  live probes prove normal chat completion works;
- vision models are eligible for `vision_input` when they accept image/video
  inputs and return text descriptions;
- free embedding models are `embedding` workers, not chat models;
- rerank/retrieval models are `rerank` workers, not chat models;
- image generators are `image_generation` workers with artifact output;
- transcription/TTS models are audio workers with audio-specific quotas;
- safety/guard models are policy workers.

OpenRouter, Google, NVIDIA, CodexSale, and browser bridges can expose multiple
categories under one provider account. Admin and Sonya-facing management should
therefore display provider -> accounts -> offerings grouped by capability
category, with `text_loop_ok` only applying to the ordinary dialog/subagent
loop.

## Dynamic Limit Notes

- Google states that RPM, TPM, and RPD vary by model/tier and are applied per
  project, not per API key.
- OpenRouter catalog metadata and endpoint availability must be refreshed.
- freemodel rolling windows, kimchi balances, and multi-account access are
  account observations with reset timestamps.
- Nominal aggregate credits are not usable balance until each account passes
  health, access, and policy checks.

## Measured Production Observations 2026-06-11

- Kimchi was imported from an ignored workspace key file into encrypted
  provider accounts: 15 active accounts.
- Kimchi account-scoped discovery/health refresh succeeded for 15/15 accounts.
- Kimchi currently exposes 8 cached/available model offerings in substrate.
- Full raw Kimchi secret values were checked against the SQLite dump after
  import; leak count was 0. Stored masks still intentionally include short
  prefixes/suffixes.

## Measured Production Observations 2026-06-10

- OpenRouter `/models` discovery succeeded on the VPS and returned `339`
  offerings.
- Nested OpenRouter pricing normalized into per-million costs; `27` discovered
  offerings were observed as free.
- `google/gemma-4-31b-it:free` returned a non-empty live response and is the
  current substrate default/fallback plus executor preference.
- Main OpenRouter account was migrated from legacy plaintext storage to an
  encrypted `provider-secret` reference; its legacy `provider_keys.api_key`
  value is empty.
- Live `LLMProvider` inference succeeded after plaintext removal, proving the
  main runtime resolves the encrypted account secret.
- Nous remains unbootstrapped. Its credential must enter through the protected
  ingestion endpoint, not through shell/tool traces.

## Provider Constraints

Constraints are factual routing inputs, not prompt insults or hard bans:

- `slow`
- `high_refusal_or_content_filter_risk`
- `browser_session_required`
- `cli_bridge_required`
- `paid_last_resort`
- `account_specific_model_access`
- `unavailable`

## Secure Bootstrap Order

After the runtime migration:

1. Nous + one OpenRouter account for minimum viable text routing.
2. Google AI Studio with native adapter.
3. Google AI Studio with native adapter.
4. FreeQwenApi VPS experiment.
5. freemodel and agentrouter bridge research/import.
6. codex.sale only as explicit premium fallback.

Do not load every credential before account/offering/quota modeling exists.

## Official References Checked 2026-06-10

- OpenRouter models API:
  `https://openrouter.ai/docs/api/api-reference/models/get-models`
- OpenRouter endpoint discovery:
  `https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints`
- Google Gemini models:
  `https://ai.google.dev/gemini-api/docs/models`
- Google Gemini rate limits:
  `https://ai.google.dev/gemini-api/docs/rate-limits`
- Nous inference API:
  `https://portal.nousresearch.com/api-docs`
- AgentRouter Claude Code setup:
  `https://docs.agentrouter.org/en/start.html`
- Kimchi model API overview:
  `https://docs.kimchi.dev/docs/model-apis-overview`
- freemodel dashboard docs:
  `https://freemodel.dev/dashboard/docs`
