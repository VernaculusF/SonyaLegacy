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


async def test_project_consent_block_sets_waiting_choice(substrate: Substrate, tmp_path: Path) -> None:
    from sonya.project import ProjectStore
    from sonya.tools.projects_tool import ProjectsTool

    project = ProjectStore(substrate).create(
        "consent project",
        workspace_path=str(tmp_path / "consent-project"),
    )
    provider = _Stub([
        "[TOOL: shell.run echo blocked]",
        "[DONE: waiting for choice]",
    ])

    await run_agent_session(
        provider=provider,
        stream=ContinuityStream(substrate),
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(project_root=tmp_path),
        projects=ProjectsTool(substrate),
        workspace_id=project.project_id,
        system_prompt="test",
        max_steps=2,
        max_seconds=10.0,
        purpose="test",
    )

    assert ProjectStore(substrate).get(project.project_id).status == "waiting_choice"


async def test_grace_period_allows_early_work_tools(substrate: Substrate, monkeypatch) -> None:
    """First half of step budget: non-dialog tools NOT blocked.

    Иван заметил что Соня делала "Понял. Сейчас." перед каждым browser.open
    — лишний шаг. Теперь grace period (max_steps // 2) пропускает работу;
    финальный [DONE] всё ещё требует chat.dialog ИЛИ [DONE: text].
    """
    stream = ContinuityStream(substrate)

    import sonya.initiative.outbound as outbound_mod

    def _fake_call_outbound_sync(_gate, text, **kw):
        return f"[OK] dialog: {text[:40]}"

    monkeypatch.setattr(
        outbound_mod, "call_outbound_sync", _fake_call_outbound_sync,
    )

    # Step 0 — straight to web.fetch (no chat.dialog ack). Gate should NOT
    # fire because we're under grace threshold. Step 1 — chat.dialog to reply.
    provider = _Stub([
        "[TOOL: web.fetch https://example.com]",
        "[TOOL: chat.dialog]\nОткрыла example.com — заголовок Example Domain.",
        "[DONE]"
    ])

    from sonya.tools.web_tool import WebTool
    fake_outbound = object()

    await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        web=WebTool(),
        outbound=fake_outbound,
        system_prompt="test",
        initial_user_text="Открой example.com.",
        require_dialog_reply=True,
        max_steps=10,  # grace = 5
        max_seconds=10.0,
        purpose="test",
    )

    # No gate-block on web.fetch (step 0 < grace threshold).
    rows = substrate.connection.execute(
        "SELECT payload_json FROM continuity_events "
        "WHERE kind = 'internal.inbox_priority_gate' "
        "  AND payload_json LIKE '%web.fetch%'"
    ).fetchall()
    assert not rows, (
        "web.fetch on step 0 must NOT be gate-blocked under grace period"
    )


async def test_done_blocked_after_work_without_followup_dialog(substrate: Substrate, monkeypatch) -> None:
    """Phase 2 of inbox gate: даже если она ответила первый раз, после
    реальной работы (web.fetch / browser / etc.) **bare** `[DONE]` без
    body должен быть заблокирован. (Если есть `[DONE: <text>]` —
    DONE-as-reply короткозамыкает gate и закрывает сессию: см.
    test_done_with_body_dispatches_as_reply_short_circuits_gate.)
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
    #  3. [DONE]   (bare, no body)                  → MUST be blocked (phase 2)
    #  4. [DONE]   (bare again)                     → still blocked
    provider = _Stub([
        "Принято.\n[TOOL: chat.tell_ivan]\nпривет, начинаю",
        "Получаю данные.\n[TOOL: web.fetch https://example.com]",
        "Готово.\n[DONE]",   # bare [DONE], no inline body — must block
        "Опять.\n[DONE]",
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
        "phase-2 gate must trigger when bare [DONE] follows work tools "
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


async def test_repeated_dialog_without_new_input_or_work_is_suppressed(
    substrate: Substrate, monkeypatch
) -> None:
    import sonya.initiative.outbound as outbound_mod

    sent: list[str] = []

    def _fake_call_outbound_sync(_gate, text, **kw):
        sent.append(text)
        return f"[OK] dialog: {text[:40]}"

    monkeypatch.setattr(outbound_mod, "call_outbound_sync", _fake_call_outbound_sync)
    provider = _Stub([
        "[TOOL: chat.dialog]\nПервый ответ.",
        "[TOOL: chat.dialog]\nВторой ответ без новой причины.",
        "[DONE]",
    ])

    await run_agent_session(
        provider=provider,
        stream=ContinuityStream(substrate),
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        outbound=object(),
        system_prompt="test",
        initial_user_text="Привет.",
        require_dialog_reply=True,
        max_steps=4,
        max_seconds=10.0,
        purpose="test",
    )

    assert sent == ["Первый ответ."]
    suppressed = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events "
        "WHERE kind = 'internal.dialog_repeat_suppressed'"
    ).fetchone()[0]
    assert suppressed == 1


async def test_done_with_body_is_blocked_by_inbox_gate(
    substrate: Substrate, monkeypatch
) -> None:
    """`[DONE: <text>]` without chat.dialog must NOT bypass the inbox gate."""
    stream = ContinuityStream(substrate)

    sent_via_outbound: list[str] = []
    import sonya.initiative.outbound as outbound_mod

    def _fake_call_outbound_sync(_gate, text, **kw):
        sent_via_outbound.append(text)
        return f"[OK] dialog: {text[:40]}"

    monkeypatch.setattr(
        outbound_mod, "call_outbound_sync", _fake_call_outbound_sync,
    )

    provider = _Stub(["[DONE: Открыла example.com, заголовок 'Example Domain'.]"])
    fake_outbound = object()

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        outbound=fake_outbound,
        system_prompt="test",
        initial_user_text="Соня, открой example.com.",
        require_dialog_reply=True,
        max_steps=4,
        max_seconds=10.0,
        purpose="test",
    )

    assert not sent_via_outbound

    gate_events = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events "
        "WHERE kind = 'internal.inbox_priority_gate'"
    ).fetchone()[0]
    assert gate_events >= 1


async def test_bare_done_without_body_still_blocked_by_phase_1_old():
    pass


async def test_bare_done_without_body_still_blocked_by_phase_1(
    substrate: Substrate,
) -> None:
    """`[DONE]` без body НЕ короткозамкнёт gate — нужен либо `chat.dialog`,
    либо текст внутри `[DONE: ...]`."""
    stream = ContinuityStream(substrate)
    provider = _Stub([
        "[DONE]",  # bare, no body
        "[DONE]",  # still bare
    ])
    await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=SelfInspectTool(substrate),
        filesystem=FilesystemTool(),
        system_prompt="test",
        initial_user_text="привет",
        require_dialog_reply=True,
        max_steps=3,
        max_seconds=5.0,
        purpose="test",
    )
    rows = substrate.connection.execute(
        "SELECT COUNT(*) FROM continuity_events "
        "WHERE kind = 'internal.inbox_priority_gate'"
    ).fetchone()[0]
    assert rows >= 1, "bare [DONE] without body must still trigger gate"
