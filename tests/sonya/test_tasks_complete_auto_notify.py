"""tasks.complete / tasks.fail auto-notify Ivan via outbound gate.

Symptom from the 27.05.15:30 mpbacademy session: worker collected the
final result, called `tasks.complete` with a multi-paragraph result body,
but Ivan got nothing in TG. He had to ping ("ну?") for the answer to
arrive 13 minutes later — through a fresh TG round-trip, not from the
worker.

Root cause: `tasks.complete` only emitted `task.completed` continuity
event. The prompt told the agent to ALSO call `chat.tell_ivan` after,
but when the model bundled both `[TOOL: chat.tell_ivan ...]` and
`[TOOL: tasks.complete ...json...]` in one response, the block-form
parser picked up only `tasks.complete` (it had a fenced JSON arg) and
dropped the inline chat.tell_ivan.

Fix: terminal task transitions now auto-send the result/reason to Ivan
through the outbound gate (unless notify_mode='silent'), and record
the text in outbound_sent so _extract_reply doesn't double-message.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from sonya.channels.base import OutgoingMessage
from sonya.channels.registry import ChannelRegistry
from sonya.initiative.outbound import OutboundGate
from sonya.state import Substrate, seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.subject.agent_session import (
    _ToolContext,
    _h_tasks_complete,
    _h_tasks_fail,
)
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool
from sonya.tools.tasks_tool import TasksTool


class _FakeChannel:
    name = "telegram"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.is_running = True

    async def start(self, deps) -> None:
        self.is_running = True

    async def stop(self) -> None:
        self.is_running = False

    async def send(self, chat_id: str, message: OutgoingMessage) -> None:
        self.sent.append((chat_id, message.text))


@pytest.fixture()
def env(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    seed_identity_if_empty(sub)
    stream = ContinuityStream(sub)
    registry = ChannelRegistry()
    fake = _FakeChannel()
    registry.register(fake)
    gate = OutboundGate(
        registry=registry,
        stream=stream,
        target_tg_chat_id="123",
        max_per_day=20,
        min_quiet_minutes=0,
    )
    tasks = TasksTool(sub, stream=stream, default_created_by="ivan")
    yield sub, stream, gate, fake, tasks
    sub.close()


def _make_ctx(sub: Substrate, gate, tasks: TasksTool, *, outbound_sent=None) -> _ToolContext:
    return _ToolContext(
        self_inspect=SelfInspectTool(sub),
        filesystem=FilesystemTool(),
        selfmod=None,
        tasks=tasks,
        web=None,
        code=None,
        shell=None,
        memory=None,
        env=None,
        skills=None,
        outbound=gate,
        outbound_sent=outbound_sent if outbound_sent is not None else [],
    )


async def _flush_loop():
    """Yield twice so create_task'd outbound dispatch coro actually runs."""
    import asyncio
    await asyncio.sleep(0)
    await asyncio.sleep(0)


# --- complete ---


async def test_complete_with_result_notifies_ivan(env) -> None:
    sub, stream, gate, fake, tasks = env
    task = tasks._service.create(
        title="recon target X",
        created_by="ivan",
        notify_mode="progress",
    )
    ctx = _make_ctx(sub, gate, tasks)
    arg = json.dumps({
        "task_id": task.task_id,
        "result": "Нашла backup.sql на /admin/. Доказательства собраны.",
    })
    out = _h_tasks_complete(arg, ctx)
    await _flush_loop()
    assert "[OK] task done" in out
    assert "notify queued" in out
    assert any(
        "Нашла backup.sql" in text for _, text in fake.sent
    ), f"expected backup.sql notify, got {fake.sent}"
    assert any("Нашла backup.sql" in s for s in (ctx.outbound_sent or []))


