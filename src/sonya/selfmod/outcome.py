"""Selfmod outcome tracking — did the change help?

After 24h watchdog confirms a proposal as stable, we record baseline metrics.
7 days later we re-measure and compare: improved / neutral / degraded.

Metrics:
  - error_count: internal.tool_error + internal.task_worker_error events
  - token_usage: sum of total_tokens from llm_calls

Substrate: selfmod_outcomes table (v16).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_errors_since(substrate: Substrate, since_iso: str) -> int:
    """Count error events in continuity since a given timestamp."""
    row = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events "
        "WHERE created_at >= ? AND kind IN "
        "('internal.tool_error', 'internal.task_worker_error')",
        (since_iso,),
    ).fetchone()
    return int(row[0]) if row else 0


def _count_tokens_since(substrate: Substrate, since_iso: str) -> int:
    """Sum total_tokens from llm_calls since a given timestamp."""
    row = substrate.connection.execute(
        "SELECT COALESCE(SUM(total_tokens), 0) FROM llm_calls WHERE timestamp >= ?",
        (since_iso,),
    ).fetchone()
    return int(row[0]) if row else 0


def record_baseline(substrate: Substrate, proposal_id: str, target_module: str) -> None:
    """Called when proposal transitions to CONFIRMED_STABLE.

    Records the error count and token usage for the PRIOR 7 days as baseline,
    and schedules the measure_at for 7 days from now.
    """
    now = datetime.now(timezone.utc)
    since_7d = (now - timedelta(days=7)).isoformat()
    measure_at = (now + timedelta(days=7)).isoformat()

    errors = _count_errors_since(substrate, since_7d)
    tokens = _count_tokens_since(substrate, since_7d)

    substrate.connection.execute(
        "INSERT OR REPLACE INTO selfmod_outcomes"
        "(proposal_id, target_module, confirmed_at, baseline_errors_7d, "
        "baseline_tokens_7d, measure_at, outcome) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
        (proposal_id, target_module, _utc_now_iso(), errors, tokens, measure_at),
    )
    substrate.connection.commit()


def check_pending_outcomes(substrate: Substrate) -> list[dict]:
    """Check if any pending outcomes are due for measurement.

    Called from internal_loop tick. Returns list of measured results.
    """
    now_iso = _utc_now_iso()
    rows = substrate.connection.execute(
        "SELECT proposal_id, target_module, confirmed_at, "
        "baseline_errors_7d, baseline_tokens_7d, measure_at "
        "FROM selfmod_outcomes WHERE outcome = 'pending' AND measure_at <= ?",
        (now_iso,),
    ).fetchall()

    results = []
    for row in rows:
        proposal_id = row[0]
        target_module = row[1]
        confirmed_at = row[2]
        baseline_errors = int(row[3])
        baseline_tokens = int(row[4])

        # Measure current 7-day window (from confirmed_at to now)
        current_errors = _count_errors_since(substrate, confirmed_at)
        current_tokens = _count_tokens_since(substrate, confirmed_at)

        # Determine outcome
        error_delta = current_errors - baseline_errors
        token_delta = current_tokens - baseline_tokens

        if error_delta < -5:
            outcome = "improved"
        elif error_delta > 20:
            outcome = "degraded"
        else:
            outcome = "neutral"

        # Record
        substrate.connection.execute(
            "UPDATE selfmod_outcomes SET "
            "measured_errors_7d = ?, measured_tokens_7d = ?, "
            "outcome = ?, measured_at = ? WHERE proposal_id = ?",
            (current_errors, current_tokens, outcome, now_iso, proposal_id),
        )
        substrate.connection.commit()

        results.append({
            "proposal_id": proposal_id,
            "target_module": target_module,
            "baseline_errors": baseline_errors,
            "measured_errors": current_errors,
            "outcome": outcome,
        })

    return results
