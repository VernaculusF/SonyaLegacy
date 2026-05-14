from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import (
    IdentityRecord,
    IdentityWriter,
    ImmutableFieldError,
    RelationAnchorBinding,
    Substrate,
)


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_identity_record_default_when_empty(substrate: Substrate) -> None:
    writer = IdentityWriter(substrate)
    record = writer.load()
    assert record.self_model == {}
    assert record.things_not_to_betray == ()
    assert record.identity_critical_traits == ()


def test_identity_round_trip_for_mutable_fields(substrate: Substrate) -> None:
    writer = IdentityWriter(substrate)
    writer.write_mutable(
        IdentityRecord(
            self_model={"voice": "warm"},
            drift_boundaries={"max_persona_shift": "low"},
        )
    )
    loaded = writer.load()
    assert loaded.self_model == {"voice": "warm"}
    assert loaded.drift_boundaries == {"max_persona_shift": "low"}


def test_writing_to_things_not_to_betray_via_runtime_api_raises(
    substrate: Substrate,
) -> None:
    writer = IdentityWriter(substrate)
    with pytest.raises(ImmutableFieldError):
        writer.write_mutable(
            IdentityRecord(things_not_to_betray=("relation_anchor_binding_to_ivan",))
        )


def test_writing_immutable_fields_via_governed_change_succeeds(
    substrate: Substrate,
) -> None:
    writer = IdentityWriter(substrate)
    writer.write_via_governed_change(
        IdentityRecord(
            things_not_to_betray=("relation_anchor_binding_to_ivan",),
            identity_critical_traits=("subject_continuity",),
        ),
        change_id="change-001",
        approver_principal_id="ivan-anchor",
    )
    loaded = writer.load()
    assert loaded.things_not_to_betray == ("relation_anchor_binding_to_ivan",)
    assert loaded.identity_critical_traits == ("subject_continuity",)


def test_governed_change_appends_to_continuity(substrate: Substrate) -> None:
    from sonya.state import ContinuityStream

    writer = IdentityWriter(substrate)
    writer.write_via_governed_change(
        IdentityRecord(things_not_to_betray=("x",)),
        change_id="change-002",
        approver_principal_id="ivan-anchor",
    )
    events = list(ContinuityStream(substrate).read_since(0))
    assert any(ev.kind == "governed_identity_change" for ev in events)
    governed = next(ev for ev in events if ev.kind == "governed_identity_change")
    assert governed.payload["change_id"] == "change-002"
    assert governed.payload["approver_principal_id"] == "ivan-anchor"


def test_relation_anchor_binding_round_trip(substrate: Substrate) -> None:
    writer = IdentityWriter(substrate)
    binding = RelationAnchorBinding(
        principal_id="ivan",
        trusted_identifiers=("telegram:5785127604",),
        trust_evidence={"channel_history": "stable"},
        authority_scope=("approve_immutable_change",),
        channel_constraints={"telegram": "private_chat_only"},
        is_primary=True,
    )
    writer.write_via_governed_change_relation_anchor(
        binding,
        change_id="anchor-bind-001",
        approver_principal_id="ivan-anchor",
    )
    loaded = writer.load_relation_anchor("ivan")
    assert loaded == binding
