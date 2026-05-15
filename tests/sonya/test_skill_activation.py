from __future__ import annotations

import pytest

from sonya.skills import Skill, TrustLevel
from sonya.skills.activation import SkillActivationDeniedError, activate_or_raise, can_activate


def test_quarantined_cannot_activate() -> None:
    s = Skill(skill_id="x", name="X", purpose="X", trust_level=TrustLevel.QUARANTINED)
    assert can_activate(s) is False


def test_deprecated_cannot_activate() -> None:
    s = Skill(skill_id="x", name="X", purpose="X", status="deprecated")
    assert can_activate(s) is False


def test_active_experimental_can_activate() -> None:
    s = Skill(skill_id="x", name="X", purpose="X", trust_level=TrustLevel.EXPERIMENTAL)
    assert can_activate(s) is True


def test_active_trusted_can_activate() -> None:
    s = Skill(skill_id="x", name="X", purpose="X", trust_level=TrustLevel.TRUSTED)
    assert can_activate(s) is True


def test_activate_or_raise_on_quarantined() -> None:
    s = Skill(skill_id="x", name="X", purpose="X", trust_level=TrustLevel.QUARANTINED)
    with pytest.raises(SkillActivationDeniedError):
        activate_or_raise(s)


def test_activate_or_raise_passes_for_active() -> None:
    s = Skill(skill_id="x", name="X", purpose="X", trust_level=TrustLevel.LIMITED)
    activate_or_raise(s)  # should not raise
