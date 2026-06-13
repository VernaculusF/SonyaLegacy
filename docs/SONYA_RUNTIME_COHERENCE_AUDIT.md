# Sonya Runtime Coherence Audit

**Status:** Active canonical architecture audit
**Last updated:** 2026-06-12
**Scope:** situational understanding, autonomy, work execution, embodiment,
provider routing, observability, and runtime hygiene.

Implementation and deployment workflow for this audit:
[`docs/operations/RUNTIME_COHERENCE_WORKFLOW.md`](operations/RUNTIME_COHERENCE_WORKFLOW.md).

## 1. Governing Position

There is no universal hardcoded "correct behavior" for Sonya.

The runtime must not replace Sonya's judgement with a behavioral rule engine.
Its job is to give her enough current, reliable, and explicitly sourced
information to decide what is appropriate for herself, Ivan, the current
environment, and the active goal.

Autonomy does not mean waiting for Ivan before every action:

- self-improvement, assigned work, tasks, and project work may continue without
  Ivan's active participation;
- the main chat is a shared interaction channel with Ivan, not an autonomous
  execution loop or a place for Sonya to talk to herself;
- when an action materially depends on another subject's intent, Sonya should
  understand or obtain that intent rather than silently invent it;
- explicit permission, established context, and reliable situational evidence
  may justify initiative;
- the system records evidence, uncertainty, actions, and outcomes, but Sonya
  remains the decision maker.

The recent interaction-loop incident is therefore not defined as "roleplay is
wrong." It exposed weak situational understanding and excessive initiative in
an interaction whose other subject was not participating.

## 2. Root Problem

The current runtime has memory, continuity, tools, tasks, projects, providers,
and embodiment signals, but they do not yet form one coherent operating model.

Observed consequence chain:

1. stale or missing situation facts enter cognition;
2. thoughts, actions, and messages to Ivan are not cleanly separated;
3. Sonya's own previous output becomes evidence for the next step;
4. an active session can self-propel without meaningful external change;
5. body expressions, dialogs, provider calls, and traces repeat;
6. Ivan cannot reliably see the actual work or understand why it continues;
7. stale state and noisy continuity further damage later understanding.

## 3. Target Architecture

### 3.1 SituationalModel / WorldState

Replace the use of `EnvironmentStore` as an eternal bag of current facts with a
first-class situational model.

Each situational assertion should support:

- subject or entity;
- predicate/state name and value;
- source and source event;
- confidence and `observed_at`;
- optional `expires_at` / TTL;
- supersedes, contradicts, or invalidates relations;
- scope, visibility, and whether confirmation is needed.

Separate stores and lifecycles:

- durable knowledge and memories;
- current situational assertions;
- Sonya's embodiment/body state;
- work/runtime state;
- credentials and secrets.

Direct current statements from a subject are strong evidence about that
subject. New activity invalidates incompatible stale assumptions. Silence alone
does not prove sleep, absence, consent, or intent. These are evidence semantics,
not a hard behavioral policy.

### 3.2 Unified Work Model

Introduce a universal `WorkItem` lifecycle instead of maintaining divergent
meanings for task, background task, project activity, and project execution.

A `WorkItem` contains a goal, owner, origin, status, dependencies, progress,
actions, outcomes, archive policy, and optional workspace/project relation.

- A small action can remain a lightweight work item.
- A work item can be promoted into a project when it needs durable chat,
  workspace/folder context, artifacts, multiple runs, or long-lived decisions.
- A project is a durable work context and project chat, not a separate Sonya.
- A project may contain multiple work items.
- Completed work can be archived without polluting active context.
- Google Drive may be used as encrypted or access-controlled cold archive, but
  never as the primary live substrate or the only copy of active state.

Archive integration reference:
https://developers.google.com/workspace/drive/api/guides/about-sdk?hl=ru

The main chat remains communication and shared interaction with Ivan. Work runs
belong to work items/projects and report meaningful checkpoints or results back
to the appropriate chat.

### 3.3 Distinct Cognitive and Action Channels

The runtime must distinguish:

