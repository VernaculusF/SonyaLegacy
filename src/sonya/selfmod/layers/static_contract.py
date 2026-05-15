from __future__ import annotations

from dataclasses import dataclass

from sonya.selfmod.proposal import SelfModificationProposal


@dataclass(frozen=True, slots=True)
class ValidationResult:
    layer: int
    passed: bool
    reason: str = ""


def check_static_contract(proposal: SelfModificationProposal) -> ValidationResult:
    """Layer 1: Static Contract Check.

    STUB — always passes on MVP. Real implementation (post-MVP Track B):
    AST analysis of changed code, Protocol compatibility verification,
    signature compatibility check.
    """
    return ValidationResult(layer=1, passed=True, reason="stub: always passes")
