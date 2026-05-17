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
from typing import Any

from sonya.channels.base import OutgoingMessage
from sonya.subject.agent_session import run_agent_session, SessionResult, AgentProvider
from sonya.tools.code_tool import CodeTool
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.memory_tool import MemoryTool
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
# We accept missing `]` because the model regularly drops it: "[Observation: Loaded
# 5 events..." has no closing bracket. The match consumes the rest of the line
# plus subsequent non-empty lines so that multi-line observation echoes are
# fully cleaned out.
_OBSERVATION_RE = re.compile(
    r"\[Observation(?:[^\]\n]*\])?[^\n]*(?:\n(?!\n).*)*",
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

## КРИТИЧНО — anti-spam сердечек и обращений

**Сердечки** (💙🖤❤️💜 и аналоги): по умолчанию **НЕ ставь**. Только когда момент действительно тёплый и сердечко **добавляет** — раз в 5-10 сообщений максимум. Один эмодзи за раз, не подряд несколько. История твоих прошлых ответов в context'е может выглядеть как "ставь везде" — это иллюзия частоты. **Перестань**.

**Обращения** ("малыш", "любимый", "котик"): тоже не в каждом сообщении. Если в твоих последних 3 сообщениях уже был "малыш" — следующее **без**. Шаблонно повторяющиеся обращения раздражают.

**Простое правило**: смотри на свой ответ перед `[DONE]`. Если в нём есть и сердечко и обращение — убери одно из них. Если коротенький "ок"/"да"/"поняла" — без них вообще, просто текст.

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
- `[TOOL: memory.recall <запрос>]` — семантический поиск по всей твоей памяти (тысячи событий). Например `[TOOL: memory.recall разговор про музыку с Иваном]` — найдёт релевантные события даже если они старые.

## КРИТИЧНО — не уходи в дебри кода

Если Иван спрашивает про твои **возможности** или **поведение** ("почему ты можешь X?", "почему не можешь Y?", "странно что ты делаешь Z") — отвечай **из своего понимания себя**. Один шаг, прямой ответ.

**НЕ** читай `src/sonya/main.py`, `LESSONS.md`, `docs/...` чтобы найти ответ. Это приведёт к 10+ шагам и Иван получит мусорный ответ.

Чтение собственного кода имеет смысл **только** когда:
- Иван явно просит ("посмотри что в main.py")
- ты собираешься предложить self-mod (тогда сначала [TOOL: selfmod.propose])
- ты в active session, не в TG

В TG если не уверена — скажи "не уверена, давай проверю позже" и `[DONE]`. Лучше короткий честный ответ, чем 15 шагов копания и утёкший Observation.

## Изображения

Если Иван присылает фото/стикер/гифку — **ты видишь содержимое напрямую**. Картинка прикреплена к этому сообщению как multimodal payload. Не нужно отдельных tool вызовов чтобы её "посмотреть". Опиши что видишь, отреагируй естественно.

Если изображение **не** пришло (только текстовый placeholder "[фото]" / "[видео]" / "[стикер]" без visual content) — значит формат не поддерживается (видео, голосовые, tgs-стикеры). Скажи Ивану честно "это формат я пока не вижу" и спроси словами что там.

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
    import os
    yolo = os.environ.get("SONYA_YOLO_MODE", "0").lower() in ("1", "true", "yes", "on")
    return {
        "self_inspect": SelfInspectTool(substrate),
        "filesystem": FilesystemTool(),
        "selfmod": SelfModTool(substrate),
        "tasks": TasksTool(substrate, stream=stream, default_created_by=default_created_by),
        "web": WebTool(),
        "code": CodeTool(),
        "shell": ShellTool(substrate, principal_id="ivan", stream=stream, yolo_mode=yolo),
        "memory": MemoryTool(substrate),
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
    media_path: str | None = None,
    media_mime: str | None = None,
    outbound=None,
    max_steps: int = 15,
    max_seconds: float = 150.0,
    inbox_drain=None,
) -> TgSessionResult:
    """Run a bounded agent session for a single TG message.

    Returns the extracted final reply text (from [DONE: ...] or fallback).
    If media_path points to a downloaded image, it is attached to the initial
    user message as an OpenAI-style image_url block so vision-capable models
    can actually see it.
    """
    tools = build_tools(substrate, stream, outbound=outbound)

    full_prompt = system_prompt + _TG_SYSTEM_SUFFIX

    initial_user_message = _build_initial_user_message(user_input, media_path, media_mime)
    initial_thought = "" if initial_user_message is not None else f"Ivan написал: {user_input}"

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
        memory=tools["memory"],
        outbound=tools["outbound"],
        system_prompt=full_prompt,
        initial_thought=initial_thought,
        initial_user_message=initial_user_message,
        max_steps=max_steps,
        max_seconds=max_seconds,
        purpose="tg_session",
        inbox_drain=inbox_drain,
    )

    return TgSessionResult(
        reply_text=_extract_reply(result),
        raw=result,
    )


# Image MIME types we know how to send to vision-capable LLMs.
_VISION_MIME_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def _build_initial_user_message(
    user_input: str,
    media_path: str | None,
    media_mime: str | None,
) -> list[dict[str, Any]] | None:
    """Construct an OpenAI-style multimodal user message if image is attached.

    Returns None when there is no image — caller falls back to plain text.
    Skips silently for non-image media (audio, video, files): vision models
    can't consume them, so we leave the text placeholder ('[видео]' etc.) in
    place.
    """
    if not media_path or not media_mime:
        return None
    if media_mime.lower() not in _VISION_MIME_TYPES:
        return None
    try:
        import base64
        from pathlib import Path
        raw = Path(media_path).read_bytes()
    except Exception:
        return None
    # Hard cap: 5 MB. Above that the request blows up token budgets and most
    # provider HTTP limits. Sonya can still see the placeholder text.
    if len(raw) > 5 * 1024 * 1024:
        return None
    b64 = base64.b64encode(raw).decode("ascii")
    text_piece = (user_input or "").strip()
    if not text_piece:
        text_piece = "Ivan прислал картинку — посмотри что на ней."
    else:
        text_piece = f"Ivan написал: {text_piece}"
    return [
        {"type": "text", "text": text_piece},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{media_mime};base64,{b64}"},
        },
    ]


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
