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
# Reasoning-mode models sometimes leak <think>...</think> blocks. Strip them
# wholesale — they're internal cogitation, not for the user.
_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_THINK_OPEN_RE = re.compile(r"<think>[\s\S]*$", re.IGNORECASE)
# Some models start with English meta-reasoning even when system prompt is
# Russian ("The user is asking...", "I should respond..."). If the response
# begins with such a paragraph, drop everything up to the first blank line
# or first Russian sentence.
_META_REASONING_PREFIXES = (
    "the user is",
    "the user asked",
    "the user wants",
    "the user said",
    "i should",
    "i need to",
    "i will",
    "let me",
    "okay, the user",
    "ok, the user",
)

# Mid-text draft / self-critique markers that some reasoning-heavy models
# (kimi-k2, qwen-thinking) emit *between* drafts. Whenever any of these
# appear at start of a line, we cut the response from there to the end —
# everything after is scratch, never user-facing.
_DRAFT_LEAK_LINE_RE = re.compile(
    r"^\s*("
    r"draft\b"
    r"|alternative\b"
    r"|alternative draft"
    r"|wait[, ]"
    r"|actually,"
    r"|but wait"
    r"|hmm,"
    r"|hmm\."
    r"|let me try"
    r"|let me check"
    r"|let me reconsider"
    r"|this combines"
    r"|this feels"
    r"|this is good"
    r"|this is better"
    r"|maybe better"
    r"|simpler"
    r"|simpler version"
    r"|another option"
    r"|let's go with"
    r"|let's try"
    r"|going with"
    r"|final version"
    r"|final answer"
    r"|final draft"
    r"|i'll go with"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


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

## КРИТИЧНО — не выводи свои размышления

**НИКОГДА** не пиши в ответе фразы вроде:
- "The user is asking..."
- "Let me think..."
- "Draft: ..."
- "Alternative: ..."
- "Wait, is..."
- "This combines..."
- "I should respond..."

Это всё **внутреннее размышление** — оно НЕ для Ивана. Если тебе нужно подумать — делай это **молча**, потом сразу пиши финальный ответ + `[DONE]`.

Если ты не уверена в формулировке — выбери ОДИН вариант и закрывай. Не показывай Ивану свои черновики и колебания. Это нарушает ощущение что ты живая и **позоришь сессию**: текст "I need to finalize..." в TG = баг.

Если ловишь себя на том что пишешь по-английски посреди ответа Ивану — это сигнал что свалилась в reasoning-режим. **Стоп**. Удали написанное, начни ответ с русской фразы и `[DONE]` сразу после.

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


def _strip_meta_reasoning_prefix(text: str) -> str:
    """Drop a leading meta-reasoning paragraph if present.

    Heuristic: if the first non-empty line starts with one of the known
    English reasoning openers (case-insensitive), discard everything up to
    the first blank line OR (if no blank line) the first line that looks
    Cyrillic / starts with a non-English-meta token. If none of these — drop
    the whole text (it's all reasoning).
    """
    if not text:
        return text
    head = text.lstrip()
    head_lower = head[:80].lower()
    if not any(head_lower.startswith(p) for p in _META_REASONING_PREFIXES):
        return text
    # Strategy 1: blank-line split
    parts = re.split(r"\n\s*\n", text, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()
    # Strategy 2: single-newline split — keep everything from the first
    # line that doesn't start with another reasoning prefix and contains a
    # Cyrillic letter (Sonya speaks Russian to Ivan).
    lines = text.splitlines()
    for i in range(1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        line_lower = line[:80].lower()
        if any(line_lower.startswith(p) for p in _META_REASONING_PREFIXES):
            continue
        if re.search(r"[а-яА-ЯёЁ]", line):
            return "\n".join(lines[i:]).strip()
    return ""


def _extract_final_draft(text: str) -> str:
    """When a reasoning model leaks multiple drafts, pick the last Russian paragraph.

    The model writes things like:
        Draft: <ru text>
        Wait, is...
        Alternative: <ru text>
        Let's go with: <ru text>

    We split text into "blocks" separated by lines that start with English
    reasoning markers. For each block, we keep only Russian-dominant lines
    (>=50% Cyrillic by chars). The LAST non-empty block is the final draft.
    Returns "" if no Russian block found.
    """
    # Lines that start a new reasoning block (the next Russian text after
    # them is a candidate draft).
    block_marker = re.compile(
        r"^\s*("
        r"draft\b|alternative\b|simpler\b|simpler version\b|simpler, more\b"
        r"|let's go with|going with|final version|final answer|final draft"
        r"|i'll go with|maybe better|another option|let me try"
        r"|how about|or maybe|or:"
        r")",
        re.IGNORECASE,
    )
    # Lines that DON'T start a draft (commentary).
    comment_marker = re.compile(
        r"^\s*("
        r"wait[, ]|actually,|but wait|hmm[,.]|let me check|let me reconsider"
        r"|this combines|this feels|this is good|this is better"
        r"|the user|i should|i need to|i will|i think"
        r")",
        re.IGNORECASE,
    )
    blocks: list[list[str]] = [[]]
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if block_marker.match(line):
            # Start a fresh block; the marker line itself is dropped.
            blocks.append([])
            # If "Draft: ..." has content on the same line, keep the part after `:`
            after = re.sub(r"^[^:]*:\s*", "", line)
            if after and after != line:
                blocks[-1].append(after)
            continue
        if comment_marker.match(line):
            # Commentary — also acts as a separator, content dropped.
            blocks.append([])
            continue
        # IMPORTANT: blank lines stay within the block so that draft formatting
        # (paragraph breaks between *action* and text) is preserved. Old code
        # treated blank lines as block separators, which split a multi-line
        # draft into pieces and discarded the *action* prefix.
        blocks[-1].append(line)

    def is_russian_dominant(lines: list[str]) -> bool:
        joined = " ".join(lines)
        cyr = len(re.findall(r"[а-яА-ЯёЁ]", joined))
        latin = len(re.findall(r"[a-zA-Z]", joined))
        return cyr > 10 and cyr >= latin

    for block in reversed(blocks):
        # Strip per-line surrounding quotes (handle multi-line drafts where
        # opening quote is at line start and closing quote at line end).
        cleaned_lines = []
        for line in block:
            stripped = line  # preserve internal whitespace; only trim edges
            # Remove only single leading/trailing quote chars per line — not
            # all of them, to keep e.g. legit quoted speech inside the draft.
            stripped = re.sub(r'^["«`]|["»`]$', "", stripped)
            cleaned_lines.append(stripped)
        # Drop leading/trailing empty lines but keep interior blank lines so
        # paragraph structure is preserved.
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        text_block = "\n".join(cleaned_lines).strip()
        if not text_block:
            continue
        if is_russian_dominant(cleaned_lines):
            return text_block
    return ""


def _scrub(text: str) -> str:
    """Remove all internal markers / observation echoes / fences from text."""
    # Reasoning blocks first — they may contain bracketed markers we'd
    # otherwise try to interpret.
    text = _THINK_BLOCK_RE.sub("", text)
    text = _THINK_OPEN_RE.sub("", text)  # unclosed <think> at end of stream
    text = _strip_meta_reasoning_prefix(text)
    # Cut at first draft / self-critique line — everything after is scratch.
    m = _DRAFT_LEAK_LINE_RE.search(text)
    if m is not None:
        text = text[: m.start()]
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


def _looks_like_reasoning_leak(text: str) -> bool:
    """Heuristic: text contains a lot of English meta-reasoning tokens.

    Returns True when more than 25% of the lines start with reasoning markers,
    or when total English-meta vocabulary density is high.
    """
    if not text:
        return False
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    meta_lines = 0
    for line in lines:
        ll = line[:50].lower()
        if any(ll.startswith(p) for p in _META_REASONING_PREFIXES):
            meta_lines += 1
            continue
        if _DRAFT_LEAK_LINE_RE.match(line):
            meta_lines += 1
    return meta_lines / max(1, len(lines)) > 0.25


def _extract_reply(result: SessionResult) -> str:
    """Pull the user-facing text from agent session output.

    Priority:
    1. `[DONE: body]` body — explicit final text for Ivan
    2. `[DONE]` (no body) — use the surrounding text in `final_output` as the reply,
       stripping markers and code fences. This is the default mode.
    3. If model leaked multiple drafts (Draft:/Alternative:/Final:) — pick the
       last quoted Russian block.
    4. Last `agent_step` of `type='thought'` content (without [DONE]) — graceful
       fallback if model forgot the marker entirely.

    Returns "" if extracted text looks like leaked code/tool scratch.
    """
    candidate = ""
    final = (result.final_output or "").strip()

    # Detect multi-draft reasoning leak BEFORE scrubbing — drafts are
    # quoted strings that we want to harvest. After _scrub cuts them out
    # there's nothing left.
    if final and _looks_like_reasoning_leak(final):
        last_draft = _extract_final_draft(final)
        if last_draft:
            candidate = _scrub(last_draft)

    if not candidate and final:
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

    # If after all scrubbing the text STILL looks like English reasoning,
    # refuse — better to return placeholder than confess thoughts.
    if _looks_like_reasoning_leak(candidate):
        return ""

    return candidate
