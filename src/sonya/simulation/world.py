from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """Ingest contract: event from simulation world to Sonya.

    Stub — real simulation (MetaWorm/PyBullet) is post-MVP Track D.
    See: SIMULATION_AND_EMBODIMENT_PLAN §10.
    """

    event_type: str  # spike, collision, state_change
    source_sensor: str = ""
    value: float = 0.0
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorldAction:
    """Emission contract: action from Sonya to simulation world.

    Stub — real motor commands (MOVE, FACIAL, SPEAK) are post-MVP Track D.
    See: SIMULATION_AND_EMBODIMENT_PLAN §11.
    """

    action_type: str  # move, speak, facial_expression
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