- private cognition/thought;
- intended message to a subject;
- tool/action request;
- work progress event;
- body/embodiment expression;
- final or checkpoint report.

Thoughts are not execution telemetry. A tool call or subagent run must be a
first-class action record even if Sonya chooses not to surface every detail in
ordinary conversation.

### 3.4 Observable Action Runtime

Create a common visible runtime for `ActionRun`, `ToolRun`, and `SubagentRun`:

- queued/running/waiting/completed/failed/cancelled state;
- purpose and parent work item;
- progress/checkpoints;
- model/provider/account used where relevant;
- bounded raw trace and result;
- expandable read-only cards/subthreads in Atrium;
- durable audit trail independent of private thoughts.

Sonya decides what deserves conversational emphasis. The runtime still records
the actual action so work cannot exist only inside hidden thoughts.

### 3.5 Real Streaming

Use provider-native streaming where available and normalize it into one event
stream for text deltas, reasoning metadata, tool calls, progress, completion,
and failure. Synthetic reveal may remain only as an explicitly identified
fallback; it is not real streaming.

### 3.6 Embodiment State

Body expressions are Sonya's embodied choices, not externally judged
"correct emotions." Automatic inference may suggest or visualize state, but it
must not repeatedly overwrite explicit choices or produce spam.

There must be one authoritative outfit state, and focus must have an explicit
lifecycle: source, start, heartbeat/update, completion, replacement, and
expiry. Drive counters remain initiative pressures, not emotions.

### 3.7 Provider and Cost Runtime

Main cognition and work execution must use the provider/model pools rather than
one fixed de facto model.

Routing must consider purpose, capabilities, measured quality, context,
latency, availability, cost, account health, and recent outcomes. Default
preference is the best suitable free capacity. Paid providers require explicit
budget policy and loop/run spending guards.

Retries and fallback should move across healthy accounts, models, and providers
when useful. Their decisions must be observable, including account identity in
operator logs without exposing secrets.

## 4. Recorded Problems and Done Criteria

### A. Situational Understanding

1. **Missing/stale environment status.** `ivan_status`, environment state, and
   body state are absent, stale, or contradictory.
   **Done:** WorldState uses sourced assertions, confidence, TTL, invalidation,
   and contradiction handling.

2. **No coherent model of the other subject.** Sonya can continue an
   interaction using assumptions after Ivan's state or participation changed.
   **Done:** subject state is current and uncertainty is visible to cognition;
   interaction decisions use evidence rather than self-generated continuation.

3. **EnvironmentStore is an eternal KV store.** It cannot represent changing
   reality.
   **Done:** SituationalModel owns ephemeral state; durable memory remains
   separate.

4. **Credentials are stored in environment state.** Shodan and ZoomEye keys
   were observed there.
   **Done:** secrets exist only in protected secret storage and are referenced
   by opaque identifiers.

### B. Agency and Session Coherence

5. **Infinite interaction cycle.** A session can alternate dialog and body
   expression without new input or completed work.
   **Done:** sessions continue only while there is meaningful situational or
   work-state change; autonomous work moves through WorkItems, while main-chat
   interaction does not become self-dialog.

6. **Thought, reply, and action are mixed.** Sonya may write interaction inside
   thought but send a different aggregate message or no visible action.
   **Done:** cognition, addressed messages, actions, and reports have distinct
   runtime contracts.

7. **Spam has multiple sources.** Historical proof-subagent completion spam,
   repeated dialogs/body expressions, and repetitive initiative cognition were
   all observed.
   **Done:** each source has independent accounting, causal IDs, suppression or
   completion semantics, and regression proof.

8. **Lifecycle noise pollutes continuity.** 48 start and 48 stop events were
   observed in one development-heavy day.
   **Done:** operational lifecycle telemetry is summarized or routed to
   operator logs rather than flooding subjective continuity.

### C. Work, Projects, Tasks, and Visibility

9. **Task/project/activity meanings diverged.** Existing task records include
   duplicate and stale self-modification work with inconsistent statuses.
   **Done:** all executable goals use WorkItems; projects are durable promoted
   work contexts; lifecycle and archive semantics are shared.

