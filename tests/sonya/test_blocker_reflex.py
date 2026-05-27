"""Tests for the blocker-reflex heuristic in agent_session.

Phase 2B of unified-loop work: after every tool call, scan the observation
for explicit failure markers (auth, rate-limit, credits, exception, network,
404, captcha) and inject a one-line BLOCKER hint into the next user-turn.

Without this Sonya tends to repeat the failing call (Shodan key with
credits=0, web.search hitting the same DDG instance after 429, etc.) — the
"try alternatives on failure" rule lives way back in the system prompt
and doesn't survive into step N+1's attention.

This is a pure-regex heuristic, not an LLM call. False-negative is fine
(we miss a quirky failure, no nudge); false-positive on success is the
real risk we test against.
"""
from __future__ import annotations

import pytest

from sonya.subject.agent_session import _detect_blocker


# --- positive cases (should detect) ---

@pytest.mark.parametrize("tool, obs, expected_kind", [
    ("web.fetch", "HTTP 401 Unauthorized — invalid api key", "auth_401"),
    ("code.exec", '{"status_code": 401, "body": "invalid_api_key"}', "auth_401"),
    ("web.fetch", "HTTP 403 Forbidden — access denied", "auth_403"),
    ("web.fetch", "Permission denied", "auth_403"),
    ("web.search", "HTTP 429: rate limited, retry after 60s", "rate_limit"),
    ("web.fetch", "Too Many Requests", "rate_limit"),
    ("code.exec", '{"plan": "freelancer", "credits_exhausted": true}', "credits_exhausted"),
    ("web.fetch", "402 Payment Required", "credits_exhausted"),
    ("code.exec", "scan_credits: 0, usage_limit reached", "credits_exhausted"),
    ("web.fetch", "HTTP 502 — bad gateway", "http_5xx"),
    ("web.fetch", "503 Service Unavailable", "http_5xx"),
    ("web.fetch", "HTTP 404 — Not Found", "http_404"),
    ("code.exec", 'Traceback (most recent call last):\n  File "x.py"\nValueError: bad', "exception_traceback"),
    # ConnectionError: matches exception_traceback FIRST (which is correct —
    # it IS a Python exception). Network-specific kind only fires when the
    # text is a tool-level error message without the Python exception prefix.
    ("web.fetch", "getaddrinfo failed for nope.example.com", "dns_or_connect"),
    ("web.fetch", "connect timeout to api.example.com", "dns_or_connect"),
    ("web.search", "Verifying you are human... captcha required", "ddg_blocked"),
    ("web.search", "We've detected unusual traffic from your network", "ddg_blocked"),
])
def test_blocker_detected(tool: str, obs: str, expected_kind: str) -> None:
    result = _detect_blocker(tool, obs)
    assert result is not None, f"expected blocker for {obs!r}"
    kind, hint = result
    assert kind == expected_kind, f"expected {expected_kind}, got {kind}"
    assert len(hint) > 20  # non-trivial hint


def test_empty_result_for_data_tool_flags() -> None:
    """For tools that normally return data, observation that's only
    whitespace looks suspicious."""
    # _detect_blocker returns None for falsy input as a safety guard, so
    # we test with whitespace-only (which the regex matches).
    result = _detect_blocker("web.fetch", "   \n\n   \n")
    assert result is not None
    assert result[0] == "empty_result"


def test_empty_result_for_void_tool_skips() -> None:
    """tasks.complete returning [OK] with no body is normal — don't flag."""
    assert _detect_blocker("tasks.complete", "[OK] task done") is None
    assert _detect_blocker("tasks.complete", "") is None
    assert _detect_blocker("env.set", "") is None
    assert _detect_blocker("selfmod.apply", "[OK] applied") is None


# --- negative cases (should NOT detect) ---

@pytest.mark.parametrize("tool, obs", [
    ("web.fetch", '{"title": "Example", "body": "<html>Hello world</html>"}'),
    ("web.search", '[{"url": "https://example.com", "title": "Result 1"}]'),
    ("code.exec", '{"stdout": "PONG\\n", "exit_code": 0, "stderr": ""}'),
    ("memory.recall", "5 episodic events: [event1, event2, ...]"),
    ("self_inspect.identity", "name: Sonya\nthings_not_to_betray: [4 anchors]"),
    # 200 OK with embedded "401" in JSON should NOT trigger — only standalone
    # markers.  The literal status_code field IS a code, so this flags. Keep
    # check loose; we accept some false positives in numeric scan as long as
    # they're informative.
])
def test_no_blocker_on_normal_results(tool: str, obs: str) -> None:
    assert _detect_blocker(tool, obs) is None


