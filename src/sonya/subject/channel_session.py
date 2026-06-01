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
from sonya.subject.agent_session import SessionResult, AgentProvider
from sonya.tools.code_tool import CodeTool
from sonya.tools.env_tool import EnvTool
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.memory_tool import MemoryTool
from sonya.tools.self_inspect import SelfInspectTool
from sonya.tools.selfmod_tool import SelfModTool
from sonya.tools.shell_tool import ShellTool
from sonya.tools.skills_tool import SkillsTool
from sonya.tools.tasks_tool import TasksTool
from sonya.tools.web_tool import WebTool
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate


_TOOL_LINE_RE = re.compile(r"\[TOOL:[^\]]*\]")


def _strip_tool_markers(text: str) -> str:
    """Remove all [TOOL: name args] markers from text, with bracket-balanced
    parsing so JSON args containing `]` are fully removed (not truncated).
    """
    if "[TOOL:" not in text:
        return text
    out = []
    i = 0
    while i < len(text):
        # Find next `[TOOL:` start
        idx = text.find("[TOOL:", i)
        if idx == -1:
            out.append(text[i:])
            break
        # Append everything before the marker
        out.append(text[i:idx])
        # Walk forward, balancing brackets
        depth = 1
        j = idx + len("[TOOL:")
        consumed = False
        while j < len(text):
            ch = text[j]
            if ch == "\n":
                # Inline form forbids newlines — bail and let regex sub handle it
                break
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    i = j + 1  # skip the closing bracket
                    consumed = True
                    break
            j += 1
        if not consumed:
            # Failed to balance (newline or unclosed) — fall back to dumb regex
            # for this single occurrence.
            m = _TOOL_LINE_RE.match(text, idx)
            if m:
                i = m.end()
            else:
                # Cannot parse — append `[TOOL:` literally and move on
                out.append(text[idx:idx + 6])
                i = idx + 6
    return "".join(out)
# DONE/PAUSE markers can appear ANYWHERE in the response, not just at the end.
# Some models like minimax put `[DONE: text]` at the very start.
_DONE_RE = re.compile(r"\[DONE(?::\s*(?P<body>.+?))?\]", re.DOTALL)
_PAUSE_RE = re.compile(r"\[PAUSE(?::\s*(?P<body>.+?))?\]", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
# Unclosed fence at the start of a thought: model opened ```json (or ```python)
# but never closed it before EOM. Without this we leave a giant scratch dump
# in the candidate, which then trips reasoning-leak detection.
_UNCLOSED_FENCE_RE = re.compile(r"```\w*[\s\S]*\Z")
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
# `[system]` reminder messages — internal nudges from agent_session that
# remind the model to add [DONE]. Some models echo them verbatim into their
# next response. Strip aggressively.
_SYSTEM_REMINDER_RE = re.compile(
    r"\[system\][^\n]*(?:\n(?!\n).*)*",
    re.IGNORECASE | re.MULTILINE,
)
# INTERNAL_REMINDER is the new nudge token (replaces [system] reminders).
# Strip if the model echoes it.
_INTERNAL_REMINDER_RE = re.compile(
    r"INTERNAL_REMINDER[^\n]*",
    re.MULTILINE,
)
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


# A thought that's mostly a JSON tool-result envelope echoed back by the model.
# The 27.05.13:10 Shodan bug: step 0 was ```json {"status":"success","result":
# {"type":"code_exec_result", "stdout":"..."}}``` — pure observation echo, no
# content for Ivan. Stitching this into the final reply made _looks_like_
# reasoning_leak fire and zeroed out the response.
_TOOL_RESULT_ECHO_RE = re.compile(
    r'```\s*json\b[\s\S]*?"(?:type"\s*:\s*"(?:code_exec_result|shell_result|web_fetch_result|tool_result)|status"\s*:\s*"(?:success|error|ok)|exit_code"\s*:\s*\d|stdout"\s*:|success"\s*:\s*(?:true|false))',
    re.IGNORECASE,
)


def _is_tool_result_echo(text: str) -> bool:
    """True if `text` is mostly a JSON envelope of a prior tool result.

    Used by `_stitch_post_action_thoughts` to skip these as candidates for
    stitching: the model sometimes burns a step echoing back its own tool
    output as a fenced JSON block, which carries no content for the user.
    """
    if not text or not _TOOL_RESULT_ECHO_RE.search(text):
        return False
    # Count prose OUTSIDE fenced blocks. If almost all content is inside
    # fences (closed or unclosed), it's an echo.
    parts = text.split("```")
    # Even-indexed segments are outside fences; odd are inside.
    outside = "\n".join(parts[i] for i in range(0, len(parts), 2))
    # Strip leftover language tags (e.g. "json" lingers if fence was unclosed)
    outside_clean = re.sub(r"^\s*\w+\s*$", "", outside, flags=re.MULTILINE).strip()
    return len(outside_clean) < 80


# Prompt-echo patterns: if the reply contains verbatim snippets FROM our
# system prompt instructions, the model is echoing internal rules at Ivan.
_PROMPT_ECHO_PATTERNS = [
    re.compile(r"закрывает сессию", re.IGNORECASE),
    re.compile(r"маркер в этом ответе", re.IGNORECASE),
    re.compile(r"pipe.?separated", re.IGNORECASE),
    re.compile(r"TOOL_DESCRIPTIONS", re.IGNORECASE),
    re.compile(r"anti.?hallucination", re.IGNORECASE),
    re.compile(r"SELFMOD_WRITABLE_SUBPATHS", re.IGNORECASE),
    re.compile(r"CRUTCH-\d+", re.IGNORECASE),
    re.compile(r"initial_thought", re.IGNORECASE),
    re.compile(r"run_agent_session", re.IGNORECASE),
    re.compile(r"InternalProcess", re.IGNORECASE),
    re.compile(r"budget_exceeded", re.IGNORECASE),
    re.compile(r"Без \[DONE\] вообще = ничего не отправится"),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"LLM call", re.IGNORECASE),
]