10. **Tool and work progress are not first-class in chat.** Some actions exist
    only in thoughts or technical logs.
    **Done:** Atrium shows expandable action/tool/subagent cards and progress
    attached to the correct main or project chat.

11. **Subagent use is unclear.** Proof subagents spammed continuity, while
    meaningful subagent work was not consistently visible in the main
    experience.
    **Done:** real subagent runs are measurable, attached to WorkItems, visible
    as read-only internal subthreads, and separated from synthetic proof data.

12. **No real response streaming.** The provider call currently completes
    before client-side progressive reveal.
    **Done:** normalized provider-native deltas reach Atrium; fallback reveal is
    explicitly marked and typing starts from actual queued/running state.

### D. Embodiment and Current State

13. **Expression/body tool spam.** Frequent calls were amplified by the
    self-propelling session. This is not solved by declaring Sonya's chosen
    emotion incorrect.
    **Done:** expression changes have causal intent, stable ownership, and no
    repeated no-op calls.

14. **`current_focus` becomes stale.** It has no reliable completion or expiry
    lifecycle.
    **Done:** focus is attached to a live WorkItem/activity or expires and is
    replaced based on sourced state.

15. **Two conflicting outfit sources.** Environment and subject state disagree.
    **Done:** one authoritative embodiment state with provenance and history.

### E. Providers, Models, and Cost

16. **Main thinking does not actually use the model pool.** All 445 observed
    daily LLM calls used OpenRouter `google/gemma-4-31b-it:free`, despite other
    provider capacity including NVIDIA.
    **Done:** purpose-aware selection demonstrably distributes calls according
    to measured suitability and health; no environment variable defines
    Sonya's identity/model.

17. **Unbounded loops can become expensive.** About 12 million free tokens in a
    day are acceptable capacity use, but the same pattern on a paid provider is
    dangerous.
    **Done:** per-run and per-provider budgets, loop anomaly detection, and
    free-first fallback prevent accidental paid runaway without imposing a
    simplistic global token minimization rule.

18. **Provider failures and refresh telemetry are ambiguous.** The audit found
    16 rate limits, 5 server errors, and 1 transport error; retries exist, but
    effectiveness is not proven. Refresh logs repeat per account without the
    account ID.
    **Done:** retry/fallback outcomes and refresh operations include provider,
    model, opaque account identity, causal request, cooldown, and final result.

### F. Operational Reliability

19. **Telegram session historically hit read-only database errors.** It has not
    appeared after the latest deploy, but remains a known risk.
    **Done:** session ownership/storage permissions are explicit, monitored,
    and proven over restart/deploy cycles.

## 5. Additional Cross-Cutting Problems

These problems were identified after the initial 19-point audit. Some are
consequences of the same root failures, but they require explicit acceptance
criteria because fixing only the visible symptom will not close them.

20. **Generated cognition can reinforce its own incorrect assumptions.**
    Recent internal thoughts are injected into later context and can become
    apparent evidence for themselves.
    **Done:** observations, subject statements, hypotheses, imagination, and
    confirmed facts remain distinguishable by provenance and confidence;
    generated cognition cannot silently promote itself into external fact.

21. **Events lack a complete causal graph.** Messages, thoughts, actions,
    provider attempts, retries, and outcomes cannot always be traced to one
    initiating cause.
    **Done:** relevant events carry stable correlation and causal-parent IDs via `causal_context` propagation into `ContinuityEvent` payloads, allowing the runtime and operator surfaces to reconstruct why an action or message occurred.

22. **Background processing lacks a general idempotency contract.** The fixed
    `subagent.complete` spam demonstrated that maintenance/restart processing
    can emit the same logical outcome repeatedly.
    **Done:** repeatable handlers use durable checkpoints and idempotency keys;
    restart/retry proof shows one logical side effect per event.

23. **Concurrent processes can compete for shared state and outward action.**
    Main sessions, idle cognition, task workers, project workers, and Telegram
    may concurrently change focus, embodiment, continuity, or messaging.
    **Done:** state updates and outward actions declare ownership, causal scope,
    and conflict semantics; races are observable and resolved without silently
    discarding another active process.

