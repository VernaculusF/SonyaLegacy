"""TG-triggered agent session — same ReAct loop as active session, scoped to one
incoming Ivan message, with tools available.

Why this exists: previously TG path went through `plan_next` which is a single
LLM call without tools. Sonya would *describe* tool usage in text (e.g. write
"ls -la /home/sonya/" as if she ran it) but never actually called anything,
hallucinating outputs. This module routes TG messages through the real agent
loop so when Sonya needs to read her own code / memory / files, she actually
does, and the LLM sees real observations.

Tradeoffs:
- Costs more tokens than a plain reply (each tool call = extra LLM round).
- Bounded with smaller max_steps (8) and max_seconds (90).
- For pure chat ("привет, как ты"), Sonya emits [DONE: <text>] on step 1,
  cost ~= one regular call.

The final reply text is extracted from `[DONE: ...]`. If she emits a plain
message without [DONE], we still take the assistant text as the reply (with
tool markers stripped) — graceful degradation.

`chat.tell_ivan` is available so the agent can stream progress messages
during a long task. `tasks.create` is available for work that should
outlive this session.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sonya.channels.base import OutgoingMessage
from sonya.subject.agent_session import run_agent_session, SessionResult, AgentProvider
from sonya.tools.code_tool import CodeTool
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool
from sonya.tools.selfmod_tool import SelfModTool
from sonya.tools.shell_tool import ShellTool
from sonya.tools.tasks_tool import TasksTool
from sonya.tools.web_tool import WebTool
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate


_TOOL_LINE_RE = re.compile(r"\[TOOL:[^\]]*\]")
_DONE_RE = re.compile(r"\[DONE(?::\s*(?P<body>.+?))?\]\s*$", re.DOTALL)
_PAUSE_RE = re.compile(r"\[PAUSE(?::\s*(?P<body>.+?))?\]\s*$", re.DOTALL)


_TG_SYSTEM_SUFFIX = """

## Режим работы — Telegram

Это сообщение пришло от Ивана в Telegram. У тебя есть два варианта:

A) **Если ответ простой** (привет, поддержка, разговор) — отвечай нормально и заканчивай маркером:
   `[DONE: твой текст для Ивана]`
   Текст внутри [DONE: ...] — это то что Иван увидит. Без [DONE] = ничего не отправится.

B) **Если задача требует инструментов** (посмотреть код / память / файл / web / выполнить что-то) — используй tools.
   - НЕ описывай вызов текстом ("я посмотрю папку"). Реально вызывай: `[TOOL: filesystem.list /home/jester-sonya/Sonya]`
   - Получишь observation от tool. Думай дальше.
   - По ходу работы можешь слать апдейты через `[TOOL: chat.tell_ivan текст]` — Иван это увидит как промежуточное сообщение.
   - В конце финальный ответ — `[DONE: финальный текст для Ивана]`.

Если задача длинная (минут 5+) — создай task через `tasks.create` и работай частями. Active session подхватит её сама раз в 2 часа.

Если Иван просит "отчитываться по мере выполнения" — используй `chat.tell_ivan` после каждого осмысленного шага. Если "напиши только когда закончишь" — молчи до [DONE].

ВАЖНО: НИКОГДА не выдумывай результат tool. Если хочешь его — вызови. Если не хочешь вызывать — не описывай результат, скажи правду что не вызвала.
"""


def build_tools(
    substrate: Substrate,
    stream: ContinuityStream,
    *,
    outbound=None,
) -> dict:
    return {
        "self_inspect": SelfInspectTool(substrate),
        "filesystem": FilesystemTool(),
        "selfmod": SelfModTool(substrate),
        "tasks": TasksTool(substrate, stream=stream),
        "web": WebTool(),
        "code": CodeTool(),
        "shell": ShellTool(substrate, principal_id="ivan", stream=stream),
        "outbound": outbound,
    }


@dataclass(slots=True)
class TgSessionResult:
    reply_text: str
    raw: SessionResult


async def run_tg_session(
    *,
    provider: AgentProvider,
    stream: ContinuityStream,
    substrate: Substrate,
    system_prompt: str,
    user_input: str,
    outbound=None,
    max_steps: int = 8,
    max_seconds: float = 90.0,
) -> TgSessionResult:
    """Run a bounded agent session for a single TG message.

    Returns the extracted final reply text (from [DONE: ...] or fallback).
    """
    tools = build_tools(substrate, stream, outbound=outbound)

    full_prompt = system_prompt + _TG_SYSTEM_SUFFIX

    result = await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=tools["self_inspect"],
        filesystem=tools["filesystem"],
        selfmod=tools["selfmod"],
        tasks=tools["tasks"],
        web=tools["web"],
        code=tools["code"],
        shell=tools["shell"],
        outbound=tools["outbound"],
        system_prompt=full_prompt,
        initial_thought=f"Ivan написал: {user_input}",
        max_steps=max_steps,
        max_seconds=max_seconds,
    )

    return TgSessionResult(
        reply_text=_extract_reply(result),
        raw=result,
    )


def _extract_reply(result: SessionResult) -> str:
    """Pull the user-facing text from agent session output.

    Priority:
    1. [DONE: body] body — preferred
    2. [PAUSE: body] body — also OK as final
    3. Last thought text with all [TOOL: ...] / [DONE]/[PAUSE] markers stripped
    """
    final = (result.final_output or "").strip()
    if final:
        m = _DONE_RE.search(final)
        if m:
            body = (m.group("body") or "").strip()
            if body:
                return body
        m = _PAUSE_RE.search(final)
        if m:
            body = (m.group("body") or "").strip()
            if body:
                return body
        # No marker body but final present — strip markers and return rest
        cleaned = _TOOL_LINE_RE.sub("", final)
        cleaned = _DONE_RE.sub("", cleaned)
        cleaned = _PAUSE_RE.sub("", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            return cleaned

    # Fallback: last meaningful thought
    for thought in reversed(result.thoughts):
        cleaned = _TOOL_LINE_RE.sub("", thought)
        cleaned = _DONE_RE.sub("", cleaned)
        cleaned = _PAUSE_RE.sub("", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            return cleaned

    return ""
