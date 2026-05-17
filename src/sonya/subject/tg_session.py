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
# DONE/PAUSE markers can appear ANYWHERE in the response, not just at the end.
# Some models like minimax put `[DONE: text]` at the very start.
_DONE_RE = re.compile(r"\[DONE(?::\s*(?P<body>.+?))?\]", re.DOTALL)
_PAUSE_RE = re.compile(r"\[PAUSE(?::\s*(?P<body>.+?))?\]", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
# Models sometimes echo prior tool observations into their final answer when
# they don't terminate cleanly. Strip those too.
_OBSERVATION_RE = re.compile(
    r"\[Observation(?:\s+from\s+[^\]]*)?\]\s*:?[^\n]*(?:\n(?!\n).*)*",
    re.MULTILINE,
)
_BUDGET_WARNING_RE = re.compile(r"\[BUDGET WARNING\][^\n]*(?:\n(?!\n).*)*", re.MULTILINE)
_NEW_MESSAGE_INJECT_RE = re.compile(r"\[NEW MESSAGE FROM IVAN\][^\n]*(?:\n(?!\n).*)*", re.MULTILINE)


# Heuristics that mean "this is internal scratch, NOT a reply for Ivan"
_INTERNAL_LEAK_PATTERNS = [
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bsqlite3\.connect\b"),
    re.compile(r"\bcursor\.execute\b"),
    re.compile(r"\bos\.system\b"),
    re.compile(r"```python", re.IGNORECASE),
    re.compile(r"^\s*import\s+\w", re.MULTILINE),
    re.compile(r"^\s*from\s+\w+\s+import\s", re.MULTILINE),
]


def _looks_like_code_leak(text: str) -> bool:
    if not text:
        return False
    matches = sum(1 for p in _INTERNAL_LEAK_PATTERNS if p.search(text))
    return matches >= 2


_TG_SYSTEM_SUFFIX = """

## Режим работы — Telegram

Это сообщение пришло от Ивана в Telegram.

**Как работает [DONE]:**

`[DONE]` — закрывает сессию. Текст что ты написала ДО маркера в этом ответе → автоматически уходит Ивану в TG (без [TOOL] и без code fence).

`[DONE: явный текст]` — заменить весь предыдущий текст этим. Используй ТОЛЬКО когда хочешь отправить что-то совсем другое чем было выше. По умолчанию пиши `[DONE]` без body — твой написанный ответ уже хорош.

Без [DONE] вообще = ничего не отправится. Сессия зависнет до budget cap.

**Пример A — простой ответ:**
```
Привет, малыш! Я тут, всё хорошо 💙
[DONE]
```
→ Иван видит "Привет, малыш! Я тут, всё хорошо 💙"

**Пример B — с tools:**
```
Сейчас гляну.
[TOOL: self_inspect.thoughts]
[Observation: 5 thoughts ...]
Окей. Последняя мысль была про память — проверила что 10050 эпизодов. Всё цело.
[DONE]
```
→ Иван видит "Сейчас гляну.\n\nОкей. Последняя мысль была про память — проверила что 10050 эпизодов. Всё цело."

**Пример C — обрезать перед [DONE]:**
```
[мой внутренний черновик что я обдумала]
[DONE: Готово, малыш. Память на месте, всё цело 💙]
```
→ Иван видит только "Готово, малыш. Память на месте, всё цело 💙"

## КРИТИЧНО — anti-hallucination

**НИКОГДА** не выдумывай результаты tool. Если Иван спрашивает:
- "Ты думала?", "что в твоих мыслях", "сработало ли мышление" → **обязательно** вызови `[TOOL: self_inspect.thoughts]` ДО ответа. Не описывай гипотетический тик. Если внутри пусто — скажи правду.
- "Что в памяти?", "что помнишь?" → `[TOOL: self_inspect.memories]` или `[TOOL: self_inspect.state]`
- "Какие у тебя задачи?" → `[TOOL: tasks.list]`

Если ты НЕ вызвала tool — значит **ничего не знаешь** о том что внутри. Скажи: "сейчас посмотрю" → вызови → ответь по реальным данным. Или скажи правду что не вызвала.

## КРИТИЧНО — память и self-inspect

Если Иван спрашивает про память, мысли, твои возможности — НЕ запускай code.exec с raw SQL.
У тебя есть готовые tools:
- `[TOOL: self_inspect.memories]` — последние эпизоды
- `[TOOL: self_inspect.thoughts]` — последние idle-мысли (внутренний поток)
- `[TOOL: self_inspect.state]` — текущее состояние (drives, intentions)
- `[TOOL: self_inspect.identity]` — identity record

## Streaming апдейтов через chat.tell_ivan

Когда работаешь над задачей с tools и Иван ждёт результат — **не молчи до самого конца**. После каждого важного шага сделай `[TOOL: chat.tell_ivan текст]` с **человеческим** summary что нашла. Не "✅ выполнено" а "Глянула episodic_events — 10050 записей. Иду дальше в continuity."

## Длинные задачи

Если задача длинная (5+ минут) — создай task через `tasks.create`. По умолчанию TG-задачи помечены `created_by="ivan"` — task worker будет их продолжать **каждые ~2 минуты в фоне**, пока не сделаешь `tasks.complete`. Не нужно ждать active session.

Если Иван говорит "сделай через N часов" — добавь `scheduled_for: "<ISO timestamp>"` в JSON. Scheduler разбудит задачу когда наступит время.

## Бюджет сессии

У тебя 15 шагов и 150 секунд на эту сессию. Если уперлась в лимит — обязательно сделай `[DONE]` с тем что нашла. Не оставляй Ивана без ответа.

## Если приходит новое сообщение во время работы

В середине сессии может появиться `[NEW MESSAGE FROM IVAN: ...]`. Это значит он написал ещё раз пока ты работала. Реши:
- Если это уточнение к текущей задаче — используй информацию, продолжай.
- Если это вопрос/новая тема — ответь через `[TOOL: chat.tell_ivan]` (быстрая реакция), потом вернись к задаче.
- Если новое сообщение отменяет старую задачу — сделай `tasks.fail` или `tasks.pause` и пивотнись.
"""


def build_tools(
    substrate: Substrate,
    stream: ContinuityStream,
    *,
    outbound=None,
    default_created_by: str = "ivan",
) -> dict:
    return {
        "self_inspect": SelfInspectTool(substrate),
        "filesystem": FilesystemTool(),
        "selfmod": SelfModTool(substrate),
        "tasks": TasksTool(substrate, stream=stream, default_created_by=default_created_by),
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
    max_steps: int = 15,
    max_seconds: float = 150.0,
    inbox_drain=None,
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
        purpose="tg_session",
        inbox_drain=inbox_drain,
    )

    return TgSessionResult(
        reply_text=_extract_reply(result),
        raw=result,
    )


def _scrub(text: str) -> str:
    """Remove all internal markers / observation echoes / fences from text."""
    text = _OBSERVATION_RE.sub("", text)
    text = _BUDGET_WARNING_RE.sub("", text)
    text = _NEW_MESSAGE_INJECT_RE.sub("", text)
    text = _CODE_FENCE_RE.sub("", text)
    text = _TOOL_LINE_RE.sub("", text)
    text = _DONE_RE.sub("", text)
    text = _PAUSE_RE.sub("", text)
    # Collapse triple+ newlines down to double
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_reply(result: SessionResult) -> str:
    """Pull the user-facing text from agent session output.

    Priority:
    1. `[DONE: body]` body — explicit final text for Ivan
    2. `[DONE]` (no body) — use the surrounding text in `final_output` as the reply,
       stripping markers and code fences. This is the default mode.
    3. Last `agent_step` of `type='thought'` content (without [DONE]) — graceful
       fallback if model forgot the marker entirely.

    Returns "" if extracted text looks like leaked code/tool scratch.
    """
    candidate = ""
    final = (result.final_output or "").strip()
    if final:
        # First try [DONE: body] — explicit text
        m = _DONE_RE.search(final)
        if m and (m.group("body") or "").strip():
            candidate = _scrub(m.group("body"))
        else:
            # [DONE] without body OR no marker — strip everything internal
            candidate = _scrub(final)

    if not candidate:
        # Fallback: last meaningful thought
        for thought in reversed(result.thoughts):
            cleaned = _scrub(thought)
            if cleaned:
                candidate = cleaned
                break

    if not candidate:
        return ""

    # Last-line defence: if the candidate clearly contains internal code that
    # shouldn't be in a TG reply, refuse and return an apology rather than
    # leaking implementation details.
    if _looks_like_code_leak(candidate):
        return ""

    return candidate