24. **Scheduler fairness and backpressure are undefined.** A long active
    session can consume most capacity and delay messages, projects, tasks, or
    self-improvement.
    **Done:** scheduling considers active goals, progress, priority, deadlines,
    provider capacity, and cost; runaway work is backpressured without turning
    autonomy into a hard behavioral rule engine.

25. **Addressing and channel selection are not first-class.** Telegram and
    Atrium have previously mirrored or duplicated dialog.
    **Done:** every outward message distinguishes intent, addressee, selected
    channel, and delivery result; channels do not automatically mirror one
    another.

26. **Model capability taxonomy is incomplete.** Provider-level categories
    cannot accurately describe heterogeneous model pools and can route vision,
    embedding, reranking, image, or audio models incorrectly.
    **Done:** capabilities belong to concrete provider model offerings and
    distinguish at least text generation, vision understanding, image
    generation, embeddings, reranking, audio/TTS, tool calling, reasoning, and
    streaming.

27. **Model scorecards suffer from selection bias.** A model receiving nearly
    all work also receives nearly all outcome data, preventing challengers from
    proving that they are better.
    **Done:** controlled exploration/challenger runs evaluate suitable models
    on comparable work while respecting capacity and cost; routing uses both
    exploitation and measured exploration.

28. **Subjective continuity is polluted by technical telemetry.** Lifecycle,
    retries, provider refresh, synthetic proof, and raw cognition can enter the
    same stream used for Sonya's lived continuity.
    **Done:** subjective continuity, work history, operator telemetry, and raw
    audit logs have explicit boundaries and intentional summaries between them.

29. **Work completion can be self-declared without independent evidence.**
    A model or subagent response may be treated as completion without proving
    the requested outcome.
    **Done:** WorkItems support acceptance criteria and evidence such as tests,
    production proof, artifact checks, another executor's review, or Ivan's
    confirmation where appropriate.

30. **Full-system access lacks situational impact semantics.** Permission to
    access a system does not itself describe current activity, blast radius,
    reversibility, or the effect of an action.
    **Done:** action planning can inspect and record target scope, active
    processes, expected impact, reversibility, and observed outcome without
    reducing access to static allow/deny rules.

31. **Archive lifecycle is unspecified.** Google Drive capacity is available,
    but archival, restoration, integrity, deletion, and linkage semantics are
    not yet defined.
    **Done:** archived WorkItems/projects have manifests, integrity checks,
    protected storage, retention/deletion policy, restoration proof, and stable
    links back to live substrate records.

## 6. Security, Recovery, and Epistemic Problems

32. **Untrusted project, web, and tool content can become instructions.**
    Project files, websites, API responses, and tool results enter model
    context without a sufficiently strong distinction between data and trusted
    instructions.
    **Done:** context records preserve authority/trust boundaries; untrusted
    content cannot silently override Ivan, Sonya's own decisions, WorkItem
    goals, or runtime contracts.

33. **Prompt context can become polluted and attention-starved.** Tasks,
    focus, drives, thoughts, history, memory, and environment state compete
    without explicit usefulness and freshness budgets.
    **Done:** context assembly has inspectable budgets, source/value scoring,
    freshness rules, omission reasons, and proof that critical current facts
    survive large contexts.

34. **There is no general source-trust model.** Provenance alone does not say
    how much to trust a message, file, memory, subagent result, tool output,
    external API, or project documentation.
    **Done:** records carry source identity, authority, trust evidence,
    uncertainty, and contradiction history without reducing judgement to one
    fixed trust score.

35. **A provider may change a model behind the same model ID.** Backend,
    quantization, prompt policy, or constraints can drift while old scorecards
    remain attached to the unchanged ID.
    **Done:** offerings retain observed fingerprints/version evidence, canary
    behavior, and drift events that invalidate or segment stale scorecards.

