from __future__ import annotations

from sonya.selfmod.layers.static_contract import ValidationResult
from sonya.selfmod.proposal import SelfModificationProposal


def check_trace_replay(proposal: SelfModificationProposal) -> ValidationResult:
    """Layer 3: Trace Replay.

    STUB — passes with 'not enough data' on MVP. Real implementation
    (post-MVP Track B): takes sliding window of last N days of real
    canonical responses and continuity events, replays inputs through
    the modified module, compares output with what actually happened.
    Undeclared divergence = failure.
    """
    return ValidationResult(
        layer=3, passed=True, reason="stub: not enough data for replay"
    )
