"""Single-stream agent session with tool use.

Not a parallel process. Part of the one event loop.
Called from InternalProcess on active_timeout or when tools needed for response.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.tools.code_tool import CodeTool
from sonya.tools.env_tool import EnvTool
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.memory_tool import MemoryTool
from sonya.tools.self_inspect import SelfInspectTool
from sonya.tools.skills_tool import SkillsTool
from sonya.tools.selfmod_tool import SelfModTool
from sonya.tools.shell_tool import ShellTool
from sonya.tools.tasks_tool import TasksTool
from sonya.tools.web_tool import WebTool


class AgentProvider(Protocol):
    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        ...


@dataclass(slots=True)
class SessionResult:
    steps: int = 0
    thoughts: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    final_output: str = ""
    budget_exceeded: bool = False
    # Texts already sent to user via chat.tell_ivan during the session.
    # Used by channel_session._extract_reply to suppress duplicate final
    # output when [DONE: text] echoes a prior tell_ivan.
    outbound_sent: list[str] = field(default_factory=list)


TOOL_DESCRIPTIONS = """Available tools:

## Tool syntax

Two forms supported:

**Simple form** — one line, args after the name:
```
[TOOL: filesystem.list /home/jester-sonya/Sonya]
```

**Block form** — for long args / code / JSON. Marker line then a fenced block:
```
[TOOL: code.exec]
```python
import sqlite3
conn = sqlite3.connect("/home/jester-sonya/.sonya/sonya_substrate.db")
print(conn.execute("SELECT COUNT(*) FROM episodic_events").fetchone())
```
```

Use block form when args contain newlines, brackets, or > ~200 chars.

## Tools

- self_inspect.identity — read your identity record
- self_inspect.state — read current subject state (drives, intentions)
- self_inspect.thoughts — read your recent thoughts
- self_inspect.memories — read recent episodic memories
- self_inspect.intentions — read active intentions
- self_inspect.code [module_path] — read your own source code (e.g. "planning/planner.py")
- self_inspect.modules — list your packages
- self_inspect.drift [days] — aggregate self-observation: drift detector hit counts (initiative_blocked, stuck_loops), blocked/failed tasks, selfmod activity, work volume. Default last 3 days. Use this every periodic self-improvement session to see your own behaviour patterns and decide what to fix in your own code via selfmod.
- memory.recall [query] — semantic search over your full episodic history (returns top-5 relevant memories with similarity score)
- memory.index_status — diagnostic: how many events are embedded vs pending
- env.set [key value] — record what you observe about Ivan / context (e.g. `env.set ivan_status спит`, `env.set mood уставший`, `env.set activity работает`). Used to suppress initiative when Ivan is busy/asleep — OutboundGate respects ivan_status='спит' / 'занят'.
- env.get [key] — read a previously recorded observation
- env.list — list all current observations
- env.clear [key] — drop an observation when no longer relevant
- skills.list — show registered skills and their status
- skills.run [skill_id] [query] — execute a skill (e.g. `skills.run skill-memory-search что мы обсуждали вчера`)
- skills.register_builtins — seed built-in skills (memory-search, identity-check, dialog-tone) into registry. Call once.

- knowledge.list [topic?] — список тем или файлов в теме (твоя база знаний в ~/.sonya/knowledge/)
- knowledge.read [topic/file] — прочитать факт-файл (напр. `knowledge.read pentest/sqli`)
- knowledge.write [topic/file]\\n[markdown content] — создать/обновить факт-файл. ПЕРВАЯ строка = путь, дальше содержимое
- knowledge.search [query] — full-text поиск по всей базе знаний
- knowledge.delete [topic/file] — удалить факт-файл
- goals.list — show active long-term goals
- goals.create [title | description | priority] — create a goal (higher priority = more important)
- goals.achieve [goal_id] — mark a goal as achieved
- goals.abandon [goal_id] — mark a goal as abandoned
- filesystem.read [path] — read a file
- filesystem.list [path] — list directory
- filesystem.tree [path] — show directory tree
- filesystem.write — block form: first line of args = path, remaining = content
- plugins.list — list available plugins
- plugins.create — block form: first line = name, remaining = python code
- plugins.call [name] [args] — call a loaded plugin
- selfmod.propose — block form, JSON: {"target": "src/sonya/...", "summary": "...", "content": "<full file>"} OR pipe-separated: target | summary | content
- selfmod.propose_edit — для МАЛЫХ правок:
    inline pipe (одна строка): target | summary | old_substring | new_substring
    block JSON (multi-line OK): [TOOL: selfmod.propose_edit]\n```\n{"target":"...","summary":"...","old":"...","new":"..."}\n```
  Меняет первое вхождение old → new в файле, формирует full-content proposal автоматически.
  Если old_substring встречается >1 раза — даст ошибку (расширь контекст).
  ВАЖНО: при использовании block JSON ставь `\n` в old/new для перевода строк, не реальные newlines в JSON-строке.
- selfmod.test_sandbox [proposal_id]
- selfmod.validate [proposal_id]
- selfmod.apply [proposal_id]
- selfmod.list [status_filter?]
- selfmod.get [proposal_id]
- selfmod.governed [proposal_id]
- selfmod.check_governed [proposal_id]
- selfmod.rollback [proposal_id] [reason?]
- selfmod.soft_restart [reason?]

- tasks.create — block form, JSON: {
    "title": "...",
    "description": "...",
    "plan_steps": ["step1", "step2"],
    "created_by": "ivan" | "self",        // default depends on context
    "scheduled_for": "2026-05-17T15:00:00Z",  // optional ISO timestamp; empty = run now
    "notify_mode": "progress" | "final" | "silent",  // default "progress"
    "max_sessions": 3                     // optional; 0 = unlimited. After this many active sessions / worker runs, task auto-fails if not done.
  }
  - created_by="ivan": worker runs every ~2 min (continuous)
  - created_by="self": picked up by active session every 2 hours (her own ideas)
  - scheduled_for=future: scheduler holds it until the time
  - notify_mode=progress: chat.tell_ivan after each step. final: only on done. silent: never.
  - max_sessions: hard budget cap. Use when Ivan says "не пытайся продолжать после N попыток".
- tasks.list [status_filter?] — pending / in_progress / blocked / done / failed / open
- tasks.get [task_id]
- tasks.pick — pick next open task and mark in_progress
- tasks.complete — block form, JSON: {"task_id": "...", "result": "..."}
- tasks.fail — block form, JSON: {"task_id": "...", "reason": "..."}
- tasks.block — block form, JSON: {"task_id": "...", "blocker": "..."}
- tasks.unblock [task_id]
- tasks.pause [task_id]
- tasks.handoff — block form, JSON: {"task_id": "...", "notes": "where I left off, what I learned, what's blocking", "next_step": "concrete one-liner for next session"}
  **Call BEFORE [DONE]** when ending a session on an unfinished task. This is THE continuity carrier across sessions — without handoff, the next session starts blind. Bumps sessions_used; if max_sessions reached, task auto-fails.
- tasks.plan / tasks.step — legacy step-tracking tools. Optional. Use ONLY if the task already has plan_steps you want to mark off. For continuity prefer tasks.handoff.

Tasks survive sessions. When active session starts you pick up your in_progress task.

- web.search [query]
- web.fetch [url]
- code.exec — block form, code goes inside ```python ... ```
- shell.run [command] — approval-gated
- pip.install [package] — approval-gated

- chat.tell_ivan [message] — send a message to Ivan in TG (throttled, max 5/day). Use during long tasks for progress updates.

## How to finish

Always end with `[DONE: <твой реальный финальный ответ для Ивана здесь>]` if this is a TG conversation, or `[DONE]` for internal sessions. **Не копируй placeholder дословно** — впиши настоящий текст ответа на русском (например: `[DONE: Поняла, малыш.]`). Текст внутри `[DONE: ...]` уходит Ивану в TG. Без [DONE] — ничего не отправится.

## ОДИН tool за один ход

Когда ты пишешь `[TOOL: name args]` — это **один** инструмент. Жди observation, потом следующий.

**Не делай так:**
```
[TOOL: web.search foo]
[TOOL: web.fetch bar]
[TOOL: web.fetch baz]
[DONE]
```
Это план, не выполнение. Парсер возьмёт первый tool, остальные потеряются. И `[DONE]` в том же ответе закроет сессию до того как успеют сработать остальные tools.

**Правильно:**
- Ход 1: пишешь `[TOOL: web.search foo]` — больше ничего.
- Ход 2: получаешь observation, решаешь что делать. Если нужен ещё tool — пишешь его.
- Ход 3: и так далее, пока не закончишь.
- Финальный ход: пишешь reply (текст) + `[DONE]` или `[DONE: text]`. Без tool маркеров.