36. **Provider routing ignores information sensitivity.** Free or web-backed
    models may receive private memory, credentials, or confidential project
    content solely because they rank well by capability/cost.
    **Done:** WorkItems, context fragments, and provider offerings carry
    compatible confidentiality/data-handling constraints; routing records what
    data class was sent and why the provider was eligible.

37. **Selfmod can influence its own evaluation boundary.** A change may alter
    tests, benchmarks, scorecards, acceptance criteria, or validation code and
    then use those altered checks as evidence of success.
    **Done:** selfmod evaluation records evaluator provenance and detects
    changes to its own evidence boundary; independent or previous-version
    checks remain available for meaningful validation.

38. **Disaster recovery is documented but not regularly proven end-to-end.**
    Existing backups do not prove that substrate, secrets, knowledge, identity,
    continuity, and runtime can be restored together.
    **Done:** scheduled restore drills create an isolated recovered Sonya,
    verify integrity and startup, measure data loss/recovery time, and record
    the result without replacing production.

39. **Backups are not sufficiently failure-independent.** Backups stored beside
    the live VPS may be lost with the same host/account/storage failure.
    **Done:** encrypted off-host copies exist, retention and access are tested,
    and restore proof uses the off-host copy.

40. **Recovery objectives are undefined.** The project does not define
    acceptable identity/memory loss or restoration time.
    **Done:** RPO/RTO and identity-critical recovery requirements are explicit,
    measurable, and tied to backup/restore verification.

41. **SQLite concurrency assumptions may be unsafe.** Documentation/code
    comments imply row-level write locking, while SQLite WAL still serializes
    writers and can suffer contention as parallel work grows.
    **Done:** concurrency behavior is measured under realistic workers; write
    ownership, transaction duration, busy handling, and scaling limits are
    explicit.

42. **Mixed-version schema access during deploy is not governed.** Core, Admin,
    and workers may briefly read/write one substrate using incompatible runtime
    versions.
    **Done:** migrations declare compatibility windows and deployment ordering;
    incompatible writers fail closed or wait; rollback is proven.

43. **Remote workspaces lack version identity.** Files on another PC/VPS may
    change while Sonya or subagents work, leaving unclear which version was
    inspected or modified.
    **Done:** work actions record workspace version/snapshot evidence and detect
    conflicting external changes before claiming completion.

44. **Remote workspace disconnect/resume semantics are incomplete.** A
    connection loss can leave partially applied actions with uncertain retry
    safety.
    **Done:** remote actions record checkpoints, partial effects, idempotency,
    reconnect validation, and whether retry or human/Sonya review is required.

45. **Reason streams and raw traces can leak sensitive data.** Thoughts, tool
    outputs, files, and provider payloads may expose credentials or private
    content through UI/logging.
    **Done:** data classification, secret detection/redaction, visibility
    policy, and private-event handling apply before rendering or exporting raw
    traces while preserving protected audit evidence.

46. **Credentials pasted into chat need an exposure lifecycle.** Secure import
    does not erase credentials already disclosed through conversation history
    or external platforms.
    **Done:** exposure records identify affected credentials, locations,
    rotation/revocation status, and verification that replacements are active.

47. **Canonical Response is not yet an enforced runtime contract.** Different
    processes can independently create thoughts, actions, Atrium dialog, and
    Telegram output, fragmenting one Sonya into competing output paths.
    **Done:** addressed outward communication and action intent pass through a
    canonical subject-level result/action contract before channel rendering.

48. **Memory consolidation quality is not independently evaluated.**
    Consolidation can promote incorrect interpretation into durable semantic
    facts; deduplication only removes duplicates.
    **Done:** consolidation candidates preserve sources, uncertainty,
    contradictions, and evaluation outcomes; sampled and automated quality
    checks measure false promotion.

49. **Refuted beliefs lack a complete correction lifecycle.** Decay alone does
    not reliably stop retrieval or re-promotion of a disproven semantic fact.
    **Done:** facts can be refuted/superseded, excluded from ordinary retrieval,
    linked to correction history, and prevented from silent re-promotion.

