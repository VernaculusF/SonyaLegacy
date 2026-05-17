from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class DriveCounters:
    """Internal drive analogs that accumulate over time and trigger initiative.

    These are NOT emotions. They are functional analogs of internal pressures
    that motivate action. See SYSTEM_CORE §7.20.

    Counters increment by rules, decrement on relevant events.
    Threshold crossing → InitiativeSignal.
    """

    boredom_analog: float = 0.0
    curiosity_analog: float = 0.0
    relational_focus: float = 0.0
    pending_debt: float = 0.0

    # Rates per tick
    boredom_rate: float = 0.01
    curiosity_rate: float = 0.005
    relational_rate: float = 0.003
    pending_debt_rate: float = 0.02  # rate per active intention per tick

    threshold: float = 0.7

    def tick(self, active_intentions_count: int = 0) -> list[str]:
        """Increment counters. Returns list of drives that crossed threshold."""
        crossed: list[str] = []

        prev = self.boredom_analog
        self.boredom_analog += self.boredom_rate
        if self.boredom_analog >= self.threshold and prev < self.threshold:
            crossed.append("boredom_analog")

        prev = self.curiosity_analog
        self.curiosity_analog += self.curiosity_rate
        if self.curiosity_analog >= self.threshold and prev < self.threshold:
            crossed.append("curiosity_analog")

        prev = self.relational_focus
        self.relational_focus += self.relational_rate
        if self.relational_focus >= self.threshold and prev < self.threshold:
            crossed.append("relational_focus")

        if active_intentions_count > 0:
            prev = self.pending_debt
            self.pending_debt += self.pending_debt_rate * active_intentions_count
            if self.pending_debt >= self.threshold and prev < self.threshold:
                crossed.append("pending_debt")

        return crossed

    def reset(self, drive: str) -> None:
        if hasattr(self, drive):
            setattr(self, drive, 0.0)

    def on_external_message(self) -> None:
        """Decrement on incoming message from principal."""
        self.boredom_analog = max(0.0, self.boredom_analog - 0.3)
        self.relational_focus = max(0.0, self.relational_focus - 0.2)

    def on_action_completed(self) -> None:
        """Decrement on successful action."""
        self.pending_debt = max(0.0, self.pending_debt - 0.3)
        self.curiosity_analog = max(0.0, self.curiosity_analog - 0.1)

    def to_dict(self) -> dict[str, float]:
        return {
            "boredom_analog": self.boredom_analog,
            "curiosity_analog": self.curiosity_analog,
            "relational_focus": self.relational_focus,
            "pending_debt": self.pending_debt,
        }