async def test_complete_silent_mode_skips_notify(env) -> None:
    sub, stream, gate, fake, tasks = env
    task = tasks._service.create(
        title="silent recon",
        created_by="ivan",
        notify_mode="silent",
    )
    ctx = _make_ctx(sub, gate, tasks)
    arg = json.dumps({
        "task_id": task.task_id,
        "result": "результат — silent task, не отправлять",
    })
    out = _h_tasks_complete(arg, ctx)
    await _flush_loop()
    assert "[OK] task done" in out
    assert "notify queued" not in out
    assert fake.sent == []


async def test_complete_empty_result_skips_notify(env) -> None:
    """No result body → nothing to send."""
    sub, _, gate, fake, tasks = env
    task = tasks._service.create(
        title="empty result",
        created_by="ivan",
        notify_mode="progress",
    )
    ctx = _make_ctx(sub, gate, tasks)
    arg = json.dumps({"task_id": task.task_id, "result": ""})
    out = _h_tasks_complete(arg, ctx)
    await _flush_loop()
    assert "[OK] task done" in out
    assert "notify queued" not in out
    assert fake.sent == []


async def test_complete_dedups_against_prior_chat_tell_ivan(env) -> None:
    """If model already chat.tell_ivan'd the same text, don't double-send."""
    sub, _, gate, fake, tasks = env
    task = tasks._service.create(
        title="x",
        created_by="ivan",
        notify_mode="progress",
    )
    same_text = "Готово. Нашла дамп backup.sql, всё подтверждено."
    ctx = _make_ctx(sub, gate, tasks, outbound_sent=[same_text])
    arg = json.dumps({"task_id": task.task_id, "result": same_text})
    out = _h_tasks_complete(arg, ctx)
    await _flush_loop()
    assert "[OK] task done" in out
    assert "suppressed" in out
    assert fake.sent == []


# --- fail ---


async def test_fail_with_reason_notifies_ivan(env) -> None:
    sub, _, gate, fake, tasks = env
    task = tasks._service.create(
        title="impossible target",
        created_by="ivan",
        notify_mode="progress",
    )
    ctx = _make_ctx(sub, gate, tasks)
    arg = json.dumps({
        "task_id": task.task_id,
        "reason": "Cloudflare на всех путях, без residential прокси не пройти.",
    })
    out = _h_tasks_fail(arg, ctx)
    await _flush_loop()
    assert "task failed" in out.lower() or "[OK]" in out
    assert any(
        "Cloudflare" in text for _, text in fake.sent
    ), f"expected fail-reason notify, got {fake.sent}"


async def test_fail_silent_skips_notify(env) -> None:
    sub, _, gate, fake, tasks = env
    task = tasks._service.create(
        title="silent fail",
        created_by="ivan",
        notify_mode="silent",
    )
    ctx = _make_ctx(sub, gate, tasks)
    arg = json.dumps({"task_id": task.task_id, "reason": "no go"})
    _h_tasks_fail(arg, ctx)
    await _flush_loop()
    assert fake.sent == []


# --- regression: outbound is None (e.g. test environment without gate) ---


async def test_complete_works_with_no_outbound(env) -> None:
    """When outbound gate is unavailable (tests, idle ticks), complete must
    still succeed without raising. Just no notify."""
    sub, _, _, _, tasks = env
    task = tasks._service.create(title="x", created_by="ivan")
    ctx = _ToolContext(
        self_inspect=SelfInspectTool(sub),
        filesystem=FilesystemTool(),
        selfmod=None,
        tasks=tasks,
        web=None, code=None, shell=None, memory=None, env=None, skills=None,
        outbound=None,
        outbound_sent=[],
    )
    out = _h_tasks_complete(
        json.dumps({"task_id": task.task_id, "result": "done"}),
        ctx,
    )
    assert "[OK] task done" in out
    # No notify suffix should be appended (the "notify" word in _format_task's
    # `notify_mode:` line is fine — we're checking only the trailing suffix).
    assert "notify queued" not in out
    assert "notify suppressed" not in out
    assert "notify [BLOCKED]" not in out
