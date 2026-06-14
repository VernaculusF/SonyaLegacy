from __future__ import annotations

from dataclasses import dataclass, field
import math
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

    # Rates per tick.
    #
    # IMPORTANT: each rate must be > decay_rate, otherwise the counter is
    # net-negative on every tick (decay applied first, then accrual) and
    # never moves off zero. The 31.05 audit found all four drives pinned
    # at 0.00 in feed because decay (0.012) > all accruals (0.005-0.01).
    # Re-tuned so each baseline is net-positive at idle:
    #   boredom:    +0.012 - 0.006 = +0.006/tick → 0.7 in 117 ticks (~58min)
    #   curiosity:  +0.009 - 0.006 = +0.003/tick → 0.7 in 234 ticks (~117min)
    #   relational: +0.008 - 0.006 = +0.002/tick → 0.7 in 350 ticks (~175min)
    # pending_debt accrues only with active intentions; cap matches decay
    # so 1-2 intentions bleed off but 3+ slowly climb.
    # Re-tuned so they naturally decay. Curiosity spikes dynamically.
    boredom_rate: float = 0.004
    curiosity_rate: float = 0.003
    relational_rate: float = 0.003
    pending_debt_rate: float = 0.004
    pending_debt_cap_rate: float = 0.012

    threshold: float = 0.7
    max_value: float = 1.0
    decay_rate: float = 0.006

    # Re-emit cadence when a drive is pinned at max_value. Without this the
    # signal fires once on threshold crossing, then never again until the
    # drive falls below threshold AND climbs back through it. A drive that
    # sits at 1.0 (e.g. boredom after 8h of silence) silently saturates and
    # initiative pressure plateaus instead of escalating. Re-emit every
    # `_max_re_emit_ticks` (60 ticks ≈ 30min) so the loop hears the alarm
    # again, gated by quiet/initiative caps as usual.
    _max_re_emit_ticks: int = 60
    _ticks_since_max_emit: dict[str, int] = field(default_factory=dict)

    def tick(self, active_intentions_count: int = 0, unknowns_count: int = 0) -> list[str]:
        """Increment counters (with passive decay, clamped to [0, max_value]).
        Returns drives that crossed threshold this tick OR are pinned at max
        and re-emitting periodically."""
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
        if self._should_emit("boredom_analog", prev, self.boredom_analog, m):
            crossed.append("boredom_analog")

        prev = self.curiosity_analog
        # Logarithmic scaling for unknowns to prevent runaway curiosity spikes
        inc_curiosity = self.curiosity_rate + (0.01 * math.log1p(unknowns_count))
        self.curiosity_analog = min(m, self.curiosity_analog + inc_curiosity)
        if self._should_emit("curiosity_analog", prev, self.curiosity_analog, m):
            crossed.append("curiosity_analog")

        prev = self.relational_focus
        self.relational_focus = min(m, self.relational_focus + self.relational_rate)
        if self._should_emit("relational_focus", prev, self.relational_focus, m):
            crossed.append("relational_focus")

        if active_intentions_count > 0:
            prev = self.pending_debt
            inc = min(self.pending_debt_cap_rate,
                      self.pending_debt_rate * active_intentions_count)
            self.pending_debt = min(m, self.pending_debt + inc)
            if self._should_emit("pending_debt", prev, self.pending_debt, m):
                crossed.append("pending_debt")

        return crossed

    def _should_emit(self, drive: str, prev: float, cur: float, max_v: float) -> bool:
        """Decide whether THIS tick produces an emission for `drive`.

        Two cases:
          1. Threshold crossing: prev < threshold ≤ cur. Standard signal.
          2. Pinned at max: cur == max_v. Re-emits every
             `_max_re_emit_ticks` ticks. Counter survives across calls
             via `_ticks_since_max_emit[drive]`.

        When `cur` falls below max_v, the counter resets so the next pin
        starts a fresh re-emit window.
        """
        # Case 1: threshold crossing (legacy behaviour)
        if cur >= self.threshold and prev < self.threshold:
            self._ticks_since_max_emit[drive] = 0
            return True
        # Case 2: pinned at max_value — re-emit periodically
        if cur >= max_v - 1e-9:
            n = self._ticks_since_max_emit.get(drive, 0) + 1
            self._ticks_since_max_emit[drive] = n
            if n >= self._max_re_emit_ticks:
                self._ticks_since_max_emit[drive] = 0
                return True
            return False
        # Otherwise reset the max-tick counter so a new pin starts fresh
        self._ticks_since_max_emit[drive] = 0
        return False

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
        self.curiosity_analog = max(0.0, self.curiosity_analog - 0.3)

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