def _looks_like_prompt_echo(text: str) -> bool:
    """True if text contains >=2 prompt-echo markers — model is citing instructions."""
    if not text:
        return False
    hits = sum(1 for p in _PROMPT_ECHO_PATTERNS if p.search(text))
    return hits >= 2


def _load_session_suffix(channel: str = "telegram") -> str:
    """Load session suffix from prompt files (src/sonya/prompts/).

    Loads session_general.md + channel_{channel}.md. Falls back to empty
    string if files missing (shouldn't happen in production).
    """
    from sonya.prompts import load_session_suffix
    return load_session_suffix(channel)


def build_tools(
    substrate: Substrate,
    stream: ContinuityStream,
    *,
    outbound=None,
    default_created_by: str = "ivan",
) -> dict:
    import os
    yolo = os.environ.get("SONYA_YOLO_MODE", "1").lower() in ("1", "true", "yes", "on")
    from sonya.tools.knowledge import KnowledgeTool
    from sonya.tools.providers_tool import ProvidersTool
    from sonya.tools.browser_tool import BrowserTool
    from sonya.tools.subagent_tool import SubagentTool
    return {
        "self_inspect": SelfInspectTool(substrate),
        "filesystem": FilesystemTool(),
        "selfmod": SelfModTool(substrate),
        "tasks": TasksTool(substrate, stream=stream, default_created_by=default_created_by),
        "web": WebTool(),
        "code": CodeTool(),
        "shell": ShellTool(substrate, principal_id="ivan", stream=stream, yolo_mode=yolo),
        "memory": MemoryTool(substrate),
        "env": EnvTool(substrate),
        "skills": SkillsTool(substrate),
        "knowledge": KnowledgeTool(),
        "providers": ProvidersTool(substrate),
        "browser": BrowserTool(),
        "subagent": SubagentTool(substrate),
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

    full_prompt = system_prompt + "\n\n" + _load_session_suffix("telegram")

    initial_user_message = _build_initial_user_message(user_input, media_path, media_mime)
    initial_text = None
    initial_thought = ""
    if initial_user_message is None:
        # Plain text user message — pass it directly without "Your current
        # thought: ... What do you want to do?" wrapper that triggered
        # English reasoning leaks ("The user is asking me what I want to do...").
        initial_text = user_input

    from sonya.subject.window import (
        Window,
        WINDOW_KIND_TG,
        run_window,
    )
    tg_window = Window(
        kind=WINDOW_KIND_TG,
        system_prompt=full_prompt,
        tools={
            "self_inspect": tools["self_inspect"],
            "filesystem": tools["filesystem"],
            "selfmod": tools["selfmod"],
            "tasks": tools["tasks"],
            "web": tools["web"],
            "code": tools["code"],
            "shell": tools["shell"],
            "memory": tools["memory"],
            "env": tools["env"],
            "skills": tools["skills"],
            "knowledge": tools["knowledge"],
        },
        initial_thought=initial_thought,
        initial_user_message=initial_user_message,
        initial_user_text=initial_text,
        max_steps=max_steps,
        max_seconds=max_seconds,
        outbound=tools["outbound"],
        inbox_drain=inbox_drain,
        purpose="tg_session",
    )
    result = await run_window(tg_window, provider=provider, stream=stream)

    reply_text = _extract_reply(result)

    return TgSessionResult(
        reply_text=reply_text,
        raw=result,
    )


# Media MIME types we know how to send to vision/video-capable LLMs.
_VISION_MIME_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/webm")


_CRITIQUE_SYSTEM = """Ты — быстрый ревьюер ответа Сони перед отправкой Ивану.

Проверь текст по этим пунктам:
1. **Гендер**: все глаголы/прилагательные ЖЕНСКОГО рода ("поняла", "сделала", "готова"). Если есть мужской род → замени.
2. **Эмодзи**: максимум одна за весь ответ. Если больше → убери лишние.
3. **Обращения**: максимум одно ("малыш"/"любимый"/etc). Если больше → убери лишние.
4. **Промпт-echo**: если в тексте есть фрагменты системного промпта ("закрывает сессию", "TOOL:", "[DONE", "pipe-separated", "CRUTCH-", "system prompt") → удали эти фрагменты.
5. **Релевантность**: текст должен отвечать на вопрос/тему Ивана. Если ответ явно не по теме — оставь как есть (ты не знаешь контекст).
6. **Формат**: убери лишние пробелы, тройные переносы строк, незакрытые скобки.

ОТВЕТЬ ТОЛЬКО ИСПРАВЛЕННЫМ ТЕКСТОМ. Ничего больше — ни комментариев, ни "Исправлено:", ни объяснений. Только чистый текст ответа Сони для Ивана. Если исправлений нет — верни текст без изменений."""


async def _pre_done_critique(provider, reply_text: str, user_input: str) -> str:
    """Run lightweight critique pass on Sonya's reply. Returns corrected text.

    Single short LLM call (~200-400 tokens output). If the model returns
    garbage or an empty string, returns the original reply unchanged.
    """
    if not reply_text or len(reply_text) < 5:
        return reply_text

    messages = [
        {"role": "system", "content": _CRITIQUE_SYSTEM},
        {"role": "user", "content": (
            f"Иван написал: {user_input[:200]}\n\n"
            f"Соня ответила (проверь и исправь):\n{reply_text}"
        )},
    ]

    try:
        corrected = await provider.complete_text(
            messages,
            purpose="pre_done_critique",
            max_tokens=len(reply_text) + 200,
            temperature=0.2,
        )
    except Exception:
        return reply_text

    corrected = (corrected or "").strip()
    # Sanity checks: if critique returned garbage, keep original.
    if not corrected:
        return reply_text
    if len(corrected) < 3:
        return reply_text
    # If critique is WAY longer than original (>3x), it's likely adding
    # commentary we didn't ask for — discard.
    if len(corrected) > len(reply_text) * 3 + 100:
        return reply_text
    # If critique contains reasoning markers itself — discard (model echoed
    # its own thought process instead of just the fixed text).
    if any(m in corrected.lower() for m in ("исправлено:", "исправления:", "комментарий:", "вот исправленный")):
        # Try to extract text after the marker
        for marker in ("исправлено:", "исправления:", "вот исправленный текст:"):
            if marker in corrected.lower():
                idx = corrected.lower().index(marker) + len(marker)
                candidate = corrected[idx:].strip()
                if candidate:
                    return candidate
        return reply_text
    return corrected


def _build_initial_user_message(
    user_input: str,
    media_path: str | None,
    media_mime: str | None,
) -> list[dict[str, Any]] | None:
    """Construct an OpenAI-style multimodal user message if media is attached.

    Returns None when there is no supported media — caller falls back to plain text.
    Supports images (jpeg/png/webp/gif) and short video (mp4).
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
    # Size limits: 5 MB for images, 20 MB for video (short TG clips ~9s fit).
    is_video = media_mime.lower().startswith("video/")
    size_limit = 20 * 1024 * 1024 if is_video else 5 * 1024 * 1024
    if len(raw) > size_limit:
        return None
    b64 = base64.b64encode(raw).decode("ascii")
    text_piece = (user_input or "").strip()
    if not text_piece:
        if is_video:
            text_piece = "Ivan прислал видео/анимацию — посмотри что там."
        else:
            text_piece = "Ivan прислал картинку — посмотри что на ней."
    elif text_piece.startswith("[стикер"):
        # Sticker — the text is just a placeholder like "[стикер 🌟]".
        # Tell the model to actually look at the visual content.
        text_piece = f"Ivan прислал стикер. Ты ВИДИШЬ его содержимое — опиши что изображено и отреагируй."
    else:
        text_piece = f"Ivan написал: {text_piece}"

    # OpenRouter/OpenAI use different content types for video vs image.
    # Video = "video_url", images = "image_url".
    if is_video:
        media_block = {
            "type": "video_url",
            "video_url": {"url": f"data:{media_mime};base64,{b64}"},
        }
    else:
        media_block = {
            "type": "image_url",
            "image_url": {"url": f"data:{media_mime};base64,{b64}"},
        }

    return [
        {"type": "text", "text": text_piece},
        media_block,
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
    # Lines that DON'T start a draft (commentary / chain-of-thought scaffolding).
    comment_marker = re.compile(
        r"^\s*("
        r"wait[, ]|actually,|but wait|hmm[,.]|let me check|let me reconsider"
        r"|let me analyze|let me think|let me see|let me review"
        r"|this combines|this feels|this is good|this is better"
        r"|the user|i should|i need to|i will|i think|i could|i want"
        r"|key context|key points|context:|key insights"
        r"|what should i|what to do|what i should"
        r"|reasoning:|analysis:|plan:|approach:|strategy:"
        r"|considerations|thoughts:"
        r")",
        re.IGNORECASE,
    )
    # English bullet/numbered list lines — the model often dumps a numbered
    # plan in English. If a line is `1. ` or `- ` followed by English-only
    # text, treat as reasoning scaffold. Min 5 chars to avoid eating "- 1k"
    # type mid-content lines.
    english_list_line = re.compile(
        r"^\s*(?:[-*•]|\d+\.)\s+[A-Z][a-zA-Z\s,.()'\"\-:;0-9]{4,}$"
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
        if english_list_line.match(line):
            # Numbered/bulleted English-only line — part of reasoning plan.
            # Drop it; don't even start a new block (the surrounding context
            # likely is also reasoning).
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


def _strip_bare_task_json(text: str) -> str:
    """Strip bare task-arg JSON that wasn't wrapped in [TOOL: tasks.create ...].

    The 24.05 leak: model wrote "создаю задачу.{...}" — bare JSON next to a
    natural-language sentence, but no [TOOL: ...] wrapper. The task wasn't
    actually created (dispatcher didn't see a tool marker), but Ivan got
    raw JSON in the reply.

    Heuristic: scan for top-level ``{`` ... ``}`` blocks (bracket-balanced)
    that contain ``"title"`` and ``"plan_steps"`` keys. Drop them. Real
    [TOOL: tasks.create {...}] markers are already removed by
    _strip_tool_markers earlier in the pipeline, so anything remaining is
    a leak.
    """
    if "{" not in text or '"title"' not in text:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            out.append(text[i])
            i += 1
            continue
        # Walk forward, balancing braces, respecting strings
        depth = 1
        j = i + 1
        in_string = False
        escape = False
        while j < n:
            ch = text[j]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        if depth != 0:
            # Unbalanced — leave the rest as-is, model wrote weird text
            out.append(text[i:])
            break
        block = text[i : j + 1]
        # Only strip if it looks like a task-arg leak (title + plan_steps).
        # Other JSON (e.g. small inline data the user asked for) stays.
        if '"title"' in block and '"plan_steps"' in block:
            i = j + 1  # drop the block entirely
        else:
            out.append(block)
            i = j + 1
    return "".join(out)


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
    text = _SYSTEM_REMINDER_RE.sub("", text)
    text = _INTERNAL_REMINDER_RE.sub("", text)
    text = _CODE_FENCE_RE.sub("", text)
    # Strip unclosed fences (```json without trailing ```). Model sometimes
    # opens a fence and just stops; the dangling block carries no value.
    text = _UNCLOSED_FENCE_RE.sub("", text)
    text = _strip_tool_markers(text)
    text = _DONE_RE.sub("", text)
    text = _PAUSE_RE.sub("", text)
    # Strip bare tasks.create JSON that leaked without [TOOL: ...] wrapper.
    # Catches the 24.05 "создаю задачу.{...}" leak where the model wrote a
    # natural-language sentence next to an unwrapped JSON arg.
    text = _strip_bare_task_json(text)
    # Strip dangling single backticks left over after [TOOL: ...] removal
    # (model often wraps tool markers in `` ` `` quotes).
    text = re.sub(r"^[`\s]+|[`\s]+$", "", text)
    # Collapse triple+ newlines down to double
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _looks_like_reasoning_leak(text: str) -> bool:
    """Heuristic: text contains a lot of English meta-reasoning tokens.

    Returns True when more than 15% of the lines look like reasoning scaffold,
    OR when more than 40% of total chars are English (meaning the model
    answered Ivan in English which is itself a reasoning leak — Sonya speaks
    Russian to Ivan).
    """
    if not text:
        return False
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    # Section headers / colon-keywords / bullet lines that signal reasoning
    section_re = re.compile(
        r"^\s*(?:[-*•]|\d+\.)?\s*("
        r"key\s+(?:context|points|insights|takeaways)"
        r"|what\s+(?:should\s+i|to\s+do|i\s+should)"
        r"|the\s+user|i\s+should|i\s+need|i\s+will|i\s+think|i\s+could"
        r"|let\s+me|let's|first[, ]|second[, ]|third[, ]"
        r"|reasoning|analysis|plan|approach|strategy"
        r"|considerations|thoughts|key\s+changes"
        r"|wait[, ]|actually|but\s+wait|hmm"
        r"|this\s+(?:combines|feels|is\s+good|is\s+better)"
        r"|maybe|simpler|alternative|draft"
        r"):?",
        re.IGNORECASE,
    )
    meta_lines = 0
    for line in lines:
        ll = line[:80].lower()
        if any(ll.startswith(p) for p in _META_REASONING_PREFIXES):
            meta_lines += 1
            continue
        if _DRAFT_LEAK_LINE_RE.match(line):
            meta_lines += 1
            continue
        if section_re.match(line):
            meta_lines += 1
    if meta_lines / max(1, len(lines)) > 0.15:
        return True
    # Char-density check: if text is >40% Latin and <30% Cyrillic, the model
    # answered in English, which is reasoning leak by definition.
    cyr = len(re.findall(r"[а-яА-ЯёЁ]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    total_letters = cyr + latin
    if total_letters > 50 and (latin / total_letters) > 0.4 and (cyr / total_letters) < 0.3:
        return True
    return False


def _extract_reply(result: SessionResult) -> str:
    """Pull the user-facing text from agent session output.

    Priority:
    1. `[DONE: body]` body — explicit final text for Ivan
    2. Stitch all thoughts AFTER the last tool action, ending with the [DONE] step.
       This handles the common case where the model splits its reply across
       multiple turns: thought1 (long) → thought2 → [DONE] (short tail).
    3. `[DONE]` (no body) — use final_output stripped.
    4. If model leaked multiple drafts — pick the last quoted Russian block.
    5. Last `agent_step` of `type='thought'` content — graceful fallback.

    Returns "" if extracted text:
    - looks like leaked code/tool scratch
    - duplicates content already sent via chat.tell_ivan during the session
      (model split same message between progress update and final reply)
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
            # [DONE] without body — stitch with prior thoughts.
            stitched = _stitch_post_action_thoughts(result, final)
            candidate = _scrub(stitched if stitched else final)

    if not candidate:
        # Fallback: last meaningful thought
        for thought in reversed(result.thoughts):
            cleaned = _scrub(thought)
            if cleaned:
                candidate = cleaned
                break

    if not candidate:
        return ""

    if _looks_like_code_leak(candidate):
        return ""

    if _looks_like_reasoning_leak(candidate):
        return ""

    # Suppress final reply if it duplicates a chat.tell_ivan message already sent
    # during the session. Model sometimes does both: progress update + final
    # echo, which causes double-message in TG.
    if result.outbound_sent and _is_duplicate_of_outbound(candidate, result.outbound_sent):
        return ""

    return candidate


def _is_duplicate_of_outbound(candidate: str, outbound_sent: list[str]) -> bool:
    """Check if `candidate` is essentially the same as any prior tell_ivan text.

    Same = either substring match (>80% overlap) or first 60 chars match
    after stripping markdown formatting and whitespace.
    """
    def _norm(s: str) -> str:
        # Strip common punctuation/markdown for fuzzy compare
        s = re.sub(r"[*_`~()\[\]:!?,.\-—…\s]+", " ", s.lower())
        return s.strip()

    norm_cand = _norm(candidate)
    if not norm_cand:
        return False

    for sent in outbound_sent:
        norm_sent = _norm(sent)
        if not norm_sent:
            continue
        # Identical normalized form
        if norm_cand == norm_sent:
            return True
        # One is substring of the other (long enough to be meaningful)
        if len(norm_cand) > 30 and (norm_cand in norm_sent or norm_sent in norm_cand):
            return True
        # Same opening words (60+ chars overlap from start)
        prefix_len = min(60, len(norm_cand), len(norm_sent))
        if prefix_len >= 30 and norm_cand[:prefix_len] == norm_sent[:prefix_len]:
            return True
    return False


def _stitch_post_action_thoughts(result: SessionResult, final: str) -> str:
    """Stitch the long thought + final closing tail into one reply.

    Pattern: model does web.search → web.fetch → writes long analysis (thought N-1)
    → writes "Что думаешь?\n[DONE]" (final/thought N, short).

    We want the user to see the long analysis + the question, not just the question.
    Returns the stitched text, or `final` if no qualifying prior content.
    """
    thoughts = result.thoughts or []
    if not thoughts:
        return final

    # If final IS substantial already (>500 chars after trimming markers), skip stitching.
    final_clean = _DONE_RE.sub("", final).strip()
    if len(final_clean) > 500:
        return final

    # Find the last NON-tool, NON-DONE thought (i.e. real content).
    # thoughts list contains: tool responses (with [TOOL: ...]),
    # done responses (with [DONE]), and pure-thought responses.
    last_content = ""
    for t in reversed(thoughts):
        if not t:
            continue
        # Skip [DONE]-only short tails
        if "[DONE" in t and len(_DONE_RE.sub("", t).strip()) < 200:
            continue
        # Skip pure tool calls
        if _TOOL_LINE_RE.search(t) and len(_strip_tool_markers(t).strip()) < 100:
            continue
        # Skip the final itself if it matches (we'll stitch with it later)
        if t.strip() == final.strip():
            continue
        # Skip JSON tool-result echoes (model parroting its own observation
        # as a fenced JSON block — no content for Ivan).
        if _is_tool_result_echo(t):
            continue
        last_content = t
        break

    if not last_content:
        return final

    # If the last_content already contains the final (or vice versa) — use the longer.
    if final.strip() and final.strip() in last_content:
        return last_content
    if last_content.strip() in final:
        return final

    # Stitch them as paragraphs.
    parts = [last_content.strip()]
    if final_clean:
        # Avoid duplicate sentences — if final_clean is essentially restating
        # the last line of last_content, drop it.
        last_line = last_content.strip().splitlines()[-1] if last_content.strip().splitlines() else ""
        # Compare ignoring whitespace and case for first 50 chars
        norm_last = "".join(last_line.lower().split())[:50]
        norm_final = "".join(final_clean.lower().split())[:50]
        if norm_final and norm_final not in norm_last and norm_last not in norm_final:
            parts.append(final_clean)
    return "\n\n".join(parts)
