"""Drives at max_value re-emit periodically — без этого initiative
теряет голос когда счётчик пинится на 1.0 (например boredom после
8 часов тишины)."""
from __future__ import annotations

from sonya.initiative.drives import DriveCounters


def test_initial_threshold_crossing_emits_once() -> None:
    dc = DriveCounters()
    dc.boredom_rate = 0.012  # Mock to overcome decay
    # decay -0.006 then accrual +0.012 = net +0.006/tick.
    # 0.700 -> after decay 0.694 -> after accrual 0.706.
    # prev (post-decay) = 0.694 < 0.7, cur = 0.706 ≥ 0.7 → crossing.
    dc.boredom_analog = 0.700
    crossed = dc.tick()
    assert "boredom_analog" in crossed


def test_no_re_emit_immediately_after_crossing() -> None:
    dc = DriveCounters()
    dc.boredom_rate = 0.012
    dc.boredom_analog = 0.700
    dc.tick()  # crossing
    crossed = dc.tick()  # next tick — already over threshold
    assert "boredom_analog" not in crossed


def test_pinned_at_max_re_emits_every_60_ticks() -> None:
    dc = DriveCounters()
    dc.boredom_rate = 0.012
    # Manually pin to max so we don't have to walk through 100+ ticks.
    dc.boredom_analog = dc.max_value
    # First N-1 ticks at max should NOT emit.
    for _ in range(dc._max_re_emit_ticks - 1):
        crossed = dc.tick()
        assert "boredom_analog" not in crossed
    # On the Nth tick, re-emit.
    crossed = dc.tick()
    assert "boredom_analog" in crossed


def test_re_emit_counter_resets_after_emit() -> None:
    dc = DriveCounters()
    dc.boredom_rate = 0.012
    dc.boredom_analog = dc.max_value
    for _ in range(dc._max_re_emit_ticks):
        dc.tick()  # one emission happens at the end
    # Next emission requires another full window.
    for _ in range(dc._max_re_emit_ticks - 1):
        crossed = dc.tick()
        assert "boredom_analog" not in crossed
    crossed = dc.tick()
    assert "boredom_analog" in crossed


def test_re_emit_counter_resets_when_falls_below_max() -> None:
    """When a pinned drive falls below max, its re-emit window restarts.

    Without this, a brief drop+climb wouldn't reset the cadence — so
    a drive that was at max for 50 ticks, dipped briefly, and climbed
    back would emit much sooner than 60 fresh ticks (carry-over).
    """
    dc = DriveCounters()
    dc.boredom_rate = 0.012
    dc.boredom_analog = dc.max_value
    # Run 50 ticks at max — well into the re-emit window but not yet emit.
    for _ in range(50):
        dc.tick()
    assert dc._ticks_since_max_emit["boredom_analog"] == 50
    # External event drops it below max — counter must reset.
    dc.on_external_message()
    assert dc.boredom_analog < dc.max_value
    # One tick below max should reset the counter.
    dc.tick()
    assert dc._ticks_since_max_emit["boredom_analog"] == 0


def test_independent_drives_have_independent_counters() -> None:
    dc = DriveCounters()
    dc.boredom_rate = 0.012
    dc.curiosity_rate = 0.009
    dc.boredom_analog = dc.max_value
    # curiosity: decay 0.006, accrual 0.009 = net +0.003/tick.
    # 0.700 → after decay 0.694 → after accrual 0.703 → crossing.
    dc.curiosity_analog = 0.700
    crossed = dc.tick()
    # curiosity crosses on this tick; boredom is at max but not at re-emit
    # cadence yet.
    assert "curiosity_analog" in crossed
    assert "boredom_analog" not in crossed