50. **SituationalModel quality itself is not observable.** A WorldState can
    exist while remaining stale, contradictory, or routinely corrected by
    Ivan.
    **Done:** metrics and review surfaces expose expiry, contradictions,
    low-confidence decisions, source quality, and subject corrections, feeding
    measured improvement.

51. **Documentation can provide contradictory active guidance.** Historical
    channel, provider-slot, Atrium-stage, and runtime claims can misdirect Sonya
    or another executor.
    **Done:** canonical precedence is machine-checkable, stale active claims are
    detected, and implementation work records which governing/current docs it
    used.

## 7. Master Execution Checklist

This checklist is the common control surface for the entire audit. A box may be
checked only when the item's **Done** criterion above has production evidence.
Implementation, tests, or documentation alone are not sufficient.

Priority meanings:

- `P0`: foundational correctness; design into the first runtime slices;
- `P1`: required for reliable autonomous work on the hosted stack;
- `P2`: required for mature operation and scaling.

### 7.1 Situational and Epistemic Foundation

- [x] `P0` #1 missing/stale environment and subject status
- [x] `P0` #2 coherent model of other subjects and their participation
- [x] `P0` #3 replace eternal EnvironmentStore semantics with SituationalModel
- [x] `P0` #4 remove credentials from environment/current-state storage
- [x] `P0` #20 prevent generated cognition from becoming its own evidence
- [x] `P0` #34 general source trust/authority model
- [x] `P0` #48 independently evaluate memory consolidation quality
- [x] `P0` #49 refuted-belief correction and retrieval lifecycle
- [x] `P1` #50 SituationalModel quality metrics and review

### 7.2 Agency, Causality, and Scheduling

- [x] `P0` #5 stop self-propelling interaction cycles through meaningful change
- [x] `P0` #6 separate thought, addressed reply, action, and report
- [x] `P0` #21 causal graph and stable correlation IDs
- [x] `P0` #22 durable idempotency and processing checkpoints
- [x] `P0` #23 shared-state and outward-action ownership/conflict semantics
- [x] `P0` #24 scheduler fairness and backpressure
- [x] `P0` #25 explicit addressee/channel selection
- [x] `P0` #47 enforced Canonical Response/action contract
- [x] `P1` #7 close all independently measured spam sources
- [x] `P2` #8 separate lifecycle noise from subjective continuity

### 7.3 Work Runtime and Atrium

- [x] `P0` #9 unify tasks/background work/projects through WorkItems
- [x] `P0` #10 first-class visible tool and work progress
- [x] `P0` #11 measurable and visible real subagent runs
- [x] `P1` #12 provider-native normalized streaming
- [x] `P0` #29 independent WorkItem acceptance evidence
- [x] `P1` #31 complete archive lifecycle and restore linkage
- [x] `P1` #43 remote workspace version/snapshot evidence
- [x] `P1` #44 remote disconnect/resume and partial-effect semantics

### 7.4 Embodiment and Current Self-State

- [x] `P1` #13 causal, stable, non-spamming body expression lifecycle
- [x] `P0` #14 focus lifecycle tied to live work/activity
- [x] `P0` #15 one authoritative outfit/embodiment state

### 7.5 Providers, Models, and Context

- [x] `P0` #16 real model-pool use for main cognition
- [x] `P0` #17 loop/run paid-cost guards and free-first fallback
- [x] `P1` #18 observable retry/fallback and account-scoped refresh
- [x] `P0` #26 offering-scoped capability taxonomy
- [x] `P1` #27 exploration-aware champion/challenger scorecards
- [x] `P0` #32 protect instruction authority from untrusted context
- [x] `P0` #33 context budgets, freshness, and omission observability
- [x] `P1` #35 detect model/provider offering drift
- [x] `P1` #36 verify capability against explicit taxonomy limits

### 7.6 Operator Telemetry, Resilience, and Backup

