# OMNIAGENT ANALYSIS

**Status:** Active (reference, leave as-is)
**Type:** Reference Analysis
**Scope:** OmniAgent as vocabulary donor, warning source, and rejected direct runtime base
**Depends on:** [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
**Used by:** [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), future runtime decisions
**Last reviewed:** 2026-05-16

> **Reality note (2026-05-16):** External-codebase analysis — findings stable. Note that current Sonya uses Telethon-based `tg_userbot` (MTProto, not bot API), which pulls Sonya further from OmniAgent's `python-telegram-bot` adapter pattern.


## 1. Что такое OmniAgent для проекта

OmniAgent - это сторонний framework с сильным marketing surface:

- OmniEvolve;
- Hyper-Harness;
- Deep Reflexion;
- proactive memory;
- realtime skill evolution;
- context evolution;
- brainmodel evolution.

Для проекта Сони это важно не потому, что OmniAgent является хорошей базой, а потому что он:

- использует близкий vocabulary;
- пытается закрыть похожие классы задач;
- показывает, где красивые claims расходятся с реальной кодовой базой.

## 2. Что в OmniAgent полезного

### 2.1 Vocabulary and module taxonomy

OmniAgent полезен как словарь модулей:

- evolution layers;
- harness;
- reflexion;
- multi-agent supervision;
- context/memory framing.

### 2.2 Security as multi-layer concern

Даже если реализация там сырая, сама идея того, что safety не сводится к одному флагу, правильная.

### 2.3 Attempt at explicit orchestration

В отличие от простых agent wrappers, OmniAgent хотя бы пытается мыслить:

- planning agents;
- safety agents;
- tool execution control;
- context layering.

Это полезно как reference direction.

## 3. Что в OmniAgent плохое как в базе

### 3.1 README inflation

README обещает больше, чем кодовая база надёжно подтверждает.

Это плохо для проекта Сони, потому что здесь нельзя строить ядро на wishful marketing.

### 3.2 Security trust gap

По прошлому аудиту было видно, что gateway/auth surface and approval logic не тянут уровень доверия, который нужен для Sonya core.

### 3.3 Channel claims vs runtime truth

Заявленные channels не равны гарантированно рабочим and hardened channels.

### 3.4 Alpha-codebase risk

OmniAgent выглядит как сырая база с хорошими амбициями, а не как надёжный фундамент.

## 4. Что берём из OmniAgent

- naming and module decomposition hints;
- ambition to separate evolution dimensions;
- idea that harness and reflexion are first-class;
- warning that these concepts are easy to overclaim and underbuild.

## 5. Что не берём

- кодовую базу как foundation;
- security claims on trust;
- README promises as architecture truth;
- assumption that "channel exists in README" means "channel is production-ready".

## 6. Роль OmniAgent в Sonya project

OmniAgent должен играть роль:

- concept reference;
- anti-pattern source;
- vocabulary donor.

Но не роль:

- runtime foundation;
- trusted secure shell;
- direct base for Sonya MVP.

## 7. Итоговый вывод

OmniAgent полезен как проект, с которым стоит спорить и из которого стоит вытаскивать язык и идеи.

Но строить Соню поверх него как поверх готового базиса было бы ошибкой.

Соня должна не "пересесть на OmniAgent", а использовать отдельные идеи OmniAgent inside a cleaner architecture with stricter identity, memory, harness and principal logic.


## 8. Appendix: Code-Level Audit (2026-05-13)

This section records observations from actually reading the OmniAgent codebase at `C:\Users\Jester\.openclaw\_tmp_omniagent\`, not just the README claims.

### 8.1 Package Layout

Top-level package `omniagent/` splits into: `agents/`, `channels/`, `cli/`, `config/`, `extensions/`, `gateway/`, `infra/`, `rl/`, `security/`, `tools/`. This is real Python code with real imports, not vaporware.

File sizes that matter:

- `agents/reflexion.py` — 89 KB.
- `agents/skill_evolution.py` — 53 KB.
- `agents/context_evolution.py` — 28 KB.
- `agents/memory_manager.py` — 20 KB.
- `agents/sentinel.py` — 23 KB.
- `agents/guardian.py` — 22 KB.
- `agents/llm.py` — 43 KB (multiple provider implementations).
- `rl/api_server.py` — 39 KB (FastAPI proxy for SGLang/vLLM RL pipeline).
- `gateway/webui.py` — 56 KB.

That is: the codebase is **much more real** than a README-only project. Previous version of this analysis understated that. The correct stance is still rejection as runtime base, but for more specific reasons recorded below, not for “README inflation” alone.

### 8.2 Agents Layer — Real Shape

`agents/__init__.py` exports a concrete shell:

- `Agent` abstract class and `AgentResult` dataclass in `agent.py`.
- `ReflexionAgent(Agent)` in `reflexion.py` as the main implementation.
- `LLMProvider` plus adapters: `DeepSeekLLMProvider`, `OpenAILLMProvider`, `AnthropicLLMProvider`, `OllamaLLMProvider`, `GoogleGeminiLLMProvider`, `OpenRouterLLMProvider`, `LocalInferenceLLMProvider`, with a `create_llm_provider` factory.
- `ContextManager`, `ContextEvolutionManager`, `ContextAssembler` split context work into assembly vs evolution vs run-time management.
- `MemorySearchManager` plus `MemorySearchTool` and `MemoryGetTool`. Memory is wired as a tool, not as a hidden cache.
- `SkillManager` + `SkillEvolutionManager`. Skill evolution is a real pipeline: `ExecutionPattern` (JSONL records with tool signatures, success flag, iterations, active skills), `SkillPatch` (Markdown patch with timestamp + context), `CompiledSkill` (prompt or script with confidence).
- `SentinelAgent` — planning / milestone decomposition + persistence to `.omniagent/sentinel/`.
- `GuardianAgent` — pre-execution review with a concrete regex list of “high-risk bash patterns” and a `ReviewResult` model labeling risk level.
- `EventBus`, `EventType`, `AgentEvent`, `AgentState`, `AbortController`, `AbortError`, `ToolHookManager`, `ToolCallContext`, `ToolHookResult` — runtime plumbing as first-class modules.

So the “OmniEvolve” vocabulary is backed by actual classes with dataclasses, event buses, approval flows, and file-on-disk artifacts. That deserves more credit than the previous version of this file gave it, but the same deserves more nuance on what to reject.

### 8.3 Tools Layer

`tools/__init__.py` exposes `Tool`, `ToolRegistry`, and concrete tools:

- `ReadTool`, `WriteTool`, `EditTool` (file I/O).
- `BashTool`.
- `LoadJSONTool`, `SaveJSONTool`.
- `ProcessListTool`, `ProcessKillTool`.
- `WebSearchTool`, `WebFetchTool`.
- `GrepTool`, `FindTool`, `LsTool`, `DiffTool`, `HttpTool`.

This is a real, local-execution agentic toolbox. It is exactly the class of capability that Sonya’s harness layer will have to be strict about.

### 8.4 Security Layer

`security/` is larger than a token-gate; it is a small policy subsystem:

- `policy.py` defines `PolicyDecision (ALLOW | DENY | REQUIRE_APPROVAL)`, `ToolProfile (MINIMAL | CODING | FULL)`, `TOOL_GROUPS`, `PROFILE_CONFIGS`, and `PolicyRule` with priorities.
- `approval.py` defines `ApprovalStatus`, `ApprovalRequest` with id/action/description/risk_level, persistence dict, and an `ApprovalManager` used from the agent.
- `audit.py` defines `AuditEvent` + `AuditLogger` writing to a directory of log files.
- Tests in `__pycache__` confirm these are used, not dead.

Takeaway for Sonya’s harness: three distinct concepts — `policy → decision`, `approval flow → user confirmation`, `audit log → trace` — are worth keeping as three separate objects. That matches the three harness layers we already require (technical, epistemic, anchor).

However, important weakness: the “four-layer dynamic security scanning / unbypassable” claim in the README corresponds in code to a single `ToolPolicy` + `ApprovalManager` pair plus Guardian regex checks. It is meaningful, but “unbypassable” is overclaim. An agent with bash access and no outer sandbox can still escape.

### 8.5 Config Layer

`config/loader.py` and `config/models.py` define pydantic config with `OmniAgentConfig`, `AgentConfig`, `ToolsConfig`, `ProviderConfig`. Provider selection is an `enum` literal: `deepseek | openai | anthropic | ollama | gemini | openrouter | vllm | sglang | custom`. Tool profile is also an enum literal.

Gateway API has a concrete `_mask_sensitive_fields` that masks `api_key`, `openai_api_key`, `anthropic_api_key`, and per-provider `api_key`. That is a real convention worth noting.

But the underlying storage is `~/.omniagent/config.yaml` with raw `api_key` values in plaintext. The API masks only on output, not in the file. Same anti-pattern as OpenClaw: secrets co-located with behavior knobs. Reject as final design for Sonya.

### 8.6 Gateway and Channels

`gateway/server.py` + `gateway/api.py` + `gateway/session.py` + `gateway/router.py` + `gateway/webui.py`:

- A real aiohttp WebSocket + HTTP server with `/ws`, `/health`, `/message` endpoints.
- `SessionManager` persisting sessions to `~/.omniagent/sessions`.
- `MessageRouter` with `IncomingMessage` / `OutgoingMessage` dataclasses and two modes (direct and bus-backed).
- `webui.py` is a 56 KB single-file web UI — a static surface bundled with the gateway.

`channels/`:

- `base.py`, `bus.py` define `BaseChannel`, `OutboundMessage`.
- `telegram.py` uses `python-telegram-bot` (`telegram.Application`) — **different** library than the live OpenClaw bridge (`telegram-bridge.mjs` uses raw `fetch` against `api.telegram.org/bot{token}/...`). If we ever pretended “OmniAgent Telegram is the same as OpenClaw Telegram”, that was wrong. They are two different stacks with different availability assumptions.
- `discord.py`, `feishu.py`, `mail.py`, `webhook.py`, `redirects.py` — concrete adapters. Not just README.
- `telegram.py` specifically lazy-imports the library and logs a warning if not installed. So the “multi-channel” claim is real, but channel presence depends on optional deps.

Takeaway: OmniAgent’s gateway + session + channel design is usable as a **structural reference** for how Sonya should eventually separate session store, router, and channel adapters. It should not be embedded directly.

### 8.7 RL Pipeline

`rl/__init__.py` documents an RL pipeline (GRPO + PRM) that proxies logprobs between agents and `sglang`/`vllm`. The module docstring is explicit: **“Only activates when model_provider is ‘vllm’ or ‘sglang’. When using remote LLM providers (DeepSeek, OpenAI, etc.), RL is completely disabled and zero overhead.”**

That is important. The BrainModel-self-evolution claim in the README is concrete only when you host your own model backend. It does not work over OpenRouter/Anthropic/OpenAI. For Sonya, this means:

- We can borrow the idea of an RL proxy between an agent and a local inference engine as a **future BrainModel evolution adapter**.
- We cannot pretend Sonya will get self-evolving brains by pointing at OpenRouter.
- Any future Sonya RL track must be explicitly gated on local inference.

### 8.8 Channels vs Live OpenClaw — Concrete Divergence

OmniAgent’s `channels/telegram.py` uses `python-telegram-bot`. OpenClaw’s real production bridge is a raw Node.js client. These are not interchangeable. If Sonya ever decides to reuse OmniAgent’s Telegram adapter, it becomes a **replacement**, not a drop-in — session storage, allowlist format, media handling, and the post-response-hook contract would all need to be rewritten.

### 8.9 Concrete Items We Take From OmniAgent (code-informed)

Beyond vocabulary, these are real, specific, inspectable reference ideas:

- Explicit `Agent` abstract class with `handle_message` and `execute` separation. Sonya should expose a similar split.
- Structured `IncomingMessage` / `OutgoingMessage` as the unit between channels and the agent.
- `EventBus` + `EventType` as first-class plumbing between agent, memory, skill evolution, context evolution, guardian, and sentinel.
- Dataclasses for all persisted artifacts: `ExecutionPattern`, `SkillPatch`, `CompiledSkill`, `ApprovalRequest`, `AuditEvent`, `Milestone`, `TaskPlan`, `Lesson`. Persisting artifacts as JSONL / Markdown with schemas is a strong habit.
- Three-part security split: policy decision, approval, audit.
- Provider factory (`create_llm_provider`) with an explicit enum of supported backends.
- `ToolProfile` enum with named presets (MINIMAL / CODING / FULL) that map to allowed tools and approval requirements. That pattern is better than free-text `security: full`.
- Guardian’s regex list of high-risk bash commands as a starting seed for Sonya’s harness anti-patterns.
- Sentinel’s explicit multi-step keyword detection + milestone tracking — useful when Sonya adds planner/task decomposition.
- RL-proxy architecture as the right shape for a future self-hosted BrainModel evolution slot.

### 8.10 Concrete Items We Reject (code-informed)

- **License.** OmniAgent is GPL-3.0. The README states: “Any code that references this project must also be open-sourced under the same license.” Importing any OmniAgent code directly contaminates Sonya’s licensing posture. Sonya must not copy files from OmniAgent. We can reimplement ideas, reference schemas, and document differences.
- **Plaintext secrets in `config.yaml`.** Same anti-pattern as OpenClaw. Sonya must separate.
- **“Unbypassable” security framing.** The code is a real policy + approval + audit triple, but the marketing word is overclaim. Sonya must not inherit the framing.
- **`gateway/webui.py` as a 56 KB single file.** Functional, but not a maintainable pattern. Sonya should not mimic that shape.
- **`python-telegram-bot` as the Telegram adapter.** We already have a tested OpenRouter-free Python bridge based on raw HTTP (`tg-bridge`). Switching frameworks would be a regression in parity.
- **“BrainModel self-evolution” as if it were generic.** In code, it is an SGLang/vLLM-only RL proxy. Sonya must label this correctly when we eventually introduce a similar layer.
- **Single-file 89 KB `reflexion.py` with the entire agent loop inside.** We should not follow that pattern; Sonya already decomposes runtime into small modules (`actions`, `tasks`, `continuity`), and must keep doing so.
- **Static `ToolProfile` presets as the only access control.** Good as a baseline; cannot be the final answer. Sonya’s harness must combine a tool profile with principal scope + anchor integrity checks, not with tool profile alone.

### 8.11 Licensing And Contagion Rule

Because OmniAgent is GPL-3.0, this reference analysis is allowed, but:

- No source file may be copy-pasted into Sonya.
- Schemas and interface shapes may be reimplemented from scratch with credit in this document.
- Any borrowed idea must be attributed here, not silently inlined into a Sonya module.
- If at some point we decide to take more than surface-level inspiration, we must first review the license implications with the owner.

### 8.12 Honest Caveat

OmniAgent status is `Development Status :: 3 - Alpha`. The architecture is real and richer than we previously credited. The claims that go beyond “alpha-real” are still overclaims, mostly around “unbypassable” security and “full BrainModel self-evolution”. Treat as a serious reference, not as a foundation.
