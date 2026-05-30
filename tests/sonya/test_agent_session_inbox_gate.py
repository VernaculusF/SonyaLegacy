"""Inbox priority gate — Sonya can't [DONE] without chat.dialog reply.

Regression for the 30.05 silent-no-reply bug: active session was triggered
by an atrium dialog message; Sonya called body.expression and immediately
[DONE], leaving Ivan with no text reply. The gate forces chat.dialog before
[DONE] when the session was opened on a real Ivan message
(`require_dialog_reply=True`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate
from sonya.subject.agent_session import run_agent_session
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool


class _Stub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.calls += 1
        if not self._responses:
            return "[DONE]"
        return self._responses.pop(0)


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


async def test_done_blocked_when_dialog_reply_required(substrate: Substrate) -> None:
    """If the session opened on a real Ivan message, [DONE] without
    chat.dialog must be refused and the model nudged to reply."""
    stream = ContinuityStream(substrate)

    # First turn: model tries to close without replying. Gate must block.
    # Second turn: model still tries. Gate blocks again.
    # Third turn: model finally writes a [DONE] (would normally close, but
    # again gate blocks because no chat.dialog ever fired).
    # We're not driving chat.dialog here — that needs the outbound machinery.
    # Just verify the gate triggered at least once.
    provider = _Stub([
        "[DONE: тихо смотрю]",
        "[DONE: всё ещё тихо]",
        "[DONE: ну хватит]",
        "[DONE: финал]",
    ])

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="Привет, отзовись",
        require_dialog_reply=True,
        max_steps=4,
        max_seconds=10.0,
        purpose="test",
    )

    # Find inbox_priority_gate audit events.
    gate_events = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events WHERE kind = 'internal.inbox_priority_gate'"
    ).fetchone()[0]
    assert gate_events >= 1, "gate must have blocked at least one [DONE]"
    # The session should have hit the step cap (no chat.dialog tool, no
    # break path). budget_exceeded covers the case where time ran out;
    # otherwise we expect at least N gate events.
    assert provider.calls >= 2, "model should have been re-prompted"


async def test_done_blocked_after_work_without_followup_dialog(substrate: Substrate, monkeypatch) -> None:
    """Phase 2 of inbox gate: even if она ответила первый раз, после
    реальной работы (web.fetch / browser / etc.) должен быть второй
    chat.dialog с отчётом перед [DONE].

    Regression for 31.05 silent-no-result bug: Соня писала "Привет, иду"
    → делала browser.open/text/close → [DONE] без второго chat.dialog.
    Ivan видел только приветствие, результат пропадал.
    """
    stream = ContinuityStream(substrate)

    # Stub call_outbound_sync so chat.tell_ivan returns success without
    # needing the full OutboundGate scaffolding.
    import sonya.subject.agent_session as agent_session_mod

    def _fake_call_outbound_sync(_gate, text, **kw):
        return f"[OK] dialog: {text[:40]}"

    # The handler uses a local import; we patch the module
    # `sonya.initiative.outbound.call_outbound_sync` — that's where the
    # `from sonya.initiative.outbound import call_outbound_sync` resolves.
    import sonya.initiative.outbound as outbound_mod
    monkeypatch.setattr(
        outbound_mod, "call_outbound_sync", _fake_call_outbound_sync,
    )

    # Sequence:
    #  1. [TOOL: chat.tell_ivan привет, начинаю]   → phase 1 lifted (ack)
    #  2. [TOOL: web.fetch https://example.com]    → work done, phase 2 set
    #  3. [DONE: вот результат]                    → MUST be blocked (phase 2)
    #  4. [DONE: ну ладно]                         → still blocked
    provider = _Stub([
        "Принято.\n[TOOL: chat.tell_ivan]\nпривет, начинаю",
        "Получаю данные.\n[TOOL: web.fetch https://example.com]",
        "Готово.\n[DONE: всё ок]",
        "Опять.\n[DONE: точно всё ок]",
    ])

    from sonya.tools.web_tool import WebTool

    # Sentinel outbound — handler only checks `is None`. Any non-None object works.
    fake_outbound = object()

    await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        web=WebTool(),
        outbound=fake_outbound,
        system_prompt="test",
        initial_user_text="Соня, открой example.com и расскажи что там.",
        require_dialog_reply=True,
        max_steps=6,
        max_seconds=10.0,
        purpose="test",
    )

    rows = substrate.connection.execute(
        "SELECT payload_json FROM continuity_events "
        "WHERE kind = 'internal.inbox_priority_gate' "
        "  AND payload_json LIKE '%must_report_results%'"
    ).fetchall()
    assert len(rows) >= 1, (
        "phase-2 gate must trigger when [DONE] follows work tools "
        "without a follow-up chat.dialog"
    )


async def test_done_allowed_without_dialog_reply_required(substrate: Substrate) -> None:
    """When the caller doesn't set require_dialog_reply, [DONE] closes
    immediately as before — internal sessions keep their old semantics."""
    stream = ContinuityStream(substrate)
    provider = _Stub([
        "[DONE: всё, я закончила]",
    ])

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="seed",  # provided but require_dialog_reply NOT set
        require_dialog_reply=False,
        max_steps=4,
        max_seconds=10.0,
        purpose="test",
    )

    assert provider.calls == 1
    assert "закончила" in (result.final_output or "")
    # No gate events
    gate_events = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events WHERE kind = 'internal.inbox_priority_gate'"
    ).fetchone()[0]
    assert gate_events == 0