Если хочешь сделать несколько действий — это **несколько ходов**, не один многострочный ответ.
"""


# Single-line: [TOOL: name arg-no-newlines-or-brackets]
# Single-line: [TOOL: name arg-no-newlines]
# Inline parser is bracket-balanced: handles JSON args containing nested
# `]` (e.g. plan_steps array). Falls through to a simple regex if no balanced
# match found.
_TOOL_INLINE_RE = re.compile(r"\[TOOL:\s*([^\s\]]+)(?:\s+([^\n\]]*))?\]")
# Block form: [TOOL: name]\n```optional-lang\n<arg>\n```
_TOOL_BLOCK_RE = re.compile(
    r"\[TOOL:\s*([^\s\]]+)\s*\]\s*\n```[a-zA-Z0-9_-]*\n(.*?)\n```",
    re.DOTALL,
)
# Locate the start of an inline TOOL marker so we can do bracket-balanced
# parse after the name.
_TOOL_INLINE_START_RE = re.compile(r"\[TOOL:\s*([^\s\]]+)\s*")


def _find_balanced_inline_tool(response: str) -> tuple[str, str] | None:
    """Find an inline [TOOL: name arg] where arg may contain nested `]`.

    Returns (tool_name, arg) if found. arg is text between the name and the
    OUTERMOST closing `]`, computed by bracket-balancing.

    Pattern: `[TOOL: name {nested[json]args}]` — outer pair of `[]` brackets
    are the TOOL delimiter; inner `[...]` are part of the arg.
    """
    m = _TOOL_INLINE_START_RE.search(response)
    if not m:
        return None
    tool_name = m.group(1)
    arg_start = m.end()
    # Walk forward, balancing brackets. Depth starts at 1 (we're inside the
    # outer `[TOOL: ...`). Stop on newline (inline form forbids it).
    depth = 1
    i = arg_start
    while i < len(response):
        ch = response[i]
        if ch == "\n":
            return None  # not an inline form — caller falls back to block
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return tool_name, response[arg_start:i].strip()
        i += 1
    return None


def _extract_tool_call(response: str) -> tuple[str, str] | None:
    """Return (tool_name, arg) if response contains a tool invocation.

    Block form takes precedence so multi-line code/JSON args work.
    Inline form uses bracket-balanced parsing so JSON args with `]` work.
    """
    m = _TOOL_BLOCK_RE.search(response)
    if m:
        return m.group(1), m.group(2)
    # Try bracket-balanced inline parse first (handles JSON with nested ]).
    balanced = _find_balanced_inline_tool(response)
    if balanced is not None:
        return balanced
    # Fallback to simple regex (shouldn't be reached after balanced parser
    # but kept for safety on edge cases).
    m = _TOOL_INLINE_RE.search(response)
    if m:
        return m.group(1), (m.group(2) or "").strip()
    return None


# --- Blocker reflex (Phase 2B of unified loop) ----------------------------
#
# After every tool call, we scan the observation for explicit failure
# signals. If we find one, we inject a one-line BLOCKER hint into the
# next user-turn, before the model plans step N+1. Without this the model
# tends to repeat the same call (especially when it's been told via prompt
# "try alternatives on failure" — the rule is too far back in context to
# survive into step N+1's attention).
#
# This is a cheap regex pass, NOT a separate LLM call. It nudges the
# model with concrete observation-grounded text. The model still decides
# what to actually do.

_BLOCKER_PATTERNS: tuple[tuple[str, "re.Pattern[str]", str], ...] = (
    (
        "auth_401",
        re.compile(r"\b(401|HTTP 401|unauthor[ie]z[e]?d|invalid[_ ]api[_ ]?key|invalid[_ ]?key)\b", re.IGNORECASE),
        "Это auth-проблема (нет/неверный/просроченный ключ). Попробуй найти ключ через "
        "`env.list` или `memory.recall`, или взять другой провайдер.",
    ),
    (
        "auth_403",
        re.compile(r"\b(403|forbidden|access[_ ]denied|permission denied)\b", re.IGNORECASE),
        "Доступ запрещён. Альтернатива — другой эндпойнт, прокси, или другой подход к данным.",
    ),
    (
        "rate_limit",
        re.compile(r"\b(429|rate[_ ]limit(ed)?|too many requests|quota exceeded)\b", re.IGNORECASE),
        "Rate-limit. Сейчас повтор не поможет — возьми другой ключ/IP/провайдер либо "
        "подожди и переключись на параллельную работу.",
    ),
    (
        "credits_exhausted",
        re.compile(r"\b(credits[_ ]?(exhaust|depleted|empty|0)|usage[_ ]limit|quota[_ ]reach|payment[_ ]required|402|credits_exhausted|out[_ ]of[_ ]credits|insufficient[_ ]credit|insufficient[_ ]quota)\b", re.IGNORECASE),
        "Кредиты/квота исчерпаны. Этот ключ мёртв до пополнения — найди другой "
        "(env.list / memory.recall / создать новый аккаунт). Не повторяй с тем же ключом.",
    ),
    (
        "http_5xx",
        re.compile(r"\b(5\d{2})\b.*?(server error|internal|bad gateway|service unavailable|gateway timeout)", re.IGNORECASE | re.DOTALL),
        "Upstream 5xx. Можно повторить ОДИН раз через ~10с, но если падает второй — "
        "переключись на альтернативный backend.",
    ),
    (
        "http_404",
        # Require "404" adjacent to "Not Found" or "HTTP 404" prefix —
        # NOT bare digit `404` (which appears in random URLs and side-fetches).
        # The model can probe ten URLs in one code.exec call; if ALL of them
        # are 404 the main task is dead, but if just sitemap.xml is 404 while
        # the main fetch returns 200, we shouldn't fire the blocker.
        re.compile(
            r"(\bHTTP[/ ]?404\b|\b404\s+Not\s+Found\b"
            r"|^\s*Status:?\s*404\b|status_code['\"]?\s*[:=]\s*404\b"
            r"|^\s*\[?404\]?\s*$)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Запрашиваемый ресурс — 404 Not Found. Проверь близкие варианты "
        "(другой path/host/protocol), не дёргай тот же URL.",
    ),
    (
        "exception_traceback",
        re.compile(r"\b(Traceback \(most recent call last\)|^[A-Z]\w+Error:|^[A-Z]\w+Exception:)", re.MULTILINE),
        "Исключение в коде. Прочитай конкретное сообщение, исправь cause, "
        "не запускай тот же код снова.",
    ),
    (
        "dns_or_connect",
        re.compile(r"\b(getaddrinfo failed|name resolution|connection refused|connect[_ ]?timeout|no route to host|network unreachable)\b", re.IGNORECASE),
        "Сетевая ошибка (DNS/connect). Проверь хост, или попробуй прокси/альтернативный "
        "URL. Тот же запрос не пройдёт.",
    ),
    (
        "empty_result",
        # Anchored to the WHOLE observation: only fire when the entire
        # output is whitespace / "[OK]" / a few null-equivalents. A
        # `[HTTP 200] ... Bytes: 21035 ... Login Toggle navigation ...`
        # response has plenty of content but contained blank lines
        # between header and body — earlier regex with MULTILINE matched
        # those blanks and false-positived. We need to make sure THIS
        # whole observation is empty, not just "contains some empty line".
        # _detect_blocker uses re.search anchored on the truncated obs;
        # here we use re.fullmatch via DOTALL to require everything.
        re.compile(
            r"\A\s*(\[OK\]|None|null|\{\s*\}|\[\s*\])?\s*\Z",
            re.IGNORECASE | re.DOTALL,
        ),
        "Пустой результат — tool вернулся без данных. Возможно, неверные параметры. "
        "Проверь arg перед повтором.",
    ),
    (
        "ddg_blocked",
        re.compile(r"\b(unusual traffic|verifying you are human|captcha|access denied for security)\b", re.IGNORECASE),
        "Поисковик блокирует за антибот. Используй другой backend "
        "(SearXNG fallback / web.fetch напрямую / Google scrape) или подожди.",
    ),
)


# Tools where 'empty result' is normal and shouldn't fire (no false positives).
_EMPTY_OK_TOOLS = frozenset({
    "tasks.complete", "tasks.fail", "tasks.block", "tasks.unblock",
    "tasks.handoff", "tasks.pause", "tasks.create", "tasks.pick",
    "env.set", "env.clear", "goals.create", "goals.achieve",
    "goals.abandon", "skills.register_builtins", "memory.index_status",
    "selfmod.apply", "selfmod.validate", "selfmod.propose", "selfmod.propose_edit",
})

# Local-data tools whose output may legitimately contain the words "403",
# "forbidden", "error", "rate limit" etc. as part of stored content (task
# descriptions, knowledge base, memory recall). These NEVER make external
# calls so HTTP/auth blocker detection on their output is always a FP.
_LOCAL_DATA_TOOLS = frozenset({
    "tasks.get", "tasks.list", "tasks.plan", "tasks.step",
    "memory.recall", "memory.index_status",
    "knowledge.list", "knowledge.read", "knowledge.search",
    "self_inspect.identity", "self_inspect.state", "self_inspect.thoughts",
    "self_inspect.memories", "self_inspect.intentions", "self_inspect.code",
    "self_inspect.modules", "self_inspect.drift",
    "filesystem.list", "filesystem.read", "filesystem.tree",
    "env.list", "env.get",
    "skills.list",
    "selfmod.list", "selfmod.get", "selfmod.check_governed",
    "goals.list",
})


def _detect_blocker(tool_name: str, observation: str) -> tuple[str, str] | None:
    """Return (kind, hint) if observation looks like a blocker.

    Returns None for normal results. The kind is a short tag for audit;
    hint is a one-sentence Russian nudge for the model. Cheap regex, no
    LLM call. Designed for false-positive safety — better miss a blocker
    than mis-flag a successful result.

    See `_BLOCKER_PATTERNS`.
    """
    if not observation:
        return None
    # Local-data tools never produce HTTP/auth failures — their bodies often
    # contain the words '403' / 'forbidden' / etc. as task descriptions or
    # notes (the FP we saw in the wild where every tasks.get fired auth_403
    # because the task title was about web reconnaissance).
    if tool_name in _LOCAL_DATA_TOOLS:
        return None
    obs = observation[:6000]  # cap scan length
    # Success-shape gate: if the response clearly STARTS with a successful
    # HTTP/tool envelope and has substantive body afterwards, refuse to
    # flag any blocker. This prevents the FP we saw in the wild where
    # web.fetch returned [HTTP 200] ... 21KB body and the regex caught a
    # blank line between headers and body as 'empty_result', or caught
    # a `404` mention in the middle of a successful multi-fetch as
    # 'http_404'. Real failures (5xx, exceptions, captcha, auth) are
    # never preceded by a 2xx envelope so we don't lose those.
    head = obs.lstrip()[:80]
    if (
        head.startswith("[HTTP 2") or head.startswith("[HTTP 3")
        or head.startswith("HTTP/1.1 2") or head.startswith("HTTP/2 2")
    ) and len(obs) > 200:
        return None
    for kind, pat, hint in _BLOCKER_PATTERNS:
        # `empty_result` only meaningful for tools that normally return data
        if kind == "empty_result" and tool_name in _EMPTY_OK_TOOLS:
            continue
        if pat.search(obs):
            return (kind, hint)
    return None


# Markers that disqualify a candidate ack-preamble: model is leaking internal
# scaffold rather than addressing Ivan.
_ACK_REJECT_MARKERS = (
    "[TOOL:", "[DONE", "[PAUSE", "[Observation",
    "<think>", "</think>",
    "INTERNAL_REMINDER", "[BUDGET",
    "draft:", "Draft:", "Alternative:",
    "The user is", "I should", "I need to", "Let me",
)


def _extract_pre_tool_preamble(response: str) -> str:
    """Return text before the first tool / DONE / PAUSE marker.

    Used for auto-ack on step 0: when Sonya writes "Поняла, малыш, начну
    с разведки." then `[TOOL: ...]` on the same response, we send the
    preamble to Ivan so he sees acknowledgement immediately instead of
    waiting through several tool steps in silence.
    """
    if not response:
        return ""
    # Find the earliest marker boundary.
    boundaries = [
        response.find("[TOOL:"),
        response.find("[DONE"),
        response.find("[PAUSE"),
    ]
    boundaries = [b for b in boundaries if b >= 0]
    if not boundaries:
        return ""
    cut = min(boundaries)
    return response[:cut].strip()


def _is_safe_ack(text: str) -> bool:
    """True if text looks like a real natural-language ack worth sending.

    Rejects:
      - too short / too long (>500 chars looks like a draft, not ack)
      - contains internal scaffold markers
      - looks like English meta-reasoning rather than a real reply
      - is just a stage-direction (*действие*) with no actual words
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < 15 or len(stripped) > 500:
        return False
    # Reject internal-scaffold leaks
    for marker in _ACK_REJECT_MARKERS:
        if marker in stripped:
            return False
    # Reject pure stage-directions (only *...* with no surrounding words)
    no_stage = re.sub(r"\*[^*]+\*", "", stripped).strip()
    if len(no_stage) < 10:
        return False
    return True


