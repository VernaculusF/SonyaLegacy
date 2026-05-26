"""Tests for GapDetector fingerprint-based deduplication.

Production observation (26.05): GapDetector created 20 capability_gaps,
all identical "web.fetch DNSError on search.bus-hit.me/" — same SearXNG
mirror failing every retry. Each gap also became a pending_intention.
Result: 20 noise items in Sonya's context, no actionable signal.

Fix: scan_recent reconstructs fingerprints of currently-open gaps from
their descriptions and refuses to insert duplicates. Fingerprint =
"{tool}|{error_type}|{host}" for tool-error payloads.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.skills.gap_detector import GapDetector
from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def _seed_tool_error(stream: ContinuityStream, tool: str, arg: str, err: str) -> None:
    stream.append(ContinuityEvent(
        kind="some.failure_kind",  # arbitrary; gap_detector triggers on payload contents
        payload={
            "tool": tool,
            "arg": arg,
            "error_type": err,
            "error_message": "failed_action description here",
        },
    ))


def test_dedup_same_tool_same_host_same_error(substrate: Substrate) -> None:
    """20 identical DNS errors on same URL → only 1 gap created."""
    stream = ContinuityStream(substrate)
    detector = GapDetector(substrate, stream)
    for _ in range(20):
        _seed_tool_error(
            stream,
            tool="web.fetch",
            arg="https://search.bus-hit.me/",
            err="ClientConnectorDNSError",
        )
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 1


def test_different_hosts_create_separate_gaps(substrate: Substrate) -> None:
    """Same tool + error type but different hosts → distinct gaps."""
    stream = ContinuityStream(substrate)
    detector = GapDetector(substrate, stream)
    for host in ("search.bus-hit.me", "searx.example.com", "ddg.example.org"):
        _seed_tool_error(
            stream,
            tool="web.fetch",
            arg=f"https://{host}/",
            err="ClientConnectorDNSError",
        )
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 3


def test_different_error_types_create_separate_gaps(substrate: Substrate) -> None:
    """Same tool + host but different error types → distinct gaps."""
    stream = ContinuityStream(substrate)
    detector = GapDetector(substrate, stream)
    _seed_tool_error(stream, "web.fetch", "https://x.com/", "DNSError")
    _seed_tool_error(stream, "web.fetch", "https://x.com/", "TimeoutError")
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 2


def test_dedup_persists_across_scan_calls(substrate: Substrate) -> None:
    """First scan creates gap; second scan with same signal must not
    duplicate even though signal events are new."""
    stream = ContinuityStream(substrate)
    detector = GapDetector(substrate, stream)
    _seed_tool_error(stream, "web.fetch", "https://x.com/", "DNSError")
    cursor1 = stream.latest_seq()
    gaps1 = detector.scan_recent(since_seq=0)
    assert len(gaps1) == 1

    # Same error keeps happening
    for _ in range(5):
        _seed_tool_error(stream, "web.fetch", "https://x.com/", "DNSError")
    gaps2 = detector.scan_recent(since_seq=cursor1)
    assert len(gaps2) == 0  # all dedup'd


def test_url_paths_collapse_to_host(substrate: Substrate) -> None:
    """Different paths on same host fold to one gap (host-level fingerprint)."""
    stream = ContinuityStream(substrate)
    detector = GapDetector(substrate, stream)
    for path in ("/", "/foo", "/bar/baz", "/api/v1/x"):
        _seed_tool_error(
            stream,
            tool="web.fetch",
            arg=f"https://x.com{path}",
            err="DNSError",
        )
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 1
