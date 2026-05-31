"""Tests for selfmod.outcomes — Sonya's self-improvement feedback loop."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state.substrate import Substrate
from sonya.tools.selfmod_tool import SelfModTool


@pytest.fixture()
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def _seed_outcome(sub, *, pid, target, outcome, base_err=0, meas_err=0,
                  base_tok=0, meas_tok=0, days_ago=0):
    confirmed_at = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat()
    measured_at = confirmed_at if outcome != "pending" else ""
    measure_at = (
        datetime.now(timezone.utc) + timedelta(days=7 - days_ago)
    ).isoformat() if outcome == "pending" else confirmed_at
    sub.connection.execute(
        "INSERT OR REPLACE INTO selfmod_outcomes "
        "(proposal_id, target_module, confirmed_at, baseline_errors_7d, "
        "baseline_tokens_7d, measure_at, measured_errors_7d, measured_tokens_7d, "
        "outcome, measured_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, target, confirmed_at, base_err, base_tok,
         measure_at, meas_err if outcome != "pending" else None,
         meas_tok if outcome != "pending" else None,
         outcome, measured_at),
    )
    # Also insert a matching proposal so .outcomes() can pull change_summary.
    sub.connection.execute(
        "INSERT OR IGNORE INTO self_mod_proposals"
        "(proposal_id, target_module, change_summary, diff_blob, "
        "proposed_by_principal_id, status, created_at, updated_at) "
        "VALUES (?, ?, ?, '', 'system', 'applied', ?, ?)",
        (pid, target, f"summary for {pid}", confirmed_at, confirmed_at),
    )
    sub.connection.commit()


def test_outcomes_empty_returns_zero_count(substrate: Substrate) -> None:
    tool = SelfModTool(substrate)
    out = json.loads(tool.outcomes(""))
    assert out["status"] == "ok"
    assert out["count"] == 0
    assert out["counters"] == {"improved": 0, "neutral": 0, "degraded": 0, "pending": 0}


def test_outcomes_all_buckets(substrate: Substrate) -> None:
    _seed_outcome(substrate, pid="smod-aaa", target="src/m1.py",
                  outcome="improved", base_err=10, meas_err=2)
    _seed_outcome(substrate, pid="smod-bbb", target="src/m2.py",
                  outcome="degraded", base_err=2, meas_err=30)
    _seed_outcome(substrate, pid="smod-ccc", target="src/m3.py",
                  outcome="neutral", base_err=5, meas_err=6)
    _seed_outcome(substrate, pid="smod-ddd", target="src/m4.py",
                  outcome="pending")
    tool = SelfModTool(substrate)
    out = json.loads(tool.outcomes(""))
    assert out["status"] == "ok"
    assert out["count"] == 4
    assert out["counters"]["improved"] == 1
    assert out["counters"]["degraded"] == 1
    assert out["counters"]["neutral"] == 1
    assert out["counters"]["pending"] == 1
    # Each outcome carries its key fields.
    by_pid = {it["proposal_id"]: it for it in out["outcomes"]}
    assert by_pid["smod-aaa"]["delta_errors"] == -8
    assert by_pid["smod-bbb"]["delta_errors"] == 28
    assert by_pid["smod-ccc"]["delta_errors"] == 1
    assert "delta_errors" not in by_pid["smod-ddd"]
    assert by_pid["smod-ddd"]["measure_at"]
    # change_summary surfaced from proposal store.
    for it in out["outcomes"]:
        assert it["summary"].startswith("summary for")


def test_outcomes_filter_bucket(substrate: Substrate) -> None:
    _seed_outcome(substrate, pid="smod-imp", target="m.py",
                  outcome="improved", base_err=10, meas_err=1)
    _seed_outcome(substrate, pid="smod-deg", target="m.py",
                  outcome="degraded", base_err=1, meas_err=20)
    tool = SelfModTool(substrate)
    out = json.loads(tool.outcomes("improved"))
    assert out["count"] == 1
    assert out["outcomes"][0]["proposal_id"] == "smod-imp"
    assert out["filter"] == "improved"


def test_outcomes_filter_invalid(substrate: Substrate) -> None:
    tool = SelfModTool(substrate)
    out = json.loads(tool.outcomes("notabucket"))
    assert out["status"] == "error"
    assert "limit" in out["reason"] or "bucket" in out["reason"] or "pending" in out["reason"]


def test_outcomes_integer_limit(substrate: Substrate) -> None:
    for i in range(5):
        _seed_outcome(
            substrate, pid=f"smod-{i:03d}", target="m.py",
            outcome="improved", base_err=10, meas_err=1, days_ago=i,
        )
    tool = SelfModTool(substrate)
    out = json.loads(tool.outcomes("3"))
    assert out["count"] == 3


def test_outcomes_sorted_newest_first(substrate: Substrate) -> None:
    _seed_outcome(substrate, pid="smod-old", target="m.py",
                  outcome="improved", base_err=1, meas_err=0, days_ago=10)
    _seed_outcome(substrate, pid="smod-new", target="m.py",
                  outcome="improved", base_err=1, meas_err=0, days_ago=1)
    tool = SelfModTool(substrate)
    out = json.loads(tool.outcomes(""))
    assert out["outcomes"][0]["proposal_id"] == "smod-new"
    assert out["outcomes"][1]["proposal_id"] == "smod-old"
