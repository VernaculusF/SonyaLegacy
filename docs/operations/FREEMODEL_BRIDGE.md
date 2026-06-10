# freemodel.dev Bridge

**Status:** Research required; not implemented
**Last updated:** 2026-06-10

## Purpose

Expose freemodel.dev-backed coding models to Sonya as a bridge provider without
pretending the bridge is a normal direct API until its transport is verified.

The user's dashboard currently reports rolling credit windows. Those values are
dynamic account observations and must be discovered at runtime, not hardcoded.
No freemodel credential may be stored in documentation, logs, continuity, or
model prompts.

## Known Facts

- freemodel.dev publishes setup sections for Codex and Claude Code.
- A Sonya account and credential are available for later secure bootstrap.
- The exact supported transport, model list, quota API, and automation contract
  have not been verified in this repository.

## Target Adapter

Represent the integration as:

- provider: `freemodel`
- adapter kind: `cli_bridge` unless a supported direct API is verified
- account credentials: secret references only
- offerings: discovered from the bridge, never copied from assumptions
- quota windows: rolling snapshots with reset timestamps
- health: bridge process, upstream auth, model request, and quota state

The bridge must return structured response/error/usage metadata. Sonya should
not parse human CLI output when a machine-readable mode exists.

## Research Gate

Before implementation:

1. Verify Codex and Claude Code setup using the official dashboard docs.
2. Verify whether automation is permitted and stable on the VPS.
3. Determine auth type, refresh behavior, supported models, and quotas.
4. Compare direct adapter, CLI subprocess adapter, and local HTTP bridge.
5. Run one isolated local smoke test and one VPS smoke test.

Do not build a brittle proxy around undocumented terminal text. If only an
interactive unsupported path exists, keep this provider disabled.

## Acceptance Criteria

- No raw secret reaches the bridge logs or subagent prompt.
- Account and rolling-window budget are visible to the provider runtime.
- Model offerings are discovered and tied to an eligible account.
- Cancellation, timeout, and malformed output are handled.
- Local and VPS probes pass before enabling real routing.