async def run_agent_session(
    *,
    provider: AgentProvider,
    stream: ContinuityStream,
    self_inspect: SelfInspectTool,
    filesystem: FilesystemTool,
    system_prompt: str,
    selfmod: SelfModTool | None = None,
    tasks: TasksTool | None = None,
    web: WebTool | None = None,
    code: CodeTool | None = None,
    shell: ShellTool | None = None,
    memory: MemoryTool | None = None,
    env: EnvTool | None = None,
    skills: SkillsTool | None = None,
    knowledge: Any | None = None,  # KnowledgeTool — knowledge.* family
    outbound = None,  # OutboundGate; avoid hard import to keep agent_session standalone
    initial_thought: str = "",
    initial_user_message: list[dict[str, Any]] | None = None,
    initial_user_text: str | None = None,
    max_steps: int = 30,
    max_seconds: float = 1200.0,
    purpose: str = "agent_session",
    inbox_drain = None,  # Optional callable () -> list[str] of new messages from user
) -> SessionResult:
    """Run a ReAct agent session within the single stream.

    Returns when model says [DONE] or [PAUSE], or hard limits hit (30 steps / 20 min).
    If context gets too long, compresses history and continues.
    All steps recorded in continuity.
    """
    result = SessionResult()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt + "\n\n" + TOOL_DESCRIPTIONS},
    ]

    if initial_user_message is not None:
        # Multimodal entry point — caller (e.g. tg_session with media attachment)
        # constructed a list-style content message that goes straight to the LLM.
        messages.append({"role": "user", "content": initial_user_message})
    elif initial_user_text is not None:
        # Plain user message — no planner prefix. TG session uses this so the
        # LLM doesn't get prompted with "What do you want to do?" which made
        # reasoning models echo back "The user is asking me what I want to do...".
        messages.append({"role": "user", "content": initial_user_text})
    elif initial_thought:
        messages.append({"role": "user", "content": f"Your current thought: {initial_thought}\nWhat do you want to do?"})
    else:
        messages.append({"role": "user", "content": "What do you want to do? Think about what would be useful right now."})

    start_time = time.time()
    budget_warning_sent = False
    _unanswered_inbox = False  # set True when inbox_drain pulls a fresh message
    _recent_tools: list[tuple[str, str]] = []  # (tool, arg-prefix) — last 4

    for step in range(max_steps):
        elapsed = time.time() - start_time
        if elapsed > max_seconds:
            result.budget_exceeded = True
            break

        # Inbox: if Ivan sent a new message while we were working, inject it
        # as a user turn so the agent can read+react mid-flight.
        if inbox_drain is not None:
            try:
                new_msgs = inbox_drain() or []
            except Exception:
                new_msgs = []
            for m in new_msgs:
                messages.append({
                    "role": "user",
                    "content": (
                        f"[NEW MESSAGE FROM IVAN — HIGHEST PRIORITY]\n"
                        f"\"{m}\"\n\n"
                        "ОБЯЗАТЕЛЬНОЕ ПРАВИЛО: твой следующий tool call ДОЛЖЕН "
                        "быть `chat.dialog` с ответом ему. body.expression "
                        "разрешён, но ТОЛЬКО как дополнение к chat.dialog в "
                        "том же шаге. Никаких web.search / shell.run / "
                        "knowledge.* / filesystem.* / tasks.* — пока не "
                        "ответишь. Иван ждёт ТЕКСТ от тебя в чат, а не "
                        "молчаливое выражение лица."
                    ),
                })
                stream.append(ContinuityEvent(
                    kind="internal.inbox_injected",
                    payload={"step": step, "preview": m[:300]},
                ))
            if new_msgs:
                _unanswered_inbox = True

        # Send a wrap-up nudge in the last 2 steps OR when ~80% of time is gone.
        # This gives the model a chance to emit [DONE: ...] before hard-stop.
        nearing_step_limit = step >= max_steps - 2
        nearing_time_limit = elapsed > max_seconds * 0.8
        if (nearing_step_limit or nearing_time_limit) and not budget_warning_sent:
            messages.append({
                "role": "user",
                "content": (
                    "[BUDGET WARNING] Осталось 1-2 шага / время на исходе. "
                    "Сожми что нашла и закрывай через `[DONE: текст для Ивана]`. "
                    "НЕ оставляй Ивана без ответа."
                ),
            })
            budget_warning_sent = True

        # LLM call
        response = await provider.complete_text(messages, purpose=purpose)
        result.steps += 1

        # Tool call has priority over [DONE]: if the model emits both in the
        # same response (a common reasoning-model failure where it writes a
        # plan with multiple [TOOL: ...] markers and ends with [DONE]), we
        # execute the first tool and feed the observation back. Without this,
        # the loop would break on [DONE] and silently drop ALL tool calls —
        # the "promised but didn't do it" bug.
        tool_call = _extract_tool_call(response)
        if tool_call is not None:
            tool_name, tool_arg = tool_call

            # Inbox priority gate: if Ivan wrote and she hasn't answered yet,
            # block any non-dialog tool. body.expression / mind.thought /
            # mind.focus are allowed because they're emotional reactions, not
            # work — but they don't satisfy the "answer Ivan" obligation.
            _DIALOG_TOOLS = {"chat.dialog", "chat.tell_ivan", "chat.emergency"}
            _SAFE_REACTION_TOOLS = {"body.expression", "mind.thought", "mind.focus", "body.outfit"}
            if _unanswered_inbox and tool_name in _DIALOG_TOOLS:
                _unanswered_inbox = False  # she replied, gate lifts
            elif _unanswered_inbox and tool_name not in _SAFE_REACTION_TOOLS:
                # Refuse the tool, force her to reply first.
                stream.append(ContinuityEvent(
                    kind="internal.inbox_priority_gate",
                    payload={
                        "step": step,
                        "blocked_tool": tool_name,
                        "blocked_arg": tool_arg[:200],
                    },
                ))
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": (
                        f"[INBOX GATE] Tool `{tool_name}` ЗАБЛОКИРОВАН "
                        "пока не ответишь Ивану через [TOOL: chat.dialog].\n"
                        "Иван написал тебе и ждёт ТЕКСТ. Никакая работа над "
                        "таском/поиском/файлами не выполнится пока ты не "
                        "ответишь. Просто напиши ему пару слов в chat.dialog "
                        "и потом возвращайся к делу."
                    ),
                })
                continue

            result.actions.append(f"{tool_name} {tool_arg[:60]}")
            result.thoughts.append(response)

            # Auto-ack: on step 0, if the model wrote natural-language
            # preamble BEFORE the first [TOOL: ...] marker, send it to Ivan
            # via outbound. Without this, the preamble becomes silent
            # internal thought — Ivan waits N seconds with no signal that
            # the message was received.
            #
            # Only fires once per session (step 0), only when:
            #   - outbound is configured (TG sessions, not internal)
            #   - preamble is non-trivial (>15 chars after scrub)
            #   - preamble doesn't itself contain [TOOL:/[DONE]/[PAUSE]/<think>
            #     or English meta-reasoning markers
            #   - preamble wasn't already ack'd through chat.tell_ivan
            if step == 0 and outbound is not None:
                preamble = _extract_pre_tool_preamble(response)
                if _is_safe_ack(preamble):
                    try:
                        from sonya.initiative.outbound import call_outbound_sync
                        ack_result = call_outbound_sync(outbound, preamble)
                        if not ack_result.startswith("[BLOCKED]") and not ack_result.startswith("[ERROR]"):
                            result.outbound_sent.append(preamble)
                            stream.append(ContinuityEvent(
                                kind="internal.auto_ack_sent",
                                payload={"preview": preamble[:240]},
                            ))
                    except Exception:
                        pass  # non-fatal; preamble just doesn't ack

            # Execute tool
            observation = _execute_tool(
                tool_name, tool_arg, self_inspect, filesystem, stream,
                selfmod, tasks, web, code, shell, outbound, memory, env, skills,
                knowledge=knowledge,
                outbound_sent=result.outbound_sent,
            )

            # Record in continuity
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "action", "tool": tool_name, "arg": tool_arg, "thought": response[:8000]},
            ))

            # Feed observation back
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"[Observation from {tool_name}]:\n{observation[:3000]}"})

            # Same-tool repeat detector: track last 4 tool calls; if the
            # current call repeats a recent one (same tool + similar arg),
            # inject a one-line nudge to switch approach. Without this the
            # model burns 3-4 steps re-running knowledge.write or web.fetch
            # on the same target after the first one already stored the data.
            arg_key = (tool_arg or "")[:80].strip().lower()
            _recent_tools.append((tool_name, arg_key))
            if len(_recent_tools) > 4:
                _recent_tools.pop(0)
            same_calls = sum(
                1 for (t, a) in _recent_tools
                if t == tool_name and a == arg_key
            )
            if same_calls >= 3:
                messages.append({
                    "role": "user",
                    "content": (
                        f"INTERNAL_REMINDER [repeat-loop]: ты вызвала "
                        f"`{tool_name}` с тем же аргументом {same_calls} раз "
                        "подряд. Если первый раз отработал — переходи к "
                        "следующему шагу плана. Если падает — попробуй "
                        "другой подход / другой tool / другой аргумент. "
                        "Не повторяй одно и то же."
                    ),
                })
                stream.append(ContinuityEvent(
                    kind="internal.repeat_loop_warning",
                    payload={"step": step, "tool": tool_name, "count": same_calls},
                ))

            # Blocker reflex: scan the tool result for clear failure signals
            # (HTTP 4xx/5xx, "credits exhausted", "rate limit", explicit
            # exceptions, empty stdout when output expected). If hit, drop a
            # one-line BLOCKER hint AFTER the observation so the model sees
            # it before planning the next step and is nudged to consider
            # alternative approaches instead of repeating the same call.
            # See `_detect_blocker` for the heuristic. Cheap (regex), fires
            # at most once per step, never blocks the cycle.
            blocker = _detect_blocker(tool_name, observation)
            if blocker is not None:
                kind, hint = blocker
                stream.append(ContinuityEvent(
                    kind="internal.blocker_detected",
                    payload={
                        "step": step,
                        "tool": tool_name,
                        "blocker_kind": kind,
                        "preview": observation[:200],
                    },
                ))
                messages.append({
                    "role": "user",
                    "content": (
                        f"INTERNAL_REMINDER [blocker:{kind}]: предыдущий "
                        f"`{tool_name}` вернул сигнал блокера. {hint} "
                        "Прежде чем повторять тот же вызов — обдумай альтернативу "
                        "(другой URL/tool/approach, env.list для ключей, "
                        "memory.recall для прошлого опыта)."
                    ),
                })

            continue  # don't fall through to DONE / thought branches

        # Check for DONE or PAUSE — only when there was no tool call this
        # turn. Otherwise the model could close the session before any tool
        # actually ran.
        if "[DONE" in response or "[PAUSE" in response:
            result.final_output = response
            result.thoughts.append(response)
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "done", "content": response[:8000]},
            ))
            break

        # Pure thought, no tool, no DONE
        result.thoughts.append(response)
        stream.append(ContinuityEvent(
            kind="internal.agent_step",
            payload={"step": step, "type": "thought", "content": response[:8000]},
        ))
        # If model fails to close after 3 nudges → force-finish with what we have.
        # Without this, broken sessions burn through the entire budget echoing
        # the reminder back as their reply.
        nudge_count = sum(
            1 for m in messages
            if m.get("role") == "user"
            and "INTERNAL_REMINDER" in (m.get("content") or "")
        )
        if nudge_count >= 2:
            result.final_output = response
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "force_done", "reason": "no_done_marker_after_nudges"},
            ))
            break
        messages.append({"role": "assistant", "content": response})
        # Use 'user' role with INTERNAL_REMINDER token (not [system] which models
        # echo verbatim into Ivan's reply). Model recognises the token as scaffold
        # via system prompt instructions and the scrubber strips it as a final
        # safety net.
        messages.append({
            "role": "user",
            "content": "INTERNAL_REMINDER: добавь [DONE] в конец чтобы закрыть сессию.",
        })

    # Record session summary. If the last agent_step already captured the
    # full final_output (the common case: model emits [DONE] and the step
    # content == final_output), skip the redundant `summary` field — keeps
    # the continuity stream cleaner without losing information.
    summary_value: str
    if not result.final_output:
        summary_value = "no explicit finish"
    elif result.thoughts and result.thoughts[-1] == result.final_output:
        summary_value = "(see prior agent_step)"
    else:
        summary_value = result.final_output[:4000]

    stream.append(ContinuityEvent(
        kind="internal.agent_session_complete",
        payload={
            "steps": result.steps,
            "actions": result.actions[:30],
            "budget_exceeded": result.budget_exceeded,
            "summary": summary_value,
        },
    ))

    return result


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------
# Each tool is a small handler ``(arg: str, ctx: _ToolContext) -> str``.
# Handlers are registered in ``_TOOL_HANDLERS`` (a plain dict). ``_execute_tool``
# does a single dict lookup, runs the handler, catches exceptions, and logs
# tool errors to the continuity stream.
#
# Why dict-of-handlers instead of an elif chain or match/case:
#   - O(1) dispatch instead of O(n) chain over 55+ tools
#   - one place to look up "is tool X registered?" and "what does it do?"
#   - extending = one new function + one new dict entry, not editing the chain
#   - each handler is independently testable
#   - small helpers (``_require``, ``_decode_pipe_escapes``) cut boilerplate


