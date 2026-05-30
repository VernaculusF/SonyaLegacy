"""Verify BrowserTool handles being called from inside an asyncio loop.

Sync_playwright().start() refuses to run when there's a running event loop
in the current thread (it bails with SyncPlaywrightError). agent_session
runs tools INSIDE an async loop, so without thread-pool offloading, every
browser.* call would crash.

Test: simulate "called from async context" by checking BrowserTool routes
the call through its dedicated executor (the worker thread has no loop).
"""
from __future__ import annotations

import asyncio
import threading

import pytest

from sonya.tools.browser_tool import BrowserTool


def test_browser_open_returns_error_string_not_crash_when_playwright_missing(monkeypatch):
    """Even without playwright installed, BrowserTool.open returns a
    deterministic [ERROR] string — never a Python exception."""
    bt = BrowserTool()
    # Force the lazy import to fail by patching builtins.__import__ for
    # 'playwright.sync_api'.
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api" or name.startswith("playwright"):
            raise ImportError("simulated missing playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = bt.open("https://example.com")
    assert out.startswith("[ERROR]"), out
    assert "Playwright не установлен" in out or "ImportError" in out


def test_browser_close_safe_to_call_when_never_opened():
    bt = BrowserTool()
    out = bt.close()
    assert "[OK]" in out


async def _async_call(bt, method, *args):
    """Helper — call browser method while we're inside an async loop."""
    return method(*args)


def test_browser_call_inside_running_loop_does_not_crash():
    """BrowserTool methods are sync, but they can be invoked from inside
    a running event loop (which is what agent_session does). The thread
    pool inside BrowserTool sidesteps the sync_playwright-loop-detection
    panic. We can't actually launch chromium in CI, but we CAN verify
    the call doesn't raise — it should return a deterministic [ERROR]
    string from the executor.
    """
    bt = BrowserTool()
    # Simulate agent_session: an async loop is running, sync tool is called
    # synchronously from a coroutine.
    async def driver():
        # The call may succeed (chromium present) or return [ERROR]
        # (chromium missing in CI). Either way it must NOT raise.
        return bt.open("https://example.com")

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(driver())
    finally:
        loop.close()
    assert isinstance(result, str)
    # Always cleanup
    bt.close()


def test_browser_executor_is_single_threaded():
    """All browser ops must serialise through one worker thread to keep
    the persistent context consistent."""
    bt = BrowserTool()
    seen_threads: set[int] = set()

    def fake_op() -> str:
        seen_threads.add(threading.get_ident())
        return "[OK] fake"

    # Run 5 sequential ops — they should all land on the same thread.
    for _ in range(5):
        bt._run(fake_op)
    assert len(seen_threads) == 1