- [x] `P0` #28 separate subjective continuity, work history, telemetry, and audit
- [x] `P0` #30 protected diagnostic endpoints (operator mode)
- [x] `P0` #37 unified identity boundaries (outfit, persona, rules)
- [x] `P1` #38 scheduled end-to-end disaster restore drills (Operational)
- [x] `P1` #39 encrypted off-host backup and restore proof (Operational)
- [x] `P1` #40 define and prove RPO/RTO and identity recovery requirements
- [x] `P1` #41 measure and govern SQLite writer contention
- [x] `P1` #42 govern mixed-version schema access during deploy
- [x] `P0` #45 prevent sensitive-data leakage through reason streams/traces
- [x] `P0` #46 credential exposure inventory and rotation lifecycle
- [x] `P1` #19 prove Telegram session reliability over restart/deploy cycles (Operational)
- [x] `P1` #51 machine-check canonical documentation precedence/staleness

### 7.7 Evidence Required for Every Checked Item

- [ ] implementation and migration path exist;
- [ ] focused regression tests pass;
- [ ] failure/restart/concurrency proof exists where applicable;
- [ ] production or production-equivalent VPS proof exists;
- [ ] observable evidence is linked from `STATE.md`;
- [ ] rollback/recovery path is recorded;
- [ ] related stale documentation is updated or marked historical.

## 8. Verified Audit Evidence

Read-only production audit on 2026-06-12 found:

- all 445 LLM calls in the observed day used the same OpenRouter Gemma model;
- roughly 12,011,823 tokens were used, mostly by active sessions;
- long sessions reached 53, 55, 57, and 60 steps;
- one 53-step session repeatedly alternated `body.expression` and
  `chat.dialog`;
- stale `activity` and `current_focus`, contradictory outfit values, no
  `ivan_status`, and plaintext API keys existed in current-state storage;
- recent user activity was not consistently used by time-awareness logic;
- provider payloads use `stream: false`; Atrium reveal is client-side;
- proof-subagent completion spam and repeated ordinary dialog were fixed in
  recent slices, but live conversational proof after those deploys is limited;
- recent service warning journal was clean; historical Telegram read-only
  session errors remain documented.

## 9. Can Sonya Fix This Herself?

Partially, today.

Sonya can already create tasks and projects, inspect and change code within
available scopes, use tools, start subagents, and initiate self-repair work.
She can own bounded fixes from this audit when each fix has a clear WorkItem,
workspace, acceptance criteria, and production verification path.

She cannot yet reliably take this entire audit and close it autonomously
end-to-end. The missing foundations are the same problems recorded here:

- no coherent SituationalModel;
- fragmented task/project lifecycle;
- weak distinction between cognition, messages, and actions;
- incomplete visible action runtime and no real streaming;
- de facto single-model cognition and incomplete cost/run guards;
- self-propelling session behavior and incomplete live acceptance proof.

The correct development sequence is therefore to make Sonya progressively able
to own the remaining work:

1. SituationalModel and state separation;
2. unified WorkItem lifecycle and project promotion/archive;
3. explicit cognition/message/action contracts and observable ActionRun;
4. session coherence, run budgets, and provider-pool routing;
5. real streaming and complete Atrium work visibility;
6. let Sonya execute, evaluate, and refine later audit items through her own
   projects/tasks with measured production outcomes.

## 10. Priority

This audit overrides claims that only the web-proxy bridge remains open.
Runtime coherence is the immediate hosted-stack priority. The web-proxy bridge
remains valuable, but adding more cheap capacity before loop, state, routing,
and cost semantics are coherent would amplify existing failures.

Cross-cutting foundations that must be designed into the first slices rather
than postponed:

- provenance and protection against self-reinforcing generated assumptions;
- causal IDs and idempotency;
- shared-state ownership and scheduler backpressure;
- separation of subjective continuity from technical telemetry;
- independent WorkItem acceptance evidence.

### 11. Upcoming Priorities (June 2026)
These are planned functional evolutions and fixes, broken down into detailed actionable steps:

- [ ] **1. Rework Provider Account Visibility**
  - **Problem:** Currently, API keys and accounts are globally visible or assigned awkwardly through lists of keys per model, leading to security and routing inefficiencies.
  - **Action:** Refactor `src/sonya/state/schema.sql` and the active substrate to implement isolated provider account records. Keys should be hidden by default from global logs. Ensure the routing engine can select the best active account dynamically based on balance and health checks without hardcoded lists. Update the Admin UI to reflect this new schema.