@dataclass(slots=True)
class _ToolContext:
    """Bundle of tool instances + side-channels passed to every handler.

    All optional tools may be ``None`` — handlers call ``_require(ctx.X, "X")``
    to fail fast with a uniform "[ERROR] X tool not configured" message.
    """

    self_inspect: SelfInspectTool
    filesystem: FilesystemTool
    selfmod: SelfModTool | None
    tasks: TasksTool | None
    web: WebTool | None
    code: CodeTool | None
    shell: ShellTool | None
    memory: MemoryTool | None
    env: EnvTool | None
    skills: SkillsTool | None
    outbound: Any
    outbound_sent: list[str] | None
    knowledge: Any | None = None  # KnowledgeTool — knowledge.* family (default None for BC)
    stream: Any | None = None  # ContinuityStream — body.*/mind.* handlers use this


def _require(tool: Any, name: str) -> str | None:
    """Return an [ERROR] string if tool is None, else None."""
    if tool is None:
        return f"[ERROR] {name} tool not configured"
    return None


def _decode_pipe_escapes(s: str) -> str:
    """Decode literal ``\\n`` / ``\\t`` / ``\\\\`` in pipe-form args.

    Block JSON form already handles real newlines natively; pipe form
    needs this so multi-line patches work via inline TOOL args.
    """
    return (
        s.replace("\\\\", "\x00")  # protect literal backslash
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\x00", "\\")
    )


