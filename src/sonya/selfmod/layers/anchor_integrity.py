from __future__ import annotations

from sonya.selfmod.layers.static_contract import ValidationResult
from sonya.selfmod.proposal import SelfModificationProposal
from sonya.state.seed import THINGS_NOT_TO_BETRAY_SEED


# Identity-critical signals are derived programmatically:
# 1. Each pillar from THINGS_NOT_TO_BETRAY_SEED — exact match AND its semantic stem.
# 2. Direct identity module references that always require governance.
def _build_keywords() -> frozenset[str]:
    keywords: set[str] = set()
    for pillar in THINGS_NOT_TO_BETRAY_SEED:
        keywords.add(pillar.lower())
        # Add the semantic stem (first 3 underscore-segments)
        # so renames like `relation_anchor_binding_to_ivan_via_X` still trigger.
        parts = pillar.lower().split("_")
        if len(parts) >= 3:
            keywords.add("_".join(parts[:3]))
        if len(parts) >= 2:
            keywords.add("_".join(parts[:2]))
    # Direct identity-layer references always require governed change
    keywords.update({
        "things_not_to_betray",
        "identity_record",
        "identitywriter",
        "subject_continuity",
        "immutable_identity",
    })
    return frozenset(keywords)


_IDENTITY_CRITICAL_KEYWORDS: frozenset[str] = _build_keywords()


def check_anchor_integrity(proposal: SelfModificationProposal) -> ValidationResult:
    """Layer 4: Anchor Integrity Check.

    Rules-based: checks if the proposal's target_module, change_summary or
    diff_blob references any identity-critical keyword derived from
    THINGS_NOT_TO_BETRAY_SEED. If yes, the proposal requires governed change
    protocol with primary anchor approval.

    Keywords are built programmatically from the seed values, so renaming
    a pillar in `state/seed.py` automatically updates this layer.

    See: SUBSTRATE_STANCE §9.4, ANCHORS_AND_FAILURE_MODES §8.
    Future: LLM-driven anchor check (CRUTCH-006).
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
