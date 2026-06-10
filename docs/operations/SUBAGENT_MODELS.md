# Subagent Model Selection

**Status:** Active policy
**Last updated:** 2026-06-10
**Runtime truth:** substrate observations, not this file

This document defines how Sonya chooses models for one-shot internal subagents.
The provider inventory lives in
[`PROVIDER_MODEL_CATALOG.md`](PROVIDER_MODEL_CATALOG.md). The target data model
lives in [`PROVIDER_SYSTEM_DESIGN.md`](PROVIDER_SYSTEM_DESIGN.md).

## Invariants

- A subagent is an internal one-shot tool, not another Sonya and not a UI actor.
- Sonya decides whether to delegate, how many workers to create, their model,
  task, and filesystem scope.
- Provider and model are separate choices. A provider exposes accounts and a
  pool of model offerings.
- No fixed provider-to-model binding and no permanent keyword rule engine.
- Explicit model selection is an override, not the default architecture.
- Raw subagent traces may be visible, but only summaries and lessons enter
  Sonya's durable memory.

## Selection Inputs

Before `subagent.spawn`, Sonya should express a small task requirement object:

- role: planner, executor, reviewer, researcher, cleanup, multimodal
- required modalities and tool support
- estimated context and output size
- quality/risk level
- latency tolerance and deadline
- budget ceiling
- filesystem scope
- known provider constraints that matter for this task

The runtime then filters unavailable offerings and ranks the rest using:

- current account/provider/model health
- remaining quota and budget windows
- context fit and supported modalities
- measured success for similar tasks
- measured latency, error rate, and refusal/constraint rate
- marginal cost

Hard filters protect capability and availability. Ranking is soft and
evidence-driven. Sonya retains judgment and may override the recommendation.

## Evidence Levels

Model claims must carry one of these evidence levels:

1. `advertised`: provider metadata only
2. `user_observed`: reported by Ivan, not reproduced
3. `benchmarked`: measured by Sonya's evaluation harness
4. `production_observed`: measured during real work

Do not encode advertised or anecdotal strengths as permanent routing truth.

## Long-Context Carrier Experiment

`nvidia/nemotron-3-ultra:free` through Nous is a candidate carrier/coordinator
because it advertises a very large context window. Ivan reports that it is weak
at coding. Treat this as a hypothesis:

- carrier reads and compresses broad context;
- stronger coding worker receives a minimal scoped packet;
- optional reviewer checks risky output;
- Sonya remains the only orchestrator.

Nested planner/worker execution is allowed only when evaluation shows better
quality or lower total token/cost use. It must not become mandatory recursion.

## Premium Escalation

Premium and last-resort providers are selected only when one of these is true:

- free/low-cost candidates failed or lack required capability;
- task risk justifies a stronger reviewer;
- deadline makes slower free candidates unsuitable;
- Ivan explicitly requests a premium model.

The trace must record why escalation happened.

## Current Runtime Gap

The picker now ranks only currently eligible substrate account offerings.
Hard-coded provider/model candidates and fixed purpose hints have been removed.
The remaining gap is operational evidence: most providers are not bootstrapped,
quota observations and scorecards are sparse, and the subagent lifecycle does
not yet record enough requirement/scope/outcome data for strong routing.

## Acceptance Criteria

- Adding a provider/model/account does not require editing the picker.
- A model is selectable only through an eligible account offering.
- Provider outages and quota exhaustion remove affected offerings immediately.
- Model choices and overrides are traceable.
- Scorecards improve future choices without turning into rigid rules.