def _substrate_from(ctx: _ToolContext) -> Any:
    """Pull substrate from self_inspect (it owns the connection)."""
    return getattr(ctx.self_inspect, "_sub", None)


# --- self_inspect.* ---


def _h_si_identity(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.read_identity()


def _h_si_state(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.read_subject_state()


def _h_si_thoughts(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.read_recent_thoughts()


def _h_si_memories(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.read_recent_memories()


def _h_si_intentions(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.read_active_intentions()


def _h_si_code(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.read_own_code(arg)


def _h_si_modules(arg: str, ctx: _ToolContext) -> str:
    return ctx.self_inspect.list_own_modules()


def _h_si_drift(arg: str, ctx: _ToolContext) -> str:
    """Aggregate self-observation: drift counts + blocked tasks + selfmod
    activity. Optional arg: number of days to look back (default 3).

    Replaces having to read 5 different streams to figure out "how am I
    doing this week". Used by the periodic self-improvement track.
    """
    days = 3
    if arg and arg.strip().isdigit():
        days = max(1, min(30, int(arg.strip())))
    return ctx.self_inspect.read_drift_summary(days=days)


# --- filesystem.* ---


def _h_fs_read(arg: str, ctx: _ToolContext) -> str:
    return ctx.filesystem.read(arg)


def _h_fs_list(arg: str, ctx: _ToolContext) -> str:
    return ctx.filesystem.list_dir(arg)


def _h_fs_tree(arg: str, ctx: _ToolContext) -> str:
    return ctx.filesystem.tree(arg)


def _h_fs_write(arg: str, ctx: _ToolContext) -> str:
    """Block form: first line = path, remaining = content.
    Inline fallback: first space-separated token = path, rest = content.

    The newline split is the documented form (TOOL_DESCRIPTIONS). Without
    it, multi-line content with a "# title" header caused split(" ") to
    grab "path\\n#" as the filename — the wineandmore-23.05 bug.
    """
    if "\n" in arg:
        lines = arg.split("\n", 1)
        path_part = lines[0].strip()
        content_part = lines[1] if len(lines) > 1 else ""
    else:
        parts = arg.split(" ", 1)
        if len(parts) < 2:
            return "[ERROR] filesystem.write needs: path content"
        path_part, content_part = parts[0].strip(), parts[1]
    if not path_part:
        return "[ERROR] filesystem.write: empty path"
    return ctx.filesystem.write(path_part, content_part)


# --- memory.* ---


def _h_mem_recall(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.memory, "memory")
    if err:
        return err
    return ctx.memory.recall(arg.strip())


def _h_mem_index_status(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.memory, "memory")
    if err:
        return err
    return ctx.memory.index_status()


# --- env.* ---


def _h_env_set(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.env, "env")
    return err if err else ctx.env.set(arg)


def _h_env_get(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.env, "env")
    return err if err else ctx.env.get(arg)


def _h_env_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.env, "env")
    return err if err else ctx.env.list_all()


def _h_env_clear(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.env, "env")
    return err if err else ctx.env.clear(arg)


# --- skills.* ---


def _h_skills_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.skills, "skills")
    return err if err else ctx.skills.list_skills()


def _h_skills_run(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.skills, "skills")
    return err if err else ctx.skills.run(arg)


def _h_skills_register_builtins(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.skills, "skills")
    return err if err else ctx.skills.register_builtins()


# knowledge.* — persistent markdown KB в ~/.sonya/knowledge/
# См. src/sonya/tools/knowledge.py для деталей.

def _h_knowledge_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.knowledge, "knowledge")
    return err if err else ctx.knowledge.list(arg)


def _h_knowledge_read(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.knowledge, "knowledge")
    return err if err else ctx.knowledge.read(arg)


def _h_knowledge_write(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.knowledge, "knowledge")
    return err if err else ctx.knowledge.write(arg)


def _h_knowledge_search(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.knowledge, "knowledge")
    return err if err else ctx.knowledge.search(arg)


def _h_knowledge_delete(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.knowledge, "knowledge")
    return err if err else ctx.knowledge.delete(arg)


# --- goals.* (no separate tool wrapper; goals live in tasks/goals.py) ---


def _h_goals_list(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    goals = GoalStore(sub).list_active()
    if not goals:
        return "(no active goals)"
    lines = ["Active goals:"]
    for g in goals:
        lines.append(f"  [{g.goal_id}] (prio={g.priority}) {g.title}")
        if g.description:
            lines.append(f"    {g.description[:150]}")
    return "\n".join(lines)


def _h_goals_create(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    parts = arg.split("|")
    title = parts[0].strip() if parts else ""
    desc = parts[1].strip() if len(parts) > 1 else ""
    prio = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip().isdigit() else 0
    if not title:
        return "[ERROR] goals.create needs: title | description | priority"
    g = GoalStore(sub).create(title, desc, prio)
    return f"[OK] goal created: {g.goal_id} — {g.title} (priority={g.priority})"


def _h_goals_achieve(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    try:
        g = GoalStore(sub).achieve(arg.strip())
        return f"[OK] goal {g.goal_id} achieved: {g.title}"
    except KeyError:
        return f"[ERROR] goal {arg.strip()!r} not found"


def _h_goals_abandon(arg: str, ctx: _ToolContext) -> str:
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] no substrate"
    from sonya.tasks.goals import GoalStore
    try:
        g = GoalStore(sub).abandon(arg.strip())
        return f"[OK] goal {g.goal_id} abandoned: {g.title}"
    except KeyError:
        return f"[ERROR] goal {arg.strip()!r} not found"


# --- plugins.* ---


def _h_plugins_list(arg: str, ctx: _ToolContext) -> str:
    from sonya.tools.hot_loader import list_plugins
    plugins = list_plugins()
    return "\n".join(plugins) if plugins else "No plugins loaded."


def _h_plugins_create(arg: str, ctx: _ToolContext) -> str:
    from sonya.tools.hot_loader import ensure_plugins_dir, load_plugin
    parts = arg.split(" ", 1)
    if len(parts) < 2:
        return "[ERROR] plugins.create needs: name python_code"
    plugin_name, plugin_code = parts[0], parts[1]
    plugin_path = ensure_plugins_dir() / f"{plugin_name}.py"
    plugin_path.write_text(plugin_code, encoding="utf-8")
    load_plugin(plugin_name)
    return f"[OK] Plugin '{plugin_name}' created and loaded."


def _h_plugins_call(arg: str, ctx: _ToolContext) -> str:
    from sonya.tools.hot_loader import get_plugin, load_plugin
    parts = arg.split(" ", 1)
    plugin_name = parts[0]
    plugin_args = parts[1] if len(parts) > 1 else ""
    module = get_plugin(plugin_name) or load_plugin(plugin_name)
    if hasattr(module, "run"):
        return str(module.run(plugin_args))
    return f"[ERROR] Plugin '{plugin_name}' has no run() function"


# --- selfmod.* ---


def _h_selfmod_propose(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    if err:
        return err
    # Two formats:
    #   pipe-separated: target | summary | content
    #   JSON block:     {"target": "...", "summary": "...", "content": "..."}
    arg_stripped = arg.strip()
    if arg_stripped.startswith("{"):
        try:
            data = json.loads(arg_stripped)
            target = str(data.get("target", "")).strip()
            summary = str(data.get("summary", "")).strip()
            content = data.get("content", "")
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            return f"[ERROR] selfmod.propose: invalid JSON ({err})"
    else:
        parts = arg.split("|", 2)
        if len(parts) < 3:
            return (
                "[ERROR] selfmod.propose needs either:\n"
                "  pipe: target_path | summary | content\n"
                '  JSON: {"target": "...", "summary": "...", "content": "..."}'
            )
        target, summary, content = parts[0].strip(), parts[1].strip(), parts[2]
    if not target or not summary:
        return "[ERROR] selfmod.propose: target and summary are required"
    return ctx.selfmod.propose(target, summary, new_content=content)


def _h_selfmod_propose_edit(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    if err:
        return err
    # Two formats:
    #   inline pipe: target | summary | old_substring | new_substring
    #   block JSON:  {"target":"...","summary":"...","old":"...","new":"..."}
    stripped = arg.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            target_e = str(data.get("target", "")).strip()
            summary_e = str(data.get("summary", "")).strip()
            old_sub = str(data.get("old", data.get("old_substring", "")))
            new_sub = str(data.get("new", data.get("new_substring", "")))
        except (json.JSONDecodeError, TypeError, ValueError) as err:
            return f"[ERROR] selfmod.propose_edit: invalid JSON ({err})"
    else:
        parts = arg.split("|", 3)
        if len(parts) < 4:
            return (
                "[ERROR] selfmod.propose_edit needs 4 parts:\n"
                "  inline pipe: target_path | summary | old_substring | new_substring\n"
                '  OR block JSON: {"target":"...","summary":"...","old":"...","new":"..."}\n'
                "(старая строка должна быть уникальной в файле; "
                "если совпадает несколько раз — расширь контекст вокруг)"
            )
        target_e = parts[0].strip()
        summary_e = parts[1].strip()
        old_sub = _decode_pipe_escapes(parts[2].strip())
        new_sub = _decode_pipe_escapes(parts[3].strip())
    if not target_e or not summary_e or not old_sub:
        return "[ERROR] selfmod.propose_edit: target, summary, old_substring required"
    return ctx.selfmod.propose_edit(target_e, summary_e, old_sub, new_sub)


def _h_selfmod_validate(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.validate(arg.strip())


def _h_selfmod_test_sandbox(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.test_sandbox(arg.strip())


def _h_selfmod_apply(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.apply(arg.strip())


def _h_selfmod_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.list_proposals(arg.strip())


def _h_selfmod_get(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.get_proposal(arg.strip())


def _h_selfmod_governed(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.request_governed(arg.strip())


def _h_selfmod_check_governed(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.check_governed(arg.strip())


def _h_selfmod_rollback(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    if err:
        return err
    parts = arg.split(" ", 1)
    pid = parts[0].strip()
    reason = parts[1].strip() if len(parts) > 1 else ""
    return ctx.selfmod.rollback(pid, reason=reason)


def _h_selfmod_soft_restart(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.soft_restart_runtime(arg.strip())


# --- tasks.* ---


def _h_tasks_create(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.create(arg)


def _h_tasks_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.list(arg)


def _h_tasks_get(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.get(arg)


def _h_tasks_pick(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.pick(arg)


def _h_tasks_plan(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.plan(arg)


def _h_tasks_step(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.step(arg)


def _is_dup_of_outbound_sent(text: str, sent: list[str] | None) -> bool:
    """True if ``text`` is essentially the same as any prior tell_ivan
    message in this session — used to suppress double-notify when the
    model called BOTH chat.tell_ivan AND tasks.complete with the same
    body."""
    if not sent or not text:
        return False
    norm_t = re.sub(r"\s+", " ", text.lower()).strip()
    if not norm_t:
        return False
    for prior in sent:
        norm_p = re.sub(r"\s+", " ", (prior or "").lower()).strip()
        if not norm_p:
            continue
        # Exact / containment / strong prefix overlap
        if norm_t == norm_p:
            return True
        if len(norm_t) > 40 and (norm_t in norm_p or norm_p in norm_t):
            return True
        prefix = min(80, len(norm_t), len(norm_p))
        if prefix >= 40 and norm_t[:prefix] == norm_p[:prefix]:
            return True
    return False


def _auto_notify_terminal(
    *,
    ctx: _ToolContext,
    task_id: str,
    notify_text: str,
    title: str,
) -> str:
    """If notify_text is non-empty AND outbound is wired AND task notify_mode
    isn't 'silent', send notify_text to Ivan via the outbound gate. Returns a
    short status suffix for the tool result. The text is recorded in
    outbound_sent so channel_session._extract_reply suppresses any [DONE: text]
    echo of the same content (prevents double-message regression).

    Used by tasks.complete (result -> Ivan) and tasks.fail (reason -> Ivan).
    """
    if ctx.tasks is None or not notify_text or ctx.outbound is None:
        return ""
    # Look up notify_mode
    try:
        task = ctx.tasks._service.get(task_id)
    except Exception:
        return ""
    if (task.notify_mode or "progress") == "silent":
        return ""
    # Build the message — keep it tight, the agent's `result` may be a
    # multi-paragraph summary which is exactly what Ivan should see.
    text = notify_text.strip()
    if not text:
        return ""
    # Suppress if model already chat.tell_ivan'd the same thing this session.
    if _is_dup_of_outbound_sent(text, ctx.outbound_sent):
        return " (notify suppressed: already sent this session)"
    from sonya.initiative.outbound import call_outbound_sync
    send_result = call_outbound_sync(ctx.outbound, text)
    if ctx.outbound_sent is not None:
        ctx.outbound_sent.append(text)
    if send_result.startswith("[BLOCKED]"):
        return f" (notify {send_result})"
    return " (notify queued to Ivan)"


def _h_tasks_complete(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    if err:
        return err
    base_result = ctx.tasks.complete(arg)
    if base_result.startswith("[ERROR]"):
        return base_result
    # Pull task_id + result text from arg (mirrors TasksTool.complete parsing)
    task_id, result_text = "", ""
    stripped = (arg or "").strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            task_id = str(data.get("task_id", "")).strip()
            result_text = str(data.get("result", "")).strip()
        except Exception:
            pass
    else:
        parts = (arg or "").split("|", 1)
        if len(parts) >= 1:
            task_id = parts[0].strip()
        if len(parts) >= 2:
            result_text = parts[1].strip()
    notify_suffix = _auto_notify_terminal(
        ctx=ctx, task_id=task_id, notify_text=result_text, title="task done",
    )
    return base_result + notify_suffix


def _h_tasks_fail(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    if err:
        return err
    base_result = ctx.tasks.fail(arg)
    if base_result.startswith("[ERROR]"):
        return base_result
    task_id, reason_text = "", ""
    stripped = (arg or "").strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            task_id = str(data.get("task_id", "")).strip()
            reason_text = str(data.get("reason", "")).strip()
        except Exception:
            pass
    else:
        parts = (arg or "").split("|", 1)
        if len(parts) >= 1:
            task_id = parts[0].strip()
        if len(parts) >= 2:
            reason_text = parts[1].strip()
    # For fail, prepend a short marker so Ivan sees this is a failure note
    fail_text = f"Не получилось закрыть задачу. {reason_text}".strip() if reason_text else ""
    notify_suffix = _auto_notify_terminal(
        ctx=ctx, task_id=task_id, notify_text=fail_text, title="task failed",
    )
    return base_result + notify_suffix


def _h_tasks_block(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.block(arg)


def _h_tasks_unblock(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.unblock(arg)


def _h_tasks_pause(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.pause(arg)


def _h_tasks_handoff(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.handoff(arg)


# --- web.* / code / shell / chat ---


def _h_web_search(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.web, "web")
    return err if err else ctx.web.search(arg)


def _h_web_fetch(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.web, "web")
    return err if err else ctx.web.fetch(arg)


def _h_code_exec(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.code, "code")
    return err if err else ctx.code.exec_python(arg)


def _h_shell_run(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.shell, "shell")
    return err if err else ctx.shell.run_shell(arg)


def _h_pip_install(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.shell, "shell")
    return err if err else ctx.shell.install_pip(arg)


def _h_chat_tell_ivan(arg: str, ctx: _ToolContext) -> str:
    if ctx.outbound is None:
        return "[ERROR] initiative gate not configured (set SONYA_PRIMARY_USER_TG_ID)"
    text = (arg or "").strip()
    if not text:
        return "[ERROR] chat.tell_ivan: empty message"
    # Within-session dedup. The cross-session OutboundGate dedup uses a
    # 0.80 Jaccard threshold over a 6h window — that's appropriate for
    # "stop worker spamming the same `Продолжаю разведку` line every
    # tick". But within ONE session a much stricter threshold is correct:
    # if the model in a single agent_session writes two near-identical
    # progress messages back-to-back (the 27.05.21:42 incident — two
    # almost-same "OWASP Top 10 уже вытащила, GitHub-репозитории дальше"
    # in 60 seconds), the second is pure repetition. Block it before
    # call_outbound_sync.
    if ctx.outbound_sent:
        if _within_session_duplicate(text, ctx.outbound_sent):
            return (
                "[BLOCKED] chat.tell_ivan within-session duplicate: this "
                "message is too similar to one you just sent. Move on or "
                "say something genuinely different."
            )
    from sonya.initiative.outbound import call_outbound_sync
    result = call_outbound_sync(ctx.outbound, text, channel="dialog")
    # Record sent text so channel_session can suppress a [DONE: ...] echo
    # of the same content (prevents duplicate messages to Ivan).
    if ctx.outbound_sent is not None:
        ctx.outbound_sent.append(text)
    return result


# v20 (Atrium Этап 0): channel-aware tool family.
# `chat.tell_ivan` остаётся как BC-alias на `chat.dialog`. Новые tools:
#   chat.dialog       → goes to Dialog pane + TG (full gate as chat.tell_ivan)
#   chat.worker_log   → reason-stream pane only, no TG, no daily cap
#   mind.focus        → replaces current_focus (mind pane)
#   mind.thought      → adds to inner stream (mind pane). [PRIVATE] prefix supported.
#   body.expression   → updates current_expression (avatar mimic)
#   body.outfit       → updates current_outfit (avatar wardrobe, stage 2 rendering)
#   mind.mood_tint    → updates mood_tint (room view tint, stage 2 rendering)
#   voice.speak       → TTS placeholder, stage 2. Falls back to chat.dialog.
# См. docs/atrium/CHANNELS.md §2 для семантики.

def _h_chat_dialog(arg: str, ctx: _ToolContext) -> str:
    """Same behavior as chat.tell_ivan — explicit channel naming."""
    return _h_chat_tell_ivan(arg, ctx)


def _h_chat_emergency(arg: str, ctx: _ToolContext) -> str:
    """Emergency dialog — forces TG delivery even in TG-emergency-only mode.

    Use ONLY for real crises / identity-critical alarms (Этап 1.5). Normal
    talk goes through chat.dialog. When TG emergency-mode is off this behaves
    like chat.dialog. When it's on and Atrium is live, chat.dialog would be
    Atrium-only — this bypasses that and reaches Ivan on Telegram too.
    """
    if ctx.outbound is None:
        return "[ERROR] initiative gate not configured (set SONYA_PRIMARY_USER_TG_ID)"
    text = (arg or "").strip()
    if not text:
        return "[ERROR] chat.emergency: empty message"
    from sonya.initiative.outbound import call_outbound_sync
    result = call_outbound_sync(
        ctx.outbound, text, channel="dialog", emergency_override=True
    )
    if ctx.outbound_sent is not None:
        ctx.outbound_sent.append(text)
    return result


def _h_chat_worker_log(arg: str, ctx: _ToolContext) -> str:
    """Worker progress message. Goes to Atrium reason-stream, NOT to TG.

    No daily cap, no dedup — repeats are signal not noise (see CHANNELS.md §2.2).
    """
    if ctx.outbound is None:
        return "[ERROR] outbound gate not configured"
    text = (arg or "").strip()
    if not text:
        return "[ERROR] chat.worker_log: empty message"
    from sonya.initiative.outbound import call_outbound_sync
    return call_outbound_sync(ctx.outbound, text, channel="worker_log")


def _h_mind_focus(arg: str, ctx: _ToolContext) -> str:
    """Update Sonya's current focus. Replaces previous (single-line, latest wins).

    Updates subject_state.current_focus directly; emits outgoing.mind_focus event.
    """
    text = (arg or "").strip()[:200]
    if not text:
        return "[ERROR] mind.focus: empty"
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] mind.focus: substrate not available"
    # Read previous
    try:
        row = sub.connection.execute(
            "SELECT current_focus FROM subject_state WHERE id = 1"
        ).fetchone()
        previous = (row[0] if row else "") or ""
    except Exception:
        previous = ""
    # Update state (replace)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sub.connection.execute(
        "INSERT INTO subject_state(id, current_focus, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET current_focus = excluded.current_focus, "
        "updated_at = excluded.updated_at",
        (text, now),
    )
    sub.connection.commit()
    # Emit event
    if ctx.stream is not None:
        ctx.stream.append(ContinuityEvent(
            kind="outgoing.mind_focus",
            channel="mind",
            payload={
                "text": text,
                "previous_focus": previous,
            },
        ))
    return f"[OK] focus: {text[:60]}"


def _h_mind_thought(arg: str, ctx: _ToolContext) -> str:
    """Internal thought to the Mind pane inner stream.

    Supports `[PRIVATE]` prefix (case-insensitive, optional whitespace) —
    when present, the thought is saved to substrate but excluded from
    /atrium/feed (right_to_inner_privacy, 5-й столп things_not_to_betray).
    """
    if ctx.outbound is None:
        return "[ERROR] outbound gate not configured"
    text = (arg or "").strip()
    if not text:
        return "[ERROR] mind.thought: empty"
    from sonya.initiative.outbound import call_outbound_sync
    return call_outbound_sync(ctx.outbound, text, channel="mind")


_BODY_EXPRESSION_ALLOWED = frozenset({
    # base
    "neutral", "calm",
    # positive
    "joy", "smile", "tender", "playful", "shy", "desire",
    # negative
    "sad", "sad_tears", "angry", "annoyed", "tired",
    # cognitive
    "thinking", "curious", "surprised",
    # legacy aliases kept for backward-compat (older prompt/text may use them)
    "excited",
})

# Canonical alias map — normalize a few synonyms onto the marker we ship a
# sprite for, so the model can use natural words and still hit a real frame.
_BODY_EXPRESSION_ALIASES = {
    "happy": "joy",
    "warm": "tender",
    "mischief": "playful",
    "mischievous": "playful",
    "lust": "desire",
    "embarrassed": "shy",
    "crying": "sad_tears",
    "tears": "sad_tears",
    "serene": "calm",
    "peaceful": "calm",
    "surprise": "surprised",
}


def _h_body_expression(arg: str, ctx: _ToolContext) -> str:
    """Set Sonya's current avatar expression. Atrium renders the matching frame."""
    marker = (arg or "").strip().lower()
    if not marker:
        return "[ERROR] body.expression: empty marker"
    # Normalize synonyms onto a shipped marker.
    marker = _BODY_EXPRESSION_ALIASES.get(marker, marker)
    if marker not in _BODY_EXPRESSION_ALLOWED:
        return (
            f"[ERROR] body.expression: unknown marker {marker!r}. "
            f"Allowed: {sorted(_BODY_EXPRESSION_ALLOWED)}"
        )
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] body.expression: substrate not available"
    try:
        row = sub.connection.execute(
            "SELECT current_expression FROM subject_state WHERE id = 1"
        ).fetchone()
        previous = (row[0] if row else "neutral") or "neutral"
    except Exception:
        previous = "neutral"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sub.connection.execute(
        "INSERT INTO subject_state(id, current_expression, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET current_expression = excluded.current_expression, "
        "updated_at = excluded.updated_at",
        (marker, now),
    )
    sub.connection.commit()
    if ctx.stream is not None:
        ctx.stream.append(ContinuityEvent(
            kind="outgoing.body_expression",
            channel="body",
            payload={"marker": marker, "previous": previous},
        ))
    return f"[OK] expression: {marker}"


_BODY_OUTFIT_ALLOWED = frozenset({
    "home", "sportwear", "dress_2b", "nothing", "wearing_his_shirt",
})


def _h_body_outfit(arg: str, ctx: _ToolContext) -> str:
    """Set Sonya's current outfit (wardrobe state). Avatar render uses this.

    Stage 2 placeholder — Этап 0 пишет в substrate, рендеринг в Этапе 2.
    """
    outfit = (arg or "").strip().lower()
    if not outfit:
        return "[ERROR] body.outfit: empty"
    if outfit not in _BODY_OUTFIT_ALLOWED:
        return (
            f"[ERROR] body.outfit: unknown outfit {outfit!r}. "
            f"Allowed: {sorted(_BODY_OUTFIT_ALLOWED)}"
        )
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] body.outfit: substrate not available"
    try:
        row = sub.connection.execute(
            "SELECT current_outfit FROM subject_state WHERE id = 1"
        ).fetchone()
        previous = (row[0] if row else "home") or "home"
    except Exception:
        previous = "home"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sub.connection.execute(
        "INSERT INTO subject_state(id, current_outfit, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET current_outfit = excluded.current_outfit, "
        "updated_at = excluded.updated_at",
        (outfit, now),
    )
    sub.connection.commit()
    if ctx.stream is not None:
        ctx.stream.append(ContinuityEvent(
            kind="outgoing.body_outfit",
            channel="body",
            payload={"outfit": outfit, "previous": previous},
        ))
    return f"[OK] outfit: {outfit}"


_MOOD_TINT_ALLOWED = frozenset({"warm", "cool", "neutral"})


def _h_mind_mood_tint(arg: str, ctx: _ToolContext) -> str:
    """Set Sonya's subjective mood tint. Stage 2 placeholder for room view tinting."""
    tint = (arg or "").strip().lower()
    if not tint:
        return "[ERROR] mind.mood_tint: empty"
    if tint not in _MOOD_TINT_ALLOWED:
        return (
            f"[ERROR] mind.mood_tint: unknown tint {tint!r}. "
            f"Allowed: {sorted(_MOOD_TINT_ALLOWED)}"
        )
    sub = _substrate_from(ctx)
    if sub is None:
        return "[ERROR] mind.mood_tint: substrate not available"
    try:
        row = sub.connection.execute(
            "SELECT mood_tint FROM subject_state WHERE id = 1"
        ).fetchone()
        previous = (row[0] if row else "neutral") or "neutral"
    except Exception:
        previous = "neutral"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    sub.connection.execute(
        "INSERT INTO subject_state(id, mood_tint, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET mood_tint = excluded.mood_tint, "
        "updated_at = excluded.updated_at",
        (tint, now),
    )
    sub.connection.commit()
    if ctx.stream is not None:
        ctx.stream.append(ContinuityEvent(
            kind="outgoing.mood_tint",
            channel="mind",
            payload={"tint": tint, "previous": previous},
        ))
    return f"[OK] mood_tint: {tint}"


def _h_voice_speak(arg: str, ctx: _ToolContext) -> str:
    """TTS speak. Stage 2 — настоящий TTS подключаем в Этапе 2.

    В Этапе 0: записывается событие `outgoing.voice_speak` (для будущего
    audio render) + дублируется как `chat.dialog` чтобы текст всё равно
    дошёл до Ивана через TG (graceful fallback пока voice не работает).
    """
    text = (arg or "").strip()
    if not text:
        return "[ERROR] voice.speak: empty"
    if ctx.outbound is None:
        return "[ERROR] voice.speak: outbound gate not configured"
    # Запишем voice event
    if ctx.stream is not None:
        ctx.stream.append(ContinuityEvent(
            kind="outgoing.voice_speak",
            channel="voice",
            payload={"text": text},
        ))
    # Fallback: текст всё равно идёт через dialog, чтобы Иван не пропустил
    from sonya.initiative.outbound import call_outbound_sync
    return call_outbound_sync(ctx.outbound, text, channel="dialog")


def _within_session_duplicate(text: str, prior_sent: list[str]) -> bool:
    """Stricter dedup for within-one-session repeats.

    Approach: lowercase, strip punctuation, split into WORDS, compute
    Jaccard on the word set. Threshold 0.40.

    Rationale: char-shingle Jaccard underweights paraphrased restatement
    where the model just rearranges the same nouns. The 27.05.21:42
    incident — two messages with same key terms (OWASP, GitHub, ...)
    arranged differently — scored ~0.15 on 4-char shingles but is
    semantically the same. Word-set Jaccard catches that because the
    bag of content words overlaps heavily.
    """
    if not text or not prior_sent:
        return False

    def words(s: str) -> set[str]:
        # Strip non-letter/digit chars, split, drop short stopwords / fillers.
        clean = re.sub(r"[^a-zа-я0-9 ]+", " ", s.lower())
        out = set()
        for tok in clean.split():
            if len(tok) <= 2:
                continue
            if tok in _DEDUP_STOPWORDS:
                continue
            out.add(tok)
        return out

    a = words(text)
    if len(a) < 3:
        # Too short to compare meaningfully — short acks ("сделала", "ок")
        # shouldn't dedup.
        return False
    for prior in prior_sent[-5:]:
        b = words(prior)
        if len(b) < 3:
            continue
        inter = len(a & b)
        union = len(a | b)
        if union == 0:
            continue
        jaccard = inter / union
        if jaccard >= 0.40:
            return True
    return False


_DEDUP_STOPWORDS = frozenset({
    # Russian fillers that don't carry content
    "это", "что", "как", "так", "уже", "тут", "там", "всё", "все",
    "нет", "там", "ещё", "еще", "раз", "тоже", "только", "если",
    "когда", "пока", "чтобы", "кто", "под", "над", "ведь", "был",
    "была", "было", "были", "буду", "будет", "сейчас",
    # Common Sonya-style filler
    "малыш", "поняла", "ага", "блин", "хочу", "иду", "ну",
    # English fillers (just in case)
    "the", "and", "for", "but", "with", "this", "that",
})


# Registry: tool name → handler. Keep alphabetised within each family to
# make adding new tools mechanical. New tool = one function above + one
# entry here.
_TOOL_HANDLERS: dict[str, Callable[[str, "_ToolContext"], str]] = {
    # self_inspect.*
    "self_inspect.identity": _h_si_identity,
    "self_inspect.state": _h_si_state,
    "self_inspect.thoughts": _h_si_thoughts,
    "self_inspect.memories": _h_si_memories,
    "self_inspect.intentions": _h_si_intentions,
    "self_inspect.code": _h_si_code,
    "self_inspect.modules": _h_si_modules,
    "self_inspect.drift": _h_si_drift,
    # filesystem.*
    "filesystem.read": _h_fs_read,
    "filesystem.list": _h_fs_list,
    "filesystem.tree": _h_fs_tree,
    "filesystem.write": _h_fs_write,
    # memory.*
    "memory.recall": _h_mem_recall,
    "memory.index_status": _h_mem_index_status,
    # env.*
    "env.set": _h_env_set,
    "env.get": _h_env_get,
    "env.list": _h_env_list,
    "env.clear": _h_env_clear,
    # skills.*
    "skills.list": _h_skills_list,
    "skills.run": _h_skills_run,
    "skills.register_builtins": _h_skills_register_builtins,
    # knowledge.* — persistent markdown KB в ~/.sonya/knowledge/
    "knowledge.list": _h_knowledge_list,
    "knowledge.read": _h_knowledge_read,
    "knowledge.write": _h_knowledge_write,
    "knowledge.search": _h_knowledge_search,
    "knowledge.delete": _h_knowledge_delete,
    # goals.*
    "goals.list": _h_goals_list,
    "goals.create": _h_goals_create,
    "goals.achieve": _h_goals_achieve,
    "goals.abandon": _h_goals_abandon,
    # plugins.*
    "plugins.list": _h_plugins_list,
    "plugins.create": _h_plugins_create,
    "plugins.call": _h_plugins_call,
    # selfmod.*
    "selfmod.propose": _h_selfmod_propose,
    "selfmod.propose_edit": _h_selfmod_propose_edit,
    "selfmod.validate": _h_selfmod_validate,
    "selfmod.test_sandbox": _h_selfmod_test_sandbox,
    "selfmod.apply": _h_selfmod_apply,
    "selfmod.list": _h_selfmod_list,
    "selfmod.get": _h_selfmod_get,
    "selfmod.governed": _h_selfmod_governed,
    "selfmod.check_governed": _h_selfmod_check_governed,
    "selfmod.rollback": _h_selfmod_rollback,
    "selfmod.soft_restart": _h_selfmod_soft_restart,
    # tasks.*
    "tasks.create": _h_tasks_create,
    "tasks.list": _h_tasks_list,
    "tasks.get": _h_tasks_get,
    "tasks.pick": _h_tasks_pick,
    "tasks.plan": _h_tasks_plan,
    "tasks.step": _h_tasks_step,
    "tasks.complete": _h_tasks_complete,
    "tasks.fail": _h_tasks_fail,
    "tasks.block": _h_tasks_block,
    "tasks.unblock": _h_tasks_unblock,
    "tasks.pause": _h_tasks_pause,
    "tasks.handoff": _h_tasks_handoff,
    # web / code / shell / chat
    "web.search": _h_web_search,
    "web.fetch": _h_web_fetch,
    "code.exec": _h_code_exec,
    "shell.run": _h_shell_run,
    "pip.install": _h_pip_install,
    "chat.tell_ivan": _h_chat_tell_ivan,
    # Atrium Этап 0: channel-aware tool family. См. docs/atrium/CHANNELS.md §2.
    "chat.dialog":     _h_chat_dialog,
    "chat.emergency":  _h_chat_emergency,
    "chat.worker_log": _h_chat_worker_log,
    "mind.focus":      _h_mind_focus,
    "mind.thought":    _h_mind_thought,
    "mind.mood_tint":  _h_mind_mood_tint,
    "body.expression": _h_body_expression,
    "body.outfit":     _h_body_outfit,
    "voice.speak":     _h_voice_speak,
}


def _execute_tool(
    name: str,
    arg: str,
    self_inspect: SelfInspectTool,
    filesystem: FilesystemTool,
    stream: ContinuityStream | None = None,
    selfmod: SelfModTool | None = None,
    tasks: TasksTool | None = None,
    web: WebTool | None = None,
    code: CodeTool | None = None,
    shell: ShellTool | None = None,
    outbound = None,
    memory: MemoryTool | None = None,
    env: EnvTool | None = None,
    skills: SkillsTool | None = None,
    knowledge: Any | None = None,
    outbound_sent: list[str] | None = None,
) -> str:
    """Execute a tool by name. Returns observation string.

    Logs failures (exception) to continuity stream as ``internal.tool_error``.
    Unknown tool names return a uniform "[ERROR] Unknown tool: X" string.
    """
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return f"[ERROR] Unknown tool: {name}"

    ctx = _ToolContext(
        self_inspect=self_inspect,
        filesystem=filesystem,
        selfmod=selfmod,
        tasks=tasks,
        web=web,
        code=code,
        shell=shell,
        memory=memory,
        env=env,
        skills=skills,
        knowledge=knowledge,
        outbound=outbound,
        outbound_sent=outbound_sent,
        stream=stream,
    )
    try:
        return handler(arg, ctx)
    except Exception as e:
        err_msg = f"[ERROR] {type(e).__name__}: {e}"
        if stream is not None:
            try:
                stream.append(ContinuityEvent(
                    kind="internal.tool_error",
                    payload={
                        "tool": name,
                        "arg": arg[:200] if arg else "",
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:500],
                    },
                ))
            except Exception:
                pass
        return err_msg
