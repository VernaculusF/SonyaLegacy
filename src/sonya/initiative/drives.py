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
    max_value: float = 1.0  # drives are bounded analogs, never exceed this
    # Passive decay per tick — drives relax toward 0 over time (homeostasis),
    # so they "breathe" instead of pinning at max. Must be >= accumulation
    # rate for boredom/curiosity/relational so an idle Sonya doesn't pin every
    # drive at 1.0 (the "all drives maxed" bug). Net effect: drives rise toward
    # threshold then oscillate, and fully relax when nothing is accumulating.
    decay_rate: float = 0.012

    def tick(self, active_intentions_count: int = 0) -> list[str]:
        """Increment counters (with passive decay, clamped to [0, max_value]).
        Returns drives that crossed threshold this tick."""
        crossed: list[str] = []
        m = self.max_value
        d = self.decay_rate

        # passive relaxation toward 0
        self.boredom_analog = max(0.0, self.boredom_analog - d)
        self.curiosity_analog = max(0.0, self.curiosity_analog - d)
        self.relational_focus = max(0.0, self.relational_focus - d)
        self.pending_debt = max(0.0, self.pending_debt - d)

        prev = self.boredom_analog
        self.boredom_analog = min(m, self.boredom_analog + self.boredom_rate)
        if self.boredom_analog >= self.threshold and prev < self.threshold:
            crossed.append("boredom_analog")

        prev = self.curiosity_analog
        self.curiosity_analog = min(m, self.curiosity_analog + self.curiosity_rate)
        if self.curiosity_analog >= self.threshold and prev < self.threshold:
            crossed.append("curiosity_analog")

        prev = self.relational_focus
        self.relational_focus = min(m, self.relational_focus + self.relational_rate)
        if self.relational_focus >= self.threshold and prev < self.threshold:
            crossed.append("relational_focus")

        if active_intentions_count > 0:
            prev = self.pending_debt
            self.pending_debt = min(
                m, self.pending_debt + self.pending_debt_rate * active_intentions_count
            )
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

    # --- persistence (substrate v16) ---

    def save(self, substrate) -> None:
        """Persist current drive state to substrate. Called every N ticks."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        substrate.connection.execute(
            "INSERT INTO drive_state(id, boredom_analog, curiosity_analog, "
            "relational_focus, pending_debt, updated_at) "
            "VALUES (1, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET "
            "boredom_analog=excluded.boredom_analog, "
            "curiosity_analog=excluded.curiosity_analog, "
            "relational_focus=excluded.relational_focus, "
            "pending_debt=excluded.pending_debt, "
            "updated_at=excluded.updated_at",
            (self.boredom_analog, self.curiosity_analog,
             self.relational_focus, self.pending_debt, now),
        )
        substrate.connection.commit()

    @classmethod
    def load(cls, substrate) -> "DriveCounters":
        """Load persisted drive state from substrate. Returns fresh if empty.

        Values are clamped to [0, max_value] on load — older builds let drives
        accumulate unbounded (pending_debt ran to 5-digit values), so we heal
        any runaway state here.
        """
        row = substrate.connection.execute(
            "SELECT boredom_analog, curiosity_analog, relational_focus, pending_debt "
            "FROM drive_state WHERE id = 1"
        ).fetchone()
        dc = cls()
        if row is not None:
            m = dc.max_value
            dc.boredom_analog = max(0.0, min(m, float(row[0])))
            dc.curiosity_analog = max(0.0, min(m, float(row[1])))
            dc.relational_focus = max(0.0, min(m, float(row[2])))
            dc.pending_debt = max(0.0, min(m, float(row[3])))
        return dc