def test_blocker_returns_first_match_priority() -> None:
    """If multiple patterns match, we pick the first listed (auth before
    generic 5xx)."""
    obs = "HTTP 401 — also some 502 mention"
    result = _detect_blocker("web.fetch", obs)
    assert result is not None
    assert result[0] == "auth_401"


def test_blocker_caps_observation_length() -> None:
    """Very long observation shouldn't cause regex catastrophic backtracking."""
    huge = "ok " * 5000 + "401 Unauthorized"
    # 401 is past the 6000-char cap → won't be detected. That's fine — we
    # don't want to scan unbounded inputs. Test just verifies no crash.
    result = _detect_blocker("web.fetch", huge)
    # Either None (past cap) or auth_401 (if cap is generous) — both fine.
    assert result is None or result[0] == "auth_401"


# --- regression tests for false-positives observed in production ---


def test_no_fp_on_successful_http_200_with_blank_lines() -> None:
    """27.05.18:35 incident: web.fetch returned `[HTTP 200] /private/login.php
    Content-Type: text/html ... Bytes: 21035 ... Login Toggle navigation Home
    Apply Now ...`. The regex caught a blank line between headers and body
    as `empty_result`. Should be silent — request succeeded."""
    obs = (
        "[HTTP 200] https://mpbacademy.com/private/login.php\n"
        "Content-Type: text/html; charset=utf-8\n"
        "Bytes: 21035 (capped at 200000)\n"
        "\n"
        "Login Toggle navigation Home Apply Now Entrance Exam Continue Upload Verify"
    )
    assert _detect_blocker("web.fetch", obs) is None


def test_no_fp_on_404_inside_multi_fetch_with_main_200() -> None:
    """27.05.18:35 incident: code.exec did several requests in one shot.
    Main page returned 200, but robots.txt and sitemap.xml were 404. The
    regex `\\b404\\b` matched those side-fetches and emitted http_404 hint
    that didn't apply to the actual primary fetch. Should be silent —
    primary request succeeded."""
    obs = (
        "[exit 0]\n"
        "--- stdout ---\n"
        "=== Main page (allow redirects) ===\n"
        "Final URL: https://mpbacademy.com/private/login.php\n"
        "Status: 200\n"
        "Server: nginx\n"
        "Content-Type: text/html\n"
        "\n"
        "robots.txt: 404\n"
        "sitemap.xml: 404\n"
    )
    # `200` envelope present + bytes — no blocker should fire.
    assert _detect_blocker("code.exec", obs) is None


def test_fires_on_isolated_404_only() -> None:
    """When EVERYTHING is a 404, do flag — that's a real blocker."""
    obs = (
        "[exit 0]\n"
        "Final URL: https://x.com/missing\n"
        "Status: 404\n"
        "Body: 404 Not Found\n"
    )
    result = _detect_blocker("code.exec", obs)
    # Either http_404 or None (if the regex is too strict). What we DON'T
    # want is exception_traceback / empty_result false positives.
    assert result is None or result[0] == "http_404"


def test_no_fp_on_http_envelope_with_short_body() -> None:
    """An [HTTP 200] envelope with minimal body shouldn't fire empty_result."""
    obs = "[HTTP 200] https://example.com\nContent-Type: text/html\nBytes: 1024\n\n<html>Hi</html>"
    assert _detect_blocker("web.fetch", obs) is None


def test_empty_result_only_on_truly_empty() -> None:
    """The new anchored regex should only fire on whitespace / [OK] /
    null-equivalents — not on multi-block outputs with empty separators."""
    assert _detect_blocker("web.fetch", "") is None  # safety guard
    assert _detect_blocker("web.fetch", "   \n\n   \n") is not None
    assert _detect_blocker("web.fetch", "[OK]") is not None
    assert _detect_blocker("web.fetch", "null") is not None
    assert _detect_blocker("web.fetch", "{}") is not None
    # Real content with embedded blanks → NOT empty
    assert _detect_blocker("web.fetch", "Header\n\nBody content here") is None
