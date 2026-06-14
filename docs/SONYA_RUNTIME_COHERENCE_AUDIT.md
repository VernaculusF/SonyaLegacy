# Sonya Runtime Coherence Audit

**Status:** Active canonical architecture audit
**Last updated:** 2026-06-12
**Scope:** situational understanding, autonomy, work execution, embodiment,
provider routing, observability, and runtime hygiene.

Implementation and deployment workflow for this audit:
[`docs/operations/RUNTIME_COHERENCE_WORKFLOW.md`](operations/RUNTIME_COHERENCE_WORKFLOW.md).


## 1. Divergence from Original Mission (`ОСНОВА.md` and `docs/core`)

This audit evaluates the current state against the original foundational principles defined in `docs/план/ОСНОВА.md` and `docs/core/SONYA_SYSTEM_CORE.md`.

- **Model Architecture and State Tuning Drift:** `ОСНОВА.md` establishes Sonya as a continuous entity running on an `RWKV-7` architecture with personality anchored via `State Tuning`. The current implementation is heavily dependent on stateless external models (OpenRouter Gemma). This fundamentally diverges from the core vision of a self-contained, continuous state.
- **Subsystem Fragmentation (`tasks` vs `work`):** The codebase transition from the legacy `tasks` system to the new `work` item architecture is incomplete. Orphaned code remains in `src/sonya/tasks/`, and legacy fields (e.g., `stuck_loop_count`) were left unmigrated. This architectural fragmentation directly caused recent runtime bugs, such as the failure of the `stuck_loop` detector due to mismatched event names (`item.session_handoff` vs `work.session_handoff`).
- **Embodiment and Initiative Mechanisms:** The original plan dictates that initiative should be driven by concrete "body spikes" (e.g., loneliness metrics from an SNN/Loihi setup). The current system relies on abstract counters like `curiosity_analog`, which are frequently maxed out and unbalanced, leading to erratic, self-propelling sessions rather than grounded initiative.
- **Channel vs. Renderer Entanglement:** `SONYA_SYSTEM_CORE.md` explicitly mandates that channels (Telegram, Atrium) act merely as "renderers" of the core state. However, channel-specific parsing logic has leaked into the core runtime, historically causing bugs like duplicate message echoes and action-report leaks.
