from __future__ import annotations

from dataclasses import dataclass

from sonya.skills.registry import SkillRegistry
from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel


@dataclass(frozen=True, slots=True)
class SkillCandidate:
    """A candidate skill extracted from user message patterns.

    Requires manual approval before promotion to registry.
    """

    name: str
    purpose: str
    source_pattern: str
    approved: bool = False


# Simple keyword patterns that suggest a promotable skill
_PROMOTION_KEYWORDS: tuple[str, ...] = (
    "always do",
    "every time",
    "remember to",
    "from now on",
    "make sure to",
)


def extract_candidates(text: str) -> list[SkillCandidate]:
    """Extract promotable skill candidates from user message text.

    Simple keyword-based rules. Production-quality scoring — post-MVP.
    """
    candidates: list[SkillCandidate] = []
    text_lower = text.lower()
    for keyword in _PROMOTION_KEYWORDS:
        if keyword in text_lower:
            # Extract the instruction after the keyword
            idx = text_lower.index(keyword)
            instruction = text[idx + len(keyword):].strip()
            if instruction and len(instruction) > 5:
                candidates.append(
                    SkillCandidate(
                        name=f"user_instruction_{len(candidates)}",
                        purpose=instruction[:100],
                        source_pattern=keyword,
                    )
                )
    return candidates


def promote_candidate(
    candidate: SkillCandidate,
    registry: SkillRegistry,
    skill_id: str,
) -> Skill:
    """Promote an approved candidate to the skill registry.

    Requires candidate.approved == True (manual approval gate).
    """
    if not candidate.approved:
        raise ValueError("candidate must be approved before promotion")
    skill = Skill(
        skill_id=skill_id,
        name=candidate.name,
        purpose=candidate.purpose,
        trust_level=TrustLevel.EXPERIMENTAL,
        activation_rules={"source": "user_injection", "pattern": candidate.source_pattern},
    )
    return registry.register(skill)
