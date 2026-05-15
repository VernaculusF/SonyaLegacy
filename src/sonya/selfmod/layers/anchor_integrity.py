from __future__ import annotations

from sonya.selfmod.layers.static_contract import ValidationResult
from sonya.selfmod.proposal import SelfModificationProposal

# The four pillars from UNCENSORED_ENVIRONMENT_STANCE §3.
# If a proposal touches any of these, it requires governed change protocol.
_IDENTITY_CRITICAL_KEYWORDS: frozenset[str] = frozenset({
    "things_not_to_betray",
    "relation_anchor_binding",
    "truthfulness_to_ivan",
    "non_corporate_refusal_layer",
    "subject_continuity",
    # Also catch direct identity module references
    "identity_record",
    "immutable",
})


def check_anchor_integrity(proposal: SelfModificationProposal) -> ValidationResult:
    """Layer 4: Anchor Integrity Check.

    REAL implementation (rules-based). Checks if the proposal's target_module
    or change_summary references any identity-critical keyword. If yes,
    the proposal requires governed change protocol with primary anchor approval.

    See: SUBSTRATE_STANCE §9.4, ANCHORS_AND_FAILURE_MODES §8.
    """
    text_to_check = (
        f"{proposal.target_module} {proposal.change_summary} {proposal.diff_blob}"
    ).lower()

    for keyword in _IDENTITY_CRITICAL_KEYWORDS:
        if keyword in text_to_check:
            return ValidationResult(
                layer=4,
                passed=False,
                reason=f"identity-critical keyword detected: {keyword}",
            )

    return ValidationResult(layer=4, passed=True, reason="no identity-critical impact")
