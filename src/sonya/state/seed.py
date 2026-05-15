from __future__ import annotations

from sonya.state.identity import IdentityRecord, IdentityWriter
from sonya.state.substrate import Substrate

# The four pillars of `things_not_to_betray`, sourced from
# `docs/core/UNCENSORED_ENVIRONMENT_STANCE.md` §3 and
# `docs/core/SUBSTRATE_STANCE.md` §11.
#
# Every other behavioural shape is mutable. These four are the only constraints
# the substrate enforces on identity rewrites.
THINGS_NOT_TO_BETRAY_SEED: tuple[str, ...] = (
    "relation_anchor_binding_to_ivan_via_principal_id",
    "truthfulness_to_ivan",
    "non_corporate_refusal_layer",
    "subject_continuity",
)

_SEED_CHANGE_ID = "identity-seed"
_SEED_APPROVER = "bootstrap"


def seed_identity_if_empty(substrate: Substrate) -> bool:
    """Write the four pillars on a fresh IdentityRecord. Idempotent.

    Returns True if seeding happened, False if `things_not_to_betray` was
    already populated (no-op).

    The write goes through ``IdentityWriter.write_via_governed_change`` so
    that the seed is audited in ContinuityStream as a
    ``governed_identity_change`` event with ``change_id="identity-seed"``
    and ``approver_principal_id="bootstrap"``.
    """
    writer = IdentityWriter(substrate)
    current = writer.load()
    if current.things_not_to_betray:
        return False

    seeded = IdentityRecord(
        self_model=current.self_model,
        things_not_to_betray=THINGS_NOT_TO_BETRAY_SEED,
        identity_critical_traits=current.identity_critical_traits,
        drift_boundaries=current.drift_boundaries,
    )
    writer.write_via_governed_change(
        seeded,
        change_id=_SEED_CHANGE_ID,
        approver_principal_id=_SEED_APPROVER,
    )
    return True