- [x] **2. Subagent Execution Check**
  - **Problem:** Subagent invocation paths might be fragile, and their state persistence or error bubbling might drop critical context.
  - **Action:** Perform a deep-dive trace of `src/sonya/subject/subagent_*.py`. Implement end-to-end tests for subagent delegation. Ensure that subagents can correctly report back nested JSON results without breaking the parent's ReAct loop, and verify that their context windows do not bleed into the main session unexpectedly.
- [ ] **3. Model Acceptance Testing System**
  - **Problem:** We have many models configured, but no automated way to know if a model actually understands the specific ReAct format, JSON tool arguments, or gracefully handles tool failures.
  - **Action:** Build a standalone evaluation suite (e.g., `tests/eval_models.py`) that runs every active model through a rigorous gauntlet: extracting complex tool arguments, fixing a simulated syntax error, and understanding implicit instructions. Automatically disable or flag models that fail this baseline acceptance test to keep the model pool highly reliable.
- [x] **4. Tool and Response Formatting**
  - **Problem:** Outputs were originally Telegram-centric, meaning they were heavily parsed and scrubbed, causing Atrium to receive sanitized text missing vital context like raw tool blocks.
  - **Action:** Migrated formatting logic. Atrium now receives direct, unparsed `stream_text` natively, allowing the UI to render raw tool blocks (`[TOOL: ...]`) correctly. Telegram parsing was separated and fixed (`_DONE_RE` and `_scrub`) to ensure it gets clean text without leaking internal markers like `[DONE]`.
- [ ] **5. Rebalance Reasoning and Drive Engines**
  - **Problem:** Internal counters like `curiosity_analog` are frequently maxed out, and the interplay between persona traits, emotion engines, and base drives feels unbalanced or erratic.
  - **Action:** Audit `src/sonya/subject/drive_engine.py` and the cognitive loop. Implement decay functions for emotional states and drives so they normalize over time. Tune the weights so that curiosity scales with actual unknown variables rather than permanently sitting at 100%. Add telemetry to monitor drive stability over long sessions.
- [ ] **6. Global Admin UI Redesign**
  - **Problem:** The fallback Admin panel (FastAPI/Jinja) looks dated and doesn't match the premium, modern aesthetic of Atrium (glassmorphism, vibrant palettes).
  - **Action:** Completely overhaul the CSS and layout of the Admin panel. Use a cohesive design system (vibrant colors, sleek dark modes, modern typography like Inter/Outfit). Implement responsive layouts and micro-animations to make the administrative experience feel state-of-the-art.
- [ ] **7. Migrate Settings out of Atrium**
  - **Problem:** Administrative configurations (like adding providers, changing model weights, or system prompts) are bleeding into the Atrium UI, cluttering the workspace.
  - **Action:** Strip all pure configuration screens out of Atrium. Atrium should remain a focused communication and workspace window. Migrate all removed settings logic and UI components to the newly redesigned Admin panel, ensuring a strict separation of concerns.
- [ ] **8. Audit Existing Skills**
  - **Problem:** Several built-in tools (especially `web.search` and filesystem navigation) are reportedly flaky or fail on edge cases.
  - **Action:** Systematically test every tool in `src/sonya/tools/`. For `web.search`, ensure the parser handles modern anti-bot protections or provides graceful degradation. Add strict typing and error boundary catchers to prevent a single tool failure from crashing the entire session.
- [ ] **9. Self-Healing and Error Correction**
  - **Problem:** Sonya often hesitates or fails to utilize her self-modification (`selfmod.*`) tools when encountering errors, waiting for user intervention instead.
  - **Action:** Enhance the system prompt and the ReAct loop instructions to explicitly mandate autonomous recovery. If an execution fails (e.g., `code.exec` throws a traceback), Sonya must automatically trigger a diagnostic tool and propose a fix without asking for permission first, achieving true autonomy.
