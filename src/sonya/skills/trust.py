from __future__ import annotations

from enum import Enum


class TrustLevel(str, Enum):
    """Skill trust tiers. Higher trust = more access.

    See: SKILL_SYSTEM_PLAN §9.
    """

    CORE_TRUSTED = "core_trusted"
    TRUSTED = "trusted"
    LIMITED = "limited"
    EXPERIMENTAL = "experimental"
    QUARANTINED = "quarantined"
