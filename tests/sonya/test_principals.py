from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import (
    Principal,
    PrincipalAlreadyExistsError,
    PrincipalRegistry,
    Substrate,
)


@pytest.fixture()
def registry(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    reg = PrincipalRegistry(sub)
    yield reg
    sub.close()


def test_register_and_get(registry: PrincipalRegistry) -> None:
    p = registry.register(
        Principal(principal_id="ivan", display_name="Иван", trusted_identifiers=("tg:1",))
    )
    assert p.principal_id == "ivan"
    assert registry.get("ivan") == p


def test_get_missing_returns_none(registry: PrincipalRegistry) -> None:
    assert registry.get("ghost") is None


def test_principal_id_is_unique(registry: PrincipalRegistry) -> None:
    registry.register(Principal(principal_id="a", display_name="A"))
    with pytest.raises(PrincipalAlreadyExistsError):
        registry.register(Principal(principal_id="a", display_name="A2"))


def test_resolve_by_trusted_identifier(registry: PrincipalRegistry) -> None:
    registry.register(
        Principal(
            principal_id="ivan",
            display_name="Иван",
            trusted_identifiers=("tg:5785127604", "discord:xyz"),
        )
    )
    found = registry.resolve_by_trusted_identifier("tg:5785127604")
    assert found is not None and found.principal_id == "ivan"
    assert registry.resolve_by_trusted_identifier("tg:0000") is None


def test_list_all_orders_by_created_at(registry: PrincipalRegistry) -> None:
    a = registry.register(Principal(principal_id="a", display_name="A"))
    b = registry.register(Principal(principal_id="b", display_name="B"))
    listed = registry.list_all()
    ids = [p.principal_id for p in listed]
    assert ids == [a.principal_id, b.principal_id]
