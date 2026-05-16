from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EmbodimentEvent:
    """Abstract embodiment event from virtual or physical body.

    Stub — real integration with SNN/Loihi/ESP32 is post-MVP Track D.
    See: SIMULATION_AND_EMBODIMENT_PLAN §10-11.
    """

    event_type: str  # pain, touch, temperature, hunger, tiredness
    source: str = ""  # body part or sensor id
    intensity: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VirtualBodyCounter:
    """Virtual body drive counter — stub for future physical body signals.

    These feed into DriveCounters (Phase 6) as additional trigger sources.
    Real body integration — post-MVP Track D.
    """

    hunger_analog: float = 0.0
    tiredness_analog: float = 0.0
    arousal_analog: float = 0.0
    touch_need: float = 0.0
    closeness_need: float = 0.0

    def tick(self) -> dict[str, float]:
        """Increment all counters. Returns current state."""
        self.hunger_analog += 0.001
        self.tiredness_analog += 0.0005
        self.touch_need += 0.002
        self.closeness_need += 0.003
        return self.to_dict()

    def on_interaction(self) -> None:
        """Decrement on meaningful interaction."""
        self.closeness_need = max(0.0, self.closeness_need - 0.2)
        self.touch_need = max(0.0, self.touch_need - 0.1)

    def to_dict(self) -> dict[str, float]:
        return {
            "hunger_analog": self.hunger_analog,
            "tiredness_analog": self.tiredness_analog,
            "arousal_analog": self.arousal_analog,
            "touch_need": self.touch_need,
            "closeness_need": self.closeness_need,
        }
