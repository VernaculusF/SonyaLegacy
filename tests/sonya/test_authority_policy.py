from __future__ import annotations

from pathlib import Path

import pytest

from sonya.harness import AuthorityDecision, AuthorityPolicy
from sonya.state import Principal, Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def _ivan(scope: tuple[str, ...] = ()) -> Principal:
    return Principal(
        principal_id="ivan",
        display_name="Иван",
        trusted_identifiers=("tg:5785127604",),
        authority_scope=scope,
    )


def test_empty_policy_denies(substrate: Substrate) -> None:
    policy = AuthorityPolicy(substrate)
    assert policy.authorize(_ivan(), "runtime.shutdown") is AuthorityDecision.DENY


def test_allow_rule_for_specific_scope(substrate: Substrate) -> None:
    policy = AuthorityPolicy(substrate)
    policy.add_rule(
        principal_id="ivan",
        scope="runtime.shutdown",
        decision=AuthorityDecision.ALLOW,
    )
    assert policy.authorize(_ivan(), "runtime.shutdown") is AuthorityDecision.ALLOW
    # other scope still denied by absence
    assert policy.authorize(_ivan(), "identity.write_immutable") is AuthorityDecision.DENY


def test_wildcard_scope_matches_any(substrate: Substrate) -> None:
    policy = AuthorityPolicy(substrate)
    policy.add_rule(
        principal_id="ivan",
        scope="*",
        decision=AuthorityDecision.ALLOW,
    )
    assert policy.authorize(_ivan(), "runtime.shutdown") is AuthorityDecision.ALLOW
    assert policy.authorize(_ivan(), "anything.else") is AuthorityDecision.ALLOW


def test_priority_overrides(substrate: Substrate) -> None:
    policy = AuthorityPolicy(substrate)
    policy.add_rule(
        principal_id="ivan", scope="*", decision=AuthorityDecision.ALLOW, priority=0
    )
    policy.add_rule(
        principal_id="ivan",
        scope="identity.write_immutable",
        decision=AuthorityDecision.REQUIRE_APPROVAL,
        priority=100,
    )
    assert (
        policy.authorize(_ivan(), "identity.write_immutable")
        is AuthorityDecision.REQUIRE_APPROVAL
    )
    assert policy.authorize(_ivan(), "runtime.shutdown") is AuthorityDecision.ALLOW


def test_other_principal_denied(substrate: Substrate) -> None:
    policy = AuthorityPolicy(substrate)
    policy.add_rule(
        principal_id="ivan", scope="*", decision=AuthorityDecision.ALLOW
    )
    other = Principal(principal_id="stranger", display_name="X")
    assert policy.authorize(other, "runtime.shutdown") is AuthorityDecision.DENY


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    AuthorityPolicy(sub1).add_rule(
        principal_id="ivan", scope="*", decision=AuthorityDecision.ALLOW
    )
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        rules = AuthorityPolicy(sub2).list_rules()
        assert len(rules) == 1
        assert rules[0].principal_id == "ivan"
    finally:
        sub2.close()


def test_remove_rule(substrate: Substrate) -> None:
    policy = AuthorityPolicy(substrate)
    rule = policy.add_rule(
        principal_id="ivan", scope="*", decision=AuthorityDecision.ALLOW
    )
    assert policy.authorize(_ivan(), "x") is AuthorityDecision.ALLOW
    assert policy.remove_rule(rule.rule_id) is True
    assert policy.authorize(_ivan(), "x") is AuthorityDecision.DENY
    assert policy.remove_rule(rule.rule_id) is False
