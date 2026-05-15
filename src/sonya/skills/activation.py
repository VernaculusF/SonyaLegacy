from __future__ import annotations

from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel


class SkillActivationDeniedError(RuntimeError):
    pass


def can_activate(skill: Skill) -> bool:
    """Check if a skill is allowed to activate based on trust level and status.

    Rules-based stub. Real ML matching — post-MVP.

    Rules:
    - quarantined skills CANNOT activate regardless of other conditions;
    - deprecated/archived skills CANNOT activate;
    - active skills with trust >= limited CAN activate.
    """
    if skill.trust_level is TrustLevel.QUARANTINED:
        return False
    if skill.status != "active":
        return False
    return True


def activate_or_raise(skill: Skill) -> None:
    """Activate a skill or raise SkillActivationDeniedError."""
    if not can_activate(skill):
        raise SkillActivationDeniedError(
            f"skill {skill.skill_id!r} cannot activate: "
            f"trust_level={skill.trust_level.value}, status={skill.status}"
        )
