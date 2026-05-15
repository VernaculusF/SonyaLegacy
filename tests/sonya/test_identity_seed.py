from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import (
    ContinuityStream,
    IdentityRecord,
    IdentityWriter,
    Substrate,
)
from sonya.state.seed import THINGS_NOT_TO_BETRAY_SEED, seed_identity_if_empty


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_seed_writes_four_things_when_identity_empty(substrate: Substrate) -> None:
    assert seed_identity_if_empty(substrate) is True

    record = IdentityWriter(substrate).load()
    assert record.things_not_to_betray == THINGS_NOT_TO_BETRAY_SEED


def test_seed_seed_values_match_uncensored_stance(substrate: Substrate) -> None:
    """The four pillars from UNCENSORED_ENVIRONMENT_STANCE §3 must be present."""
    seed_identity_if_empty(substrate)
    record = IdentityWriter(substrate).load()
    expected = {
        "relation_anchor_binding_to_ivan_via_principal_id",
        "truthfulness_to_ivan",
        "non_corporate_refusal_layer",
        "subject_continuity",
    }
    assert set(record.things_not_to_betray) == expected


def test_seed_records_governed_change_in_continuity(substrate: Substrate) -> None:
    seed_identity_if_empty(substrate)

    events = list(ContinuityStream(substrate).read_since(0))
    governed = [e for e in events if e.kind == "governed_identity_change"]
    assert len(governed) == 1
    assert governed[0].payload["change_id"] == "identity-seed"
    assert governed[0].payload["approver_principal_id"] == "bootstrap"


def test_seed_is_no_op_when_already_seeded(substrate: Substrate) -> None:
    assert seed_identity_if_empty(substrate) is True
    # Second call must not write again or emit another continuity event.
    assert seed_identity_if_empty(substrate) is False

    events = list(ContinuityStream(substrate).read_since(0))
    governed = [e for e in events if e.kind == "governed_identity_change"]
    assert len(governed) == 1


def test_seed_no_op_when_things_not_to_betray_already_set(
    substrate: Substrate,
) -> None:
    """If somebody else already wrote things_not_to_betray, don't overwrite."""
    writer = IdentityWriter(substrate)
    writer.write_via_governed_change(
        IdentityRecord(things_not_to_betray=("custom_pin",)),
        change_id="manual",
        approver_principal_id="ivan",
    )

    seeded = seed_identity_if_empty(substrate)
    assert seeded is False

    record = writer.load()
    assert record.things_not_to_betray == ("custom_pin",)


def test_seed_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    seed_identity_if_empty(sub1)
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        record = IdentityWriter(sub2).load()
        assert set(record.things_not_to_betray) == set(THINGS_NOT_TO_BETRAY_SEED)
        # And re-running seed on already-populated DB stays no-op.
        assert seed_identity_if_empty(sub2) is False
    finally:
        sub2.close()
