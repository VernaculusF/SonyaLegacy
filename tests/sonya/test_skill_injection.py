from __future__ import annotations

from pathlib import Path

import pytest

from sonya.skills import Skill, SkillRegistry, TrustLevel
from sonya.skills.injection import SkillCandidate, extract_candidates, promote_candidate
from sonya.state import Substrate


def test_extract_finds_always_do_pattern() -> None:
    text = "Always do a backup before deploying"
    candidates = extract_candidates(text)
    assert len(candidates) == 1
    assert "backup" in candidates[0].purpose.lower()


def test_extract_finds_remember_to_pattern() -> None:
    text = "Remember to check tests before committing code"
    candidates = extract_candidates(text)
    assert len(candidates) == 1
    assert "check tests" in candidates[0].purpose.lower()


def test_extract_ignores_normal_text() -> None:
    text = "How are you doing today?"
    candidates = extract_candidates(text)
    assert len(candidates) == 0


def test_extract_multiple_patterns() -> None:
    text = "Every time you respond, be concise. From now on use markdown."
    candidates = extract_candidates(text)
    assert len(candidates) == 2


def test_promote_requires_approval() -> None:
    candidate = SkillCandidate(name="x", purpose="y", source_pattern="z", approved=False)
    with pytest.raises(ValueError, match="approved"):
        promote_candidate(candidate, None, "skill-1")  # type: ignore


def test_promote_approved_candidate(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "s.db")
    try:
        registry = SkillRegistry(sub)
        candidate = SkillCandidate(
            name="backup_skill",
            purpose="Always backup before deploy",
            source_pattern="always do",
            approved=True,
        )
        skill = promote_candidate(candidate, registry, "skill-backup")
        assert skill.skill_id == "skill-backup"
        assert skill.trust_level is TrustLevel.EXPERIMENTAL

        loaded = registry.get("skill-backup")
        assert loaded.purpose == "Always backup before deploy"
    finally:
        sub.close()
