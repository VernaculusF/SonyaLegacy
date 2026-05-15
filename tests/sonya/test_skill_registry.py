from __future__ import annotations

from pathlib import Path

import pytest

from sonya.skills import Skill, SkillAlreadyExistsError, SkillNotFoundError, SkillRegistry, TrustLevel
from sonya.state import Substrate


@pytest.fixture()
def registry(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield SkillRegistry(sub)
    sub.close()


def test_register_and_get(registry: SkillRegistry) -> None:
    s = Skill(skill_id="reply-tg", name="Telegram Reply", purpose="Reply via Telegram")
    registry.register(s)
    loaded = registry.get("reply-tg")
    assert loaded.name == "Telegram Reply"
    assert loaded.trust_level is TrustLevel.EXPERIMENTAL


def test_get_missing_raises(registry: SkillRegistry) -> None:
    with pytest.raises(SkillNotFoundError):
        registry.get("nonexistent")


def test_register_duplicate_raises(registry: SkillRegistry) -> None:
    s = Skill(skill_id="x", name="X", purpose="X")
    registry.register(s)
    with pytest.raises(SkillAlreadyExistsError):
        registry.register(s)


def test_list_active(registry: SkillRegistry) -> None:
    registry.register(Skill(skill_id="a", name="A", purpose="A"))
    registry.register(Skill(skill_id="b", name="B", purpose="B"))
    registry.update_status("a", "deprecated")
    active = registry.list_active()
    ids = [s.skill_id for s in active]
    assert "b" in ids
    assert "a" not in ids


def test_trust_levels_all_valid() -> None:
    expected = {"core_trusted", "trusted", "limited", "experimental", "quarantined"}
    actual = {t.value for t in TrustLevel}
    assert actual == expected


def test_skill_14_fields() -> None:
    s = Skill(
        skill_id="full",
        name="Full Skill",
        purpose="Test all fields",
        version="1.0.0",
        status="active",
        trust_level=TrustLevel.TRUSTED,
        activation_rules={"trigger": "keyword:deploy"},
        dependencies=("base-skill",),
        allowed_tools=("shell", "fs"),
        forbidden_zones=("identity",),
        tests=("test_deploy",),
        metrics={"success_rate": 0.95},
        trace_tags=("deploy", "ops"),
        history=("created 2026-05-15",),
    )
    assert s.skill_id == "full"
    assert s.activation_rules["trigger"] == "keyword:deploy"
    assert "shell" in s.allowed_tools


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    SkillRegistry(sub1).register(Skill(skill_id="persist", name="P", purpose="P"))
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        loaded = SkillRegistry(sub2).get("persist")
        assert loaded.name == "P"
    finally:
        sub2.close()
