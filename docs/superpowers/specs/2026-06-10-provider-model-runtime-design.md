# Provider Model Runtime Design

**Status:** Approved documentation design
**Date:** 2026-06-10

## Goal

Replace the remaining fixed provider/key/model assumptions with a runtime where
Sonya can safely manage providers and accounts, discover model offerings, and
choose subagent models using current evidence.

## Decisions

- Provider, account, model identity, and provider offering are separate objects.
- Account-to-offering access is many-to-many.
- Secrets never enter documentation, prompts, continuity, or normal traces.
- Sonya manages the system through typed internal capabilities invoked from
  natural-language requests.
- Runtime observations and evaluation evidence guide routing; no permanent
  keyword/profile rule engine.
- Planner/worker nesting is an experiment, not an invariant.
- Every substantial change is proved locally and on the VPS.

## Deliverables

- provider registry and adapter capability contract
- provider account and secret-reference lifecycle
- account-specific offerings and structured quota windows
- discovery and health refresh
- evidence-driven routing
- complete Sonya/admin management surfaces
- migration away from Fireworks and fixed-model key fields
