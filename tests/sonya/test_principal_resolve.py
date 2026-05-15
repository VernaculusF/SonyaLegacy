from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import Principal, PrincipalRegistry, Substrate


@pytest.fixture()
def registry(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    registry = PrincipalRegistry(sub)
    registry.register(
        Principal(
            principal_id="ivan",
            display_name="Иван",
            trusted_identifiers=("tg:5785127604", "matrix:@ivan:home"),
            authority_scope=("*",),
        )
    )
    yield registry
    sub.close()


def test_resolve_from_channel_input_found(registry: PrincipalRegistry) -> None:
    p = registry.resolve_from_channel_input("telegram", "5785127604")
    assert p is not None
    assert p.principal_id == "ivan"


def test_resolve_from_channel_input_alias_matrix(registry: PrincipalRegistry) -> None:
    p = registry.resolve_from_channel_input("matrix", "@ivan:home")
    assert p is not None
    assert p.principal_id == "ivan"


def test_resolve_from_channel_input_unknown(registry: PrincipalRegistry) -> None:
    assert registry.resolve_from_channel_input("telegram", "999") is None


def test_resolve_from_channel_input_unknown_channel(
    registry: PrincipalRegistry,
) -> None:
    assert registry.resolve_from_channel_input("discord", "5785127604") is None


def test_resolve_passes_through_to_trusted_identifier(
    registry: PrincipalRegistry,
) -> None:
    by_full = registry.resolve_by_trusted_identifier("tg:5785127604")
    by_split = registry.resolve_from_channel_input("telegram", "5785127604")
    assert by_full == by_split


def test_resolve_telegram_canonicalises_to_tg(registry: PrincipalRegistry) -> None:
    """`telegram` channel name maps to stored `tg:` prefix."""
    p = registry.resolve_from_channel_input("telegram", "5785127604")
    assert p is not None
    assert "tg:5785127604" in p.trusted_identifiers


def test_resolve_blank_value_returns_none(registry: PrincipalRegistry) -> None:
    assert registry.resolve_from_channel_input("telegram", "") is None


def test_resolve_blank_channel_returns_none(registry: PrincipalRegistry) -> None:
    assert registry.resolve_from_channel_input("", "5785127604") is None
