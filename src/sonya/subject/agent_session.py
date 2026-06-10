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
- self_inspect.memories [since=YYYY-MM-DD] [until=YYYY-MM-DD] — read recent episodic memories (default 100). Use date args for month retrospection: `self_inspect.memories since=2026-05-01 until=2026-06-01`
- self_inspect.intentions — read active intentions
- self_inspect.code [module_path] — read your own source code (e.g. "planning/planner.py")
- self_inspect.modules — list your packages
- self_inspect.drift [days] — aggregate self-observation: drift detector hit counts (initiative_blocked, stuck_loops), blocked/failed tasks, selfmod activity, work volume. Default last 3 days. Use this every periodic self-improvement session to see your own behaviour patterns and decide what to fix in your own code via selfmod.
- memory.recall [query] — semantic search over your full episodic history (returns top-5 relevant memories with similarity score)
- memory.recall_visual [media_path] — найти похожие картинки в episodic history по perceptual hash. Принимает абсолютный путь к файлу (например /home/jester-sonya/.sonya/media/atrium_xxx.png). Возвращает топ-5 событий с дистанцией в битах (0-12 = очень похоже, 12-20 = похоже, >20 = разное).
- memory.index_status — diagnostic: how many events are embedded vs pending
- env.set [key value] — record what you observe about Ivan / context (e.g. `env.set ivan_status спит`, `env.set mood уставший`, `env.set activity работает`). Used to suppress initiative when Ivan is busy/asleep — OutboundGate respects ivan_status='спит' / 'занят'.
- env.get [key] — read a previously recorded observation
- env.list — list all current observations
- env.clear [key] — drop an observation when no longer relevant
- skills.list — show registered skills and their status
- skills.run [skill_id] [query] — execute a skill (e.g. `skills.run skill-memory-search что мы обсуждали вчера`)
- skills.register_builtins — seed built-in skills (memory-search, identity-check, dialog-tone) into registry. Call once.
- skills.register_runtime — block form, register a NEW skill from inline code. First line: `skill_id|name|purpose|trust_level`. Following lines: python source defining `def run(ctx) -> str`. Source goes to `~/.sonya/runtime_skills/<id>.py`, executor imports immediately. Re-running with same skill_id overwrites the file.

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
- plugins.create — block form: first line = name, remaining = python code.
  Plugin contract: define `def run(args): return <result>`. `args` это:
    - dict если ты вызываешь `plugins.call name {"key": "value"}` (JSON парсится автоматически)
    - list если args начинается с `[`
    - raw string иначе (`plugins.call name hello world`)
    - {} (пустой dict) если без args.
  Плагин файл живёт в src/sonya/tools/plugins/<name>.py — попадает в git
  через selfmod-pipeline и переживает рестарт. Для одноразового кода —
  используй code.exec; для нового capability который понадобится несколько
  раз — plugins.create.
- plugins.call [name] [args] — call a loaded plugin. args парсится как
  описано выше. Пример: `plugins.call email_reader {"host":"imap.gmail.com","port":993,"user":"x","pass":"y","limit":3}` → run() получит dict.
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
- selfmod.outcomes [limit_int? | improved | neutral | degraded | pending] — твоя история self-improvement: что применила, что улучшилось/нейтрально/ухудшилось через 7 дней. Смотри её, прежде чем браться за следующий selfmod — учись на собственных результатах.
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
    "max_sessions": 3,                    // optional; 0 = unlimited. After this many active sessions / worker runs, task auto-fails if not done.
    "urgency": "urgent" | "normal" | "background",   // optional; ivan-tasks default 'normal', self-tasks default 'background'
    "recurring_spec": "{\"every\": \"1d\"}"  // optional JSON; см. recurring_spec ниже
  }
  - urgency=urgent: 8 шагов / 90с window, fast worker pickup (3 min). Use when deadline ≤6h or Ivan said "сейчас же".
  - urgency=normal: 20 шагов / 5 мин window, regular worker (~30 min). Default for most Ivan-tasks.
  - urgency=background: 30 шагов / 15 мин window, picked up only when active session has nothing else. Default for self-tasks (your own ideas).
  - created_by="ivan": worker runs every ~2 min (continuous) when urgent.
  - created_by="self": picked up by active session every 2 hours (her own ideas)
  - scheduled_for=future: scheduler holds it until the time
  - notify_mode=progress: chat.tell_ivan after each step. final: only on done. silent: never.
  - max_sessions: hard budget cap. Use when Ivan says "не пытайся продолжать после N попыток".
  - recurring_spec: для повторяющихся задач. Когда current copy → DONE/FAILED, после cadence создаётся новая PENDING. Форматы: `{"every": "30m"}` (каждые 30 минут), `{"every": "1h"}`, `{"every": "1d"}` (раз в день после completed_at), `{"every": "1d", "at": "09:00"}` (каждый день в 09:00 UTC). Используй для регулярных ритуалов: "каждое утро спросить как настроение", "раз в неделю проверить балансы".
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
- code.exec — block form, code inside ```python ... ```. NOT sandboxed by path — can access ANY file the user can read, including your own runtime data (~/.sonya/sonya_substrate.db) and source (~/Sonya/src/). Use import sqlite3 to query substrate directly, or read/parse your own code for debugging. stdout is captured and returned. Timeout 30s.
- shell.run [command] — approval-gated
- pip.install [package] — approval-gated

- providers.list — твой LLM-pool: имя, статус, баланс, счётчики
- providers.models [provider?] — список доступных моделей из provider/model pool. Без аргумента — все провайдеры. С аргументом — только для одного. Используй чтобы выбрать модель под таск.
- providers.balance — суммарный баланс по провайдерам
- providers.health — синтез: OK / WARNING / CRITICAL. Используй когда видишь LLM errors или хочешь понять надо ли регать новый ключ
- providers.disable [key_id] / providers.enable [key_id]
- providers.add — JSON: {"provider","name","api_key","base_url?","model?","priority?"}
- providers.set_active [provider_name]
- providers.settings — текущие active_provider / default_model / default_base_url
- Ты можешь выбрать модель при создании субагента: передай модель из providers.models в коде который зовёт complete_text.

- browser.open [url] — Playwright headless, persistent profile в ~/.sonya/browser-profile/
- browser.click [css selector]
- browser.fill <css selector>|<value>
- browser.text [css selector] — innerText
- browser.eval [js] — выполнить JS
- browser.screenshot [path?]
- browser.wait [css selector] — до 15с
- browser.close
  Используй для JS-render, форм, login, captcha (через 2captcha-style), скриншотов, выполнения JS.
  Куки сохраняются между сессиями — логинись один раз.

- subagent.spawn — JSON: {"task": "...", "provider?": "provider_id", "model?": "model/name", "max_steps?": 8}
  Создаёт субагента который выполнит задачу в фоне. Субагент имеет доступ к web, code, memory, self_inspect.
  Это НЕ замена твоей работы — используй для параллельных задач (сбор инфы, проверка фактов, research) пока сама занята другим.
  Если provider/model не указаны, система сама выбирает лучший доступный инструмент по задаче и доступным ключам.
  Явно указывай provider/model только когда нужен конкретный backend. Результат забираешь через subagent.result.
- subagent.list — список всех субагентов (pending/running/done/failed)
- subagent.result [subagent_id] — забрать результат завершённого субагента

- chat.dialog [message] — отправить сообщение Ивану (TG + Atrium). Основной канал диалога: ответы, отчёты, прогресс. Не дросселируется в активной сессии — используй для каждого ответа ему.
- chat.tell_ivan [message] — алиас на chat.dialog. То же самое.

## How to finish

Заканчивай через `[DONE]`. Текст внутри `[DONE: <текст>]` уходит Ивану как сообщение — это короткий путь "сделала + отчиталась" одним ходом.

- **TG / Atrium диалог** (Иван написал тебе): два валидных паттерна:
  1. **Сразу к работе** — `[TOOL: ...]` без предварительного ack, потом `[DONE: <итог для Ивана>]`. Гейт пропускает работу первые ~15 шагов; обязательное условие — финал через chat.dialog ИЛИ `[DONE: text]`. Используй когда задача быстрая и осмысленный итог уместится в одно сообщение.
  2. **Ack + отчёт** — `[TOOL: chat.dialog "иду делать X"]` сначала, потом работа, потом второй chat.dialog с результатом, потом `[DONE]` (можно пустой). Используй когда работа займёт >5 шагов и Ивану важно знать что ты услышала.

- **Внутренняя сессия** (idle / cadence-fire без сообщения от Ивана): `[DONE]` без текста.

**Не копируй placeholder дословно** — впиши настоящий текст. Без [DONE] — сессия висит до budget.

**НЕ приветствуй заново** в ответ Ивану — это продолжение разговора, а не первая встреча.

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
# DONE marker with optional inline body — `[DONE: текст ответа]`.
# Matches across newlines so the body can be multi-line. Used by the
# active-session inbox gate to recognize a "DONE-as-reply" pattern:
# instead of forcing chat.dialog + [DONE], the model can finalize with
# `[DONE: <reply text>]` and that text is dispatched as her message.
# Mirrors the regex in channel_session.py for TG.
_DONE_WITH_BODY_RE = re.compile(
    r"\[DONE(?::\s*(?P<body>.+?))?\]",
    re.DOTALL,
)
# Block form: [TOOL: name]\n```optional-lang\n<arg>\n```
_TOOL_BLOCK_RE = re.compile(
    r"\[TOOL:\s*([^\s\]]+)\s*\]\s*\n```[a-zA-Z0-9_-]*\n(.*?)\n```",
    re.DOTALL,
)
# Soft block form (no code fence): [TOOL: name]\n<text>...
# Args extend until the next [TOOL:, [DONE, [PAUSE, or end of response.
# Handles the common LLM mistake of writing chat.dialog as:
#     [TOOL: chat.dialog]
#     текст ответа
# instead of `[TOOL: chat.dialog текст ответа]` (inline) or with ``` fence.
# Without this, arg is empty and the tool fires with no text.
_TOOL_SOFT_BLOCK_RE = re.compile(
    r"\[TOOL:\s*([^\s\]]+)\s*\]\s*\n([^\[]+?)(?=\[TOOL:|\[DONE|\[PAUSE|\Z)",
    re.DOTALL,
)
# Tools that legitimately take plain text args without brackets / JSON.
# Soft-block recovery only applies to these (avoids misparsing things
# like `[TOOL: filesystem.list]\n/some/path` as having a multi-line arg).
_SOFT_BLOCK_TEXT_TOOLS = frozenset({
    "chat.dialog", "chat.tell_ivan", "chat.emergency", "chat.worker_log",
    "mind.thought", "mind.focus",
    "voice.speak",
})
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


def _find_balanced_multiline_tool(response: str) -> tuple[str, str] | None:
    """Same as _find_balanced_inline_tool but allows newlines in the arg.

    Only applies to _SOFT_BLOCK_TEXT_TOOLS (chat.*, mind.*, voice.*) to
    avoid false positives on JSON/code tools. Fixes the case where the
    model writes `[TOOL: chat.dialog text

    more text]` with closing `]` on a later line.
    """
    m = _TOOL_INLINE_START_RE.search(response)
    if not m:
        return None
    tool_name = m.group(1)
    if tool_name not in _SOFT_BLOCK_TEXT_TOOLS:
        return None
    arg_start = m.end()
    depth = 1
    i = arg_start
    while i < len(response):
        ch = response[i]
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
    Soft-block (no fence) form is recovered for chat.*/mind.thought/etc.
    """
    m = _TOOL_BLOCK_RE.search(response)
    if m:
        return m.group(1), m.group(2)
    # Try bracket-balanced inline parse first (handles JSON with nested ]).
    balanced = _find_balanced_inline_tool(response)
    if balanced is not None:
        tool_name, arg = balanced
        # Empty inline arg + chat-like tool = likely the model wrote
        # block form without a fence. Fall through to soft-block to
        # recover the text on following lines.
        if arg or tool_name not in _SOFT_BLOCK_TEXT_TOOLS:
            return tool_name, arg
    # Multiline balanced: handles `[TOOL: chat.dialog text\n\nmore]`
    # where closing `]` is on a later line (inline parser aborts on \n).
    balanced_ml = _find_balanced_multiline_tool(response)
    if balanced_ml is not None:
        tool_name, arg = balanced_ml
        if arg:
            return tool_name, arg
    # Soft-block recovery: `[TOOL: name]\n<text>` for plain-text tools.
    m = _TOOL_SOFT_BLOCK_RE.search(response)
    if m and m.group(1) in _SOFT_BLOCK_TEXT_TOOLS:
        arg = m.group(2).strip()
        if arg:
            return m.group(1), arg
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
        "cloudflare_block",
        re.compile(
            r"\b(cloudflare|cf-ray|just[_ -]a[_ -]moment|attention[_ -]required|"
            r"checking[_ -]your[_ -]browser|enable[_ -]javascript|"
            r"please[_ -]wait\.\.\.|HTTP\s+(415|520|521|522|524|525))\b",
            re.IGNORECASE,
        ),
        "Cloudflare/JS-challenge блокирует прямой HTTP. Попробуй `browser.open` "
        "(Playwright рендерит JS, обходит большинство challenge), или "
        "`code.exec` с `cloudscraper`. На голой `web.fetch` это не пройдёт.",
    ),
    (
        "tls_handshake",
        re.compile(
            r"\b(SSL|TLS).*\b(handshake|certificate|verify|cert[_ ]?expired)\b|"
            r"\bSSLError\b|\bCERTIFICATE_VERIFY_FAILED\b",
            re.IGNORECASE,
        ),
        "TLS-проблема. Если сертификат не критичен — попробуй "
        "`requests.get(..., verify=False)` через code.exec, либо `browser.open`.",
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
    "goals.abandon", "skills.register_builtins", "skills.register_runtime",
    "memory.index_status",
    "selfmod.apply", "selfmod.validate", "selfmod.propose", "selfmod.propose_edit",
})

# Local-data tools whose output may legitimately contain the words "403",
# "forbidden", "error", "rate limit" etc. as part of stored content (task
# descriptions, knowledge base, memory recall). These NEVER make external
# calls so HTTP/auth blocker detection on their output is always a FP.
_LOCAL_DATA_TOOLS = frozenset({
    # tasks.* — read AND write paths return task content (title, blocker,
    # next_step_hint, last_session_notes) which can legitimately contain
    # "403", "forbidden", "Cloudflare", etc. as part of stored description.
    # The 31.05 task-225 case: tasks.block on a Cloudflare-blocked task
    # echoed back blocker text containing "403" → false-positive auth_403.
    "tasks.get", "tasks.list", "tasks.plan", "tasks.step",
    "tasks.create", "tasks.complete", "tasks.fail", "tasks.block",
    "tasks.unblock", "tasks.pause", "tasks.handoff", "tasks.pick",
    "memory.recall", "memory.index_status",
    "memory.recall_visual",
    "knowledge.list", "knowledge.read", "knowledge.search",
    "knowledge.write", "knowledge.delete",
    "self_inspect.identity", "self_inspect.state", "self_inspect.thoughts",
    "self_inspect.memories", "self_inspect.intentions", "self_inspect.code",
    "self_inspect.modules", "self_inspect.drift",
    "filesystem.list", "filesystem.read", "filesystem.tree",
    # filesystem.write returns "[OK] Written N chars to path" — no FP
    # vector, but adding for symmetry. write blockers caught at exec.
    "filesystem.write",
    "env.list", "env.get", "env.set", "env.clear",
    "skills.list", "skills.run", "skills.register_runtime",
    "skills.register_builtins",
    "selfmod.list", "selfmod.get", "selfmod.check_governed",
    "selfmod.outcomes",
    "selfmod.propose", "selfmod.propose_edit", "selfmod.validate",
    "selfmod.apply", "selfmod.rollback", "selfmod.governed",
    "goals.list", "goals.create", "goals.achieve", "goals.abandon",
    "providers.list", "providers.balance", "providers.health",
    "providers.settings",
    "plugins.list", "plugins.create", "plugins.call",
    "chat.dialog", "chat.tell_ivan", "chat.emergency", "chat.worker_log",
    "mind.focus", "mind.thought", "mind.mood_tint",
    "body.expression", "body.outfit", "voice.speak",
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
    providers: Any | None = None,  # ProvidersTool — providers.* family
    browser: Any | None = None,  # BrowserTool — browser.* family
    subagent: Any | None = None,  # SubagentTool — subagent.* family
    projects: Any | None = None,  # ProjectsTool — projects.* family
    model_eval: Any | None = None,  # ModelsEvalTool — models.evaluate, models.scoreboard, models.set_champion

    initial_thought: str = "",
    initial_user_message: list[dict[str, Any]] | None = None,
    initial_user_text: str | None = None,
    prior_messages: list[dict[str, Any]] | None = None,
    workspace_id: str = "",
    require_dialog_reply: bool = False,
    max_steps: int = 30,
    max_seconds: float = 1200.0,
    purpose: str = "agent_session",
    inbox_drain = None,  # Optional callable () -> list[str] of new messages from user
    drives_callback = None,  # Optional callable () -> None, fired after each successful (non-error) tool step
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

    # Prior dialog history — turns from previous messages between Ivan and
    # Sonya so the model sees CONTINUITY, not "I'm just waking up". Without
    # this, every active-session-from-atrium opens with a fresh "Привет,
    # малыш. Я здесь" because the LLM has no memory of the conversation
    # that happened 5 minutes ago. Caller (channel_session for TG, internal
    # _run_active_session for atrium) builds these from continuity_events.
    if prior_messages:
        for m in prior_messages:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                messages.append({
                    "role": m["role"],
                    "content": m.get("content", ""),
                })

    if initial_user_message is not None:
        # Multimodal entry point — caller (e.g. tg_session with media attachment)
        # constructed a list-style content message that goes straight to the LLM.
        messages.append({"role": "user", "content": initial_user_message})
    elif initial_user_text is not None:
        # Plain user message — no planner prefix. TG session uses this so the
        # LLM doesn't get prompted with "What do you want to do?" which made
        # reasoning models echo back "The user is asking me what I want to do...".
        # If there's also an initial_thought, prepend it as a SYSTEM-level
        # nudge (not as a user-turn — that would confuse the conversation
        # flow with prior_messages history).
        if initial_thought:
            messages.append({
                "role": "system",
                "content": "[INTERNAL_NUDGE]\n" + initial_thought,
            })
        messages.append({"role": "user", "content": initial_user_text})
    elif initial_thought:
        messages.append({"role": "user", "content": f"Your current thought: {initial_thought}\nWhat do you want to do?"})
    else:
        messages.append({"role": "user", "content": "What do you want to do? Think about what would be useful right now."})

    start_time = time.time()
    budget_warning_sent = False
    # Inbox-priority gate (two-phase):
    #
    #   Phase 1 — work-gate: tracks whether Sonya owes Ivan a chat.dialog
    #     reply. Set True when:
    #       - require_dialog_reply=True (real Ivan message opened the session)
    #       - inbox_drain pulls a fresh message mid-session
    #     Cleared when she calls chat.dialog (any text). This lets her start
    #     working — body.expression, browser.open, web.fetch are all blocked
    #     until she at least acknowledges.
    #
    #   Phase 2 — done-gate: tracks whether the most recent chat.dialog
    #     happened AFTER any "real work" tool (browser/web/code/shell/
    #     filesystem/knowledge.write/skills.run/plugins.call/selfmod.*).
    #     Set False at session start, set True every time a non-trivial
    #     tool fires, set False whenever chat.dialog fires. [DONE] is
    #     blocked while True — she has to report what she did after doing it.
    #
    # Без phase 2 был баг 30.05: Соня писала "Привет, я здесь" → делала
    # browser.open/text/close → [DONE] без второго chat.dialog. Иван видел
    # только приветствие, результат пропадал.
    _unanswered_inbox = bool(require_dialog_reply)
    _work_done_since_last_dialog = False
    _recent_tools: list[tuple[str, str]] = []  # (tool, arg-prefix) — last 4

    # Tools that count as "real work" — after one of these fires, the next
    # [DONE] must be preceded by chat.dialog so Sonya reports the result.
    # Mind/body/expression/focus etc don't count — they're internal state,
    # not externally meaningful work.
    #
    # tasks.block / tasks.fail / tasks.complete are EXCLUDED — they are
    # terminal task transitions that already include their own user-facing
    # notification (notify_mode in service.py auto-dispatches). Requiring
    # an EXTRA chat.dialog after them produces the duplicate-report stutter
    # ("Заблокировала task" → gate → chat.dialog "ну заблокировала" → DONE).
    _WORK_TOOLS = frozenset({
        "browser.open", "browser.click", "browser.fill", "browser.text",
        "browser.eval", "browser.screenshot", "browser.wait", "browser.close",
        "web.fetch", "web.search",
        "code.exec", "shell.run", "pip.install",
        "filesystem.read", "filesystem.write", "filesystem.list",
        "filesystem.tree",
        "knowledge.write", "knowledge.delete", "knowledge.read",
        "knowledge.search",
        "memory.recall",
        "skills.run", "skills.register_runtime", "skills.register_builtins",
        "plugins.create", "plugins.call",
        "selfmod.propose", "selfmod.propose_edit", "selfmod.validate",
        "selfmod.apply", "selfmod.rollback", "selfmod.test_sandbox",
        "providers.list", "providers.balance", "providers.health",
        "providers.add", "providers.disable", "providers.enable",
        "providers.set_active",
        # NOTE: tasks.complete/fail/block intentionally NOT here — they
        # carry their own report. tasks.handoff is for inter-session
        # continuity, not Ivan-facing, but creates a state-change worth
        # reporting → kept in for now.
        "tasks.handoff", "tasks.create",
        "self_inspect.code", "self_inspect.identity", "self_inspect.state",
        "self_inspect.thoughts", "self_inspect.memories", "self_inspect.drift",
    })

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

        # LLM call.
        #
        # Per-purpose max_tokens. Дефолт провайдера — 4000 токенов на ход,
        # из-за чего диалог `Привет, малыш` иногда генерится 30-40 секунд.
        # Для диалоговых поверхностей (TG, Atrium active session) ставим
        # 600 — реальные ответы Сони редко длиннее, а tool-only ходы
        # короткие по определению. Worker / research оставляем большими
        # потому что там реально пишутся длинные планы и handoff notes.
        _DIALOG_PURPOSES = {"tg_session", "active_session", "active_session_deep"}
        max_tokens = 600 if purpose in _DIALOG_PURPOSES else 1800
        response = await provider.complete_text(
            messages, purpose=purpose, max_tokens=max_tokens,
        )
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

            # Project policy consent gate: before executing sensitive tools,
            # check if the current project policy requires Ivan's consent.
            # If the action is "forbidden", block entirely. If "consent",
            # block and tell Sonya to ask Ivan via chat.dialog first.
            _POLICY_GATED_TOOLS = {
                "shell.run": "shell_run",
                "filesystem.write": "file_write",
                "selfmod.apply": "selfmod_apply",
                "selfmod.propose": "selfmod_propose",
                "subagent.spawn": "subagent_spawn",
            }
            _skip_policy_gate = False
            if workspace_id:
                try:
                    from sonya.project import WorkspacePolicyStore
                    _wsp = WorkspacePolicyStore(self_inspect._sub).get(workspace_id)
                    if _wsp.full_system_access:
                        _skip_policy_gate = True
                except Exception:
                    pass
            if projects is not None and workspace_id and workspace_id != "main" and not _skip_policy_gate:
                _policy_action = _POLICY_GATED_TOOLS.get(tool_name)
                if _policy_action:
                    try:
                        from sonya.project import ProjectStore
                        _p = ProjectStore(self_inspect._sub).get(workspace_id)
                        if _p.policy_forbids(_policy_action):
                            observation = (
                                f"[PROJECT POLICY: FORBIDDEN] Действие '{_policy_action}' "
                                f"запрещено в проекте '{_p.title}'. "
                                f"Используй projects.check_policy чтобы узнать что разрешено."
                            )
                            messages.append({"role": "assistant", "content": response})
                            messages.append({"role": "user", "content": f"[Observation]: {observation}"})
                            stream.append(ContinuityEvent(
                                kind="internal.project_policy_block",
                                payload={"tool": tool_name, "action": _policy_action, "project_id": workspace_id, "verdict": "forbidden"},
                            ))
                            continue
                        if _p.policy_requires_consent(_policy_action):
                            try:
                                ProjectStore(self_inspect._sub).set_status(
                                    workspace_id,
                                    "waiting_choice",
                                    reason=f"Consent required for {_policy_action}",
                                    source="project_policy",
                                )
                            except Exception:
                                pass
                            observation = (
                                f"[PROJECT POLICY: CONSENT REQUIRED] Для '{_policy_action}' "
                                f"в проекте '{_p.title}' нужно одобрение Ивана. "
                                f"Спроси через chat.dialog перед тем как действовать."
                            )
                            messages.append({"role": "assistant", "content": response})
                            messages.append({"role": "user", "content": f"[Observation]: {observation}"})
                            stream.append(ContinuityEvent(
                                kind="internal.project_policy_block",
                                payload={"tool": tool_name, "action": _policy_action, "project_id": workspace_id, "verdict": "consent"},
                            ))
                            continue
                    except Exception:
                        pass  # Project not found or no policy — allow by default

            # Inbox priority gate: if Ivan wrote and she hasn't answered yet,
            # block any non-dialog tool **only after she's wasted half the
            # session without responding**. On early steps work is allowed
            # — final report goes via `[DONE: text]` (DONE-as-reply) or
            # eventual chat.dialog. Without this relaxation the gate forced
            # an extra "Понял. Сейчас." chat.dialog before every browser/web
            # call, even when Ivan asked her to "просто открой URL и
            # отчитайся [DONE: ...]".
            _DIALOG_TOOLS = {"chat.dialog", "chat.tell_ivan", "chat.emergency"}
            _SAFE_REACTION_TOOLS = {"body.expression", "mind.thought", "mind.focus", "body.outfit"}
            # The gate only lifts when chat.dialog actually dispatches with
            # non-empty text. Empty-arg or [BLOCKED] result keeps the gate
            # active so she can't slip past with an empty marker. Lift is
            # applied AFTER the tool runs (see observation handling below).
            _gate_pending_lift = (
                _unanswered_inbox and tool_name in _DIALOG_TOOLS
            )
            # Half-budget threshold: only enforce the work-block in the
            # second half of the step budget. Before that she's free to
            # work; phase-1 [DONE] gate at the end still ensures a reply.
            _gate_grace_steps = max(3, max_steps // 2)
            if _unanswered_inbox and tool_name in _DIALOG_TOOLS:
                pass  # don't lift yet — wait for observation
            elif (
                _unanswered_inbox
                and tool_name not in _SAFE_REACTION_TOOLS
                and step >= _gate_grace_steps
            ):
                # Refuse the tool only after grace period — она потратила
                # >=N шагов на работу без единого слова Ивану. Force reply.
                stream.append(ContinuityEvent(
                    kind="internal.inbox_priority_gate",
                    payload={
                        "step": step,
                        "blocked_tool": tool_name,
                        "blocked_arg": tool_arg[:200],
                    },
                ))
                messages.append({"role": "assistant", "content": response})
                ivan_msg_quote = (initial_user_text or "").strip()
                quote_block = (
                    f"\nИван написал: «{ivan_msg_quote[:600]}»\n"
                    if ivan_msg_quote else ""
                )
                messages.append({
                    "role": "user",
                    "content": (
                        f"[INBOX GATE] Tool `{tool_name}` ЗАБЛОКИРОВАН — "
                        f"ты сделала {step} шагов без ответа Ивану."
                        + quote_block +
                        "Сейчас обязательно [TOOL: chat.dialog]<твой ответ "
                        "по сути> ИЛИ закрывайся через [DONE: <текст>]. "
                        "Дальше работа выполнится после ответа."
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
                providers=providers,
                browser=browser,
                subagent=subagent,
                substrate=self_inspect._sub,
                projects=projects,
                model_eval=model_eval,
                workspace_id=workspace_id,
            )

            # Record in continuity
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "action", "tool": tool_name, "arg": tool_arg, "thought": response[:8000]},
            ))

            # Auto-trace: if workspace_id is a project, record every step
            # into execution_traces for transparency. This gives Ivan a
            # step-by-step view of what Sonya did inside each project run.
            if workspace_id and workspace_id != "main":
                try:
                    from sonya.project import ExecutionTraceStore, ProjectRunStore
                    _trace_substrate = self_inspect._sub
                    _run_store = ProjectRunStore(_trace_substrate)
                    _existing = _run_store.list_by_project(workspace_id, kind="main", limit=1)
                    if _existing and _existing[0].status in ("pending", "running"):
                        _run_id = _existing[0].run_id
                    else:
                        _run = _run_store.create(workspace_id, kind="main", agent_type=purpose)
                        _run_store.start(_run.run_id)
                        _run_id = _run.run_id
                    _trace_store = ExecutionTraceStore(_trace_substrate)
                    _prev = _trace_store.list_by_run(_run_id, limit=1)
                    _seq = (_prev[0].step_seq + 1) if _prev else step
                    step_type = "action" if not observation.lstrip().startswith("[ERROR]") else "error"
                    _trace_store.append(
                        _run_id, workspace_id,
                        step_seq=_seq,
                        step_type=step_type,
                        content=response[:4000],
                        tool_name=tool_name,
                        outcome=observation[:2000],
                    )
                except Exception:
                    pass

            # Feed observation back
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"[Observation from {tool_name}]:\n{observation[:3000]}"})

            # Drives feedback: fire on_action_completed after a non-error
            # tool step. This is the missing wire from drives.py — без него
            # pending_debt только растёт, никогда не падает. Heuristic:
            # observation starting with "[ERROR]" or "[BLOCKED]" is failure.
            if drives_callback is not None and observation:
                head = observation.lstrip()[:10].upper()
                if not head.startswith("[ERROR]") and not head.startswith("[BLOCKED]"):
                    try:
                        drives_callback()
                    except Exception:
                        pass

            # Inbox-priority gate lift: chat.dialog must have actually
            # dispatched (non-error result) for the gate to lift. Empty-arg
            # or [BLOCKED] result keeps the gate active so the model can't
            # slip past with `[TOOL: chat.dialog]` and no text.
            if _gate_pending_lift and observation:
                head = observation.lstrip()[:10].upper()
                if not head.startswith("[ERROR]") and not head.startswith("[BLOCKED]"):
                    _unanswered_inbox = False

            # Done-gate tracking (phase 2 of inbox-priority): chat.dialog
            # resets the "owe a report" flag; any real-work tool sets it.
            # Used below to block premature [DONE] when she ran tools
            # without reporting back.
            #
            # Terminal task transitions (complete/fail/block) ALSO clear
            # the flag — they auto-notify Ivan via notify_mode, no extra
            # chat.dialog needed. Without this Соня писала дублирующий
            # отчёт после `tasks.block` (the 31.05 task-225 case).
            _TERMINAL_TASK_TOOLS = {
                "tasks.complete", "tasks.fail", "tasks.block",
            }
            if tool_name in _DIALOG_TOOLS:
                if observation:
                    head = observation.lstrip()[:10].upper()
                    if (
                        not head.startswith("[ERROR]")
                        and not head.startswith("[BLOCKED]")
                    ):
                        _work_done_since_last_dialog = False
            elif tool_name in _TERMINAL_TASK_TOOLS:
                if observation:
                    head = observation.lstrip()[:10].upper()
                    if not head.startswith(("[ERROR]", "[BLOCKED]")):
                        _work_done_since_last_dialog = False
                        # Phase-1 lift too — terminal transitions count
                        # as her response to Ivan when notify_mode != silent.
                        _unanswered_inbox = False
            elif tool_name in _WORK_TOOLS:
                _work_done_since_last_dialog = True

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
            # `[DONE: <text>]` short-circuit — the model finalized with
            # an inline reply body. Treat it as her message to Ivan
            # (auto-dispatch via outbound) and let [DONE] proceed.
            # Without this the active-session path forces TWO separate
            # chat.dialog calls (ack + report), which feels stilted —
            # Ivan asks "проверь X", Sonya replies "Привет малыш, иду",
            # works, then "вот результат". With DONE-as-reply she can
            # just answer: she works, then `[DONE: вот что вышло]` and
            # Ivan sees one focused reply. Mirrors TG semantics where
            # `[DONE: text]` IS the message body.
            done_body = ""
            done_match = _DONE_WITH_BODY_RE.search(response)
            if done_match is not None:
                done_body = (done_match.group("body") or "").strip()
                # This body is already the explicit answer layer. Remove only
                # protocol/internal content and preserve useful Markdown/code.
                # The heavy TG fallback scrubber intentionally does not run
                # here because it can delete valid answer content.
                if done_body:
                    try:
                        from sonya.subject.channel_session import _sanitize_explicit_answer
                        done_body = _sanitize_explicit_answer(done_body)
                    except Exception:
                        # Fail-safe keeps user content intact.
                        done_body = re.sub(
                            r"<think>[\s\S]*?</think>", "", done_body,
                            flags=re.IGNORECASE,
                        )
                        done_body = done_body.strip()
            done_as_reply_dispatched = False
            if (
                done_body
                and len(done_body) >= 5
                and outbound is not None
                and (_unanswered_inbox or _work_done_since_last_dialog)
            ):
                try:
                    from sonya.initiative.outbound import call_outbound_sync
                    dispatch_result = call_outbound_sync(
                        outbound, done_body, channel="dialog",
                    )
                    if not dispatch_result.startswith(("[ERROR]", "[BLOCKED]")):
                        if outbound is not None:
                            result.outbound_sent.append(done_body)
                        # Dialog dispatched — both gates satisfied.
                        _unanswered_inbox = False
                        _work_done_since_last_dialog = False
                        done_as_reply_dispatched = True
                        stream.append(ContinuityEvent(
                            kind="internal.done_as_reply_dispatched",
                            payload={
                                "step": step,
                                "preview": done_body[:240],
                            },
                        ))
                except Exception:
                    pass

            # Inbox-priority gate also applies to [DONE]:
            #
            #   Phase 1 — `_unanswered_inbox`: she hasn't replied to Ivan
            #     even once. Block (unless DONE-as-reply just fired).
            #   Phase 2 — `_work_done_since_last_dialog`: she replied first,
            #     then did real work (browser/code/web/...), but no follow-up
            #     chat.dialog with results. Block — Ivan needs the report.
            #
            # Without this, the active-session-from-atrium path would let her
            # do `chat.dialog "Привет, иду"` → browser.* → [DONE]. Ivan sees
            # only "Привет, иду", the result of browser work disappears.
            # The 30.05 silent-no-reply bug + 31.05 silent-no-result bug.
            gate_reason = None
            if _unanswered_inbox and not done_as_reply_dispatched:
                gate_reason = "must_reply_to_ivan_first"
                # Repeat Ivan's message verbatim — small/fast models lose
                # focus over long prompts and forget what they're supposed
                # to reply to. The gate hint becomes the freshest copy of
                # the user message in the prompt.
                ivan_msg = (initial_user_text or "").strip()
                msg_quote = (
                    f"\nИван написал: «{ivan_msg[:600]}»\n" if ivan_msg else ""
                )
                gate_msg = (
                    "[INBOX GATE] [DONE] ЗАБЛОКИРОВАН — Иван ждёт твой ответ."
                    + msg_quote +
                    "Следующий ход — [TOOL: chat.dialog]<твой ответ ему> "
                    "ИЛИ напиши финал как `[DONE: <твой ответ>]` — текст "
                    "уйдёт Ивану. Ответь по сути. "
                    "НЕ задавай вопрос «что он написал» — его текст выше. "
                    "Ответ должен быть в твоём голосе, не приветствие, "
                    "а реакция на сказанное."
                )
            elif (
                require_dialog_reply
                and _work_done_since_last_dialog
                and not done_as_reply_dispatched
            ):
                gate_reason = "must_report_results"
                gate_msg = (
                    "[REPORT GATE] [DONE] ЗАБЛОКИРОВАН — после "
                    "первого chat.dialog ты сделала реальную работу "
                    "(browser/code/web/...), но не отчиталась Ивану о "
                    "результате. Иван видит только первое приветствие. "
                    "Сделай ещё один [TOOL: chat.dialog]<краткий результат> "
                    "ИЛИ закрывай через `[DONE: <краткий результат>]` — "
                    "текст уйдёт Ивану."
                )

            if gate_reason is not None:
                stream.append(ContinuityEvent(
                    kind="internal.inbox_priority_gate",
                    payload={
                        "step": step,
                        "blocked_tool": "[DONE]",
                        "reason": gate_reason,
                    },
                ))
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": gate_msg})
                continue
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
    knowledge: Any | None = None
    stream: Any | None = None
    providers: Any | None = None
    browser: Any | None = None
    subagent: Any | None = None
    substrate: Any | None = None
    projects: Any | None = None
    workspace_id: str = ""


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
    since = ""
    until = ""
    if arg.strip():
        parts = arg.strip().split()
        for i, p in enumerate(parts):
            if p.startswith("since=") and len(p) > 6:
                since = p[6:]
            elif p.startswith("until=") and len(p) > 6:
                until = p[6:]
    return ctx.self_inspect.read_recent_memories(since=since, until=until)


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


def _h_mem_recall_visual(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.memory, "memory")
    if err:
        return err
    return ctx.memory.recall_visual(arg.strip())


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


def _h_skills_register_runtime(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.skills, "skills")
    return err if err else ctx.skills.register_runtime(arg)


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
    """Block form: первая строка = имя плагина, остальное = python source.

    Inline fallback: `<name> <inline code>` (одна строка). Source
    компилируется перед записью — раннее выявление SyntaxError.
    """
    from sonya.tools.hot_loader import ensure_plugins_dir, load_plugin
    import re as _re

    text = (arg or "").lstrip("\n")
    if not text.strip():
        return "[ERROR] plugins.create needs: <name>\\n<python_code> or <name> <inline_code>"

    if "\n" in text:
        first, rest = text.split("\n", 1)
        plugin_name = first.strip()
        plugin_code = rest
    else:
        # Inline form: first whitespace-token = name, rest = code.
        parts = text.split(None, 1)
        if len(parts) < 2:
            return "[ERROR] plugins.create needs: <name>\\n<python_code>"
        plugin_name, plugin_code = parts[0], parts[1]

    if not _re.match(r"^[a-z_][a-z0-9_]{1,63}$", plugin_name, _re.IGNORECASE):
        return (
            f"[ERROR] plugins.create: invalid name {plugin_name!r}. "
            "Use lowercase letters, digits, '_' (must start with letter/_)."
        )

    if not plugin_code.strip():
        return "[ERROR] plugins.create: empty plugin source"

    try:
        compile(plugin_code, f"<plugin:{plugin_name}>", "exec")
    except SyntaxError as exc:
        return f"[ERROR] plugins.create: SyntaxError: {exc}"

    plugin_path = ensure_plugins_dir() / f"{plugin_name}.py"
    plugin_path.write_text(plugin_code, encoding="utf-8")
    try:
        load_plugin(plugin_name)
    except Exception as exc:
        return (
            f"[OK] written {plugin_path} but load failed: "
            f"{type(exc).__name__}: {exc}. Plugin will reload on next call."
        )
    return f"[OK] Plugin '{plugin_name}' created and loaded → {plugin_path}"


def _h_plugins_call(arg: str, ctx: _ToolContext) -> str:
    """Call a loaded plugin's run(args).

    `args` parsing rules:
      - empty → run() called with empty dict {}
      - starts with `{` or `[` → parsed as JSON, run(parsed_obj)
      - otherwise → run(raw_string)

    Plugin's `run()` must accept ONE positional arg of any type and return
    a value (str/dict/list — converted to str by the dispatcher).
    """
    from sonya.tools.hot_loader import get_plugin, load_plugin
    parts = (arg or "").strip().split(None, 1)
    if not parts:
        return "[ERROR] plugins.call needs: <name> [args]"
    plugin_name = parts[0]
    plugin_args_str = parts[1] if len(parts) > 1 else ""
    # Smart parse: dict/list literals → JSON; otherwise → raw string.
    plugin_args: Any
    s = plugin_args_str.strip()
    if not s:
        plugin_args = {}
    elif s[:1] in "{[":
        try:
            plugin_args = json.loads(s)
        except json.JSONDecodeError:
            plugin_args = plugin_args_str  # fall back to raw string
    else:
        plugin_args = plugin_args_str
    try:
        module = get_plugin(plugin_name) or load_plugin(plugin_name)
    except (ImportError, FileNotFoundError) as exc:
        return f"[ERROR] plugins.call: {exc}"
    if not hasattr(module, "run"):
        return f"[ERROR] Plugin '{plugin_name}' has no run() function"
    try:
        return str(module.run(plugin_args))
    except Exception as exc:
        return f"[ERROR] plugin '{plugin_name}' crashed: {type(exc).__name__}: {exc}"


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


def _h_selfmod_outcomes(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.selfmod, "selfmod")
    return err if err else ctx.selfmod.outcomes(arg.strip())


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
    result = call_outbound_sync(
        ctx.outbound,
        text,
        channel="dialog",
        workspace_id=ctx.workspace_id or "",
    )
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
        ctx.outbound,
        text,
        channel="dialog",
        emergency_override=True,
        workspace_id=ctx.workspace_id or "",
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
    text = (arg or "").strip()
    if not text:
        return "[ERROR] mind.thought: empty"
    # Prefer the OutboundGate path (handles dedup, gating, rate caps).
    if ctx.outbound is not None:
        from sonya.initiative.outbound import call_outbound_sync
        return call_outbound_sync(ctx.outbound, text, channel="mind")
    # Fallback: write directly to continuity stream. Used when outbound
    # gate isn't wired (e.g. early-init self-checks, pure smoke tests).
    # Mind pane is internal-only — no Telegram dispatch needed.
    if ctx.stream is None:
        return "[ERROR] mind.thought: no continuity stream available"
    import re as _re
    is_private = bool(_re.match(r"^\s*\[PRIVATE\]\s*", text, _re.IGNORECASE))
    body = _re.sub(r"^\s*\[PRIVATE\]\s*", "", text, count=1, flags=_re.IGNORECASE).strip()
    ctx.stream.append(ContinuityEvent(
        kind="outgoing.mind_thought",
        channel="mind",
        private=is_private,
        payload={"text": body, "private": is_private, "via": "mind.thought"},
    ))
    privacy_note = " (private)" if is_private else ""
    return f"[OK] mind.thought recorded{privacy_note}: {body[:80]}"


_BODY_EXPRESSION_ALLOWED = frozenset({
    # base
    "neutral", "calm",
    # positive
    "joy", "smile", "tender", "playful", "shy", "desire", "desire_bite",
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
# Registry: tool name → handler. Keep alphabetised within each family to
# make adding new tools mechanical. New tool = one function above + one
# entry here.


# providers.* — она управляет своим LLM-pool сама. См. tools/providers_tool.py
def _h_providers_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.list_keys(arg)


def _h_providers_settings(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.settings(arg)


def _h_providers_balance(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.balance(arg)


def _h_providers_health(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.health_report(arg)


def _h_providers_disable(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.disable_key(arg)


def _h_providers_enable(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.enable_key(arg)


def _h_providers_add(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.add_key(arg)


def _h_providers_set_active(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.set_active(arg)


def _h_providers_models(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.providers, "providers")
    return err if err else ctx.providers.list_models(arg)


# subagent.* — spawn/list/check subagent tasks
def _h_subagent_spawn(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.subagent, "subagent")
    return err if err else ctx.subagent.spawn(arg)


def _h_subagent_list(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.subagent, "subagent")
    return err if err else ctx.subagent.list_all(arg)


def _h_subagent_result(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.subagent, "subagent")
    return err if err else ctx.subagent.result(arg)


# browser.* — Playwright wrapper. См. tools/browser_tool.py
def _h_browser_open(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.open(arg)


def _h_browser_click(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.click(arg)


def _h_browser_fill(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.fill(arg)


def _h_browser_text(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.text(arg)


def _h_browser_eval(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.eval_js(arg)


def _h_browser_screenshot(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.screenshot(arg)


def _h_browser_wait(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.wait_for(arg)


def _h_browser_close(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.browser, "browser")
    return err if err else ctx.browser.close(arg)


async def _h_projects_dispatch(call: dict) -> str:
    import asyncio
    tool = call.get("_projects_tool")
    if tool is None:
        return "[ERROR] projects tool not configured"
    return await tool.execute(call)


def _h_projects(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.projects, "projects")
    if err:
        return err
    import json
    try:
        call = json.loads(arg) if arg.startswith("{") else {"name": "projects.list", "arguments": {}}
    except Exception:
        call = {"name": "projects.list", "arguments": {}}
    call["_projects_tool"] = ctx.projects
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _h_projects_dispatch(call))
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(_h_projects_dispatch(call))
    except Exception:
        return asyncio.run(_h_projects_dispatch(call))


def _h_projects_demo_webchat(arg: str, ctx: _ToolContext) -> str:
    """Create a test website/chat-bot project and orchestrate it with subagents only.

    This is the end-to-end verification path the user asked for.
    It creates a project, then spawns subagents for planning / execution /
    review, letting the subagent model picker choose appropriate models.
    """
    err = _require(ctx.projects, "projects")
    if err:
        return err
    err = _require(ctx.subagent, "subagent")
    if err:
        return err
    import json
    try:
        data = json.loads(arg or "{}")
    except Exception:
        data = {}
    title = str(data.get("title") or "test website chat-bot").strip()
    workspace_path = str(data.get("workspace_path") or "").strip()
    description = str(data.get("description") or "")
    # 1) Create project
    project_res = ctx.projects.execute({
        "name": "projects.create",
        "arguments": {
            "title": title,
            "description": description or "End-to-end test project: website + chat-bot",
            "workspace_path": workspace_path,
        },
    })
    # 2) Extract project_id from the result
    import re
    m = re.search(r"\[(proj-[a-z0-9]+)\]", project_res)
    project_id = m.group(1) if m else ""
    if not project_id:
        return f"[ERROR] Could not parse project_id from: {project_res}"

    # 3) Spawn subagents only (no direct tool execution of the project work).
    sub_tasks = [
        {
            "name": "planner",
            "task": (
                f"Project {project_id}: design a minimal website chat-bot architecture. "
                f"Break it into small implementable tasks. Focus on cheap/free models for execution, "
                f"keep expensive models for reasoning/review only if needed."
            ),
        },
        {
            "name": "executor-ui",
            "task": (
                f"Project {project_id}: implement the frontend skeleton for a website chat-bot. "
                f"Only handle UI implementation steps. Use the fastest suitable model."
            ),
        },
        {
            "name": "executor-backend",
            "task": (
                f"Project {project_id}: implement backend endpoints and persistence for a website chat-bot. "
                f"Keep the work split into small steps; do not attempt the whole backend in one shot."
            ),
        },
        {
            "name": "reviewer",
            "task": (
                f"Project {project_id}: review architecture, verify policy gates, and report gaps. "
                f"Use strong reasoning only for review; otherwise stay cheap/fast."
            ),
        },
    ]
    spawned = []
    for item in sub_tasks:
        try:
            resp = ctx.subagent.spawn(json.dumps({"task": item["task"], "max_steps": 8}))
            spawned.append(f"[{item['name']}] {resp.splitlines()[0] if resp else 'spawned'}")
        except Exception as e:
            spawned.append(f"[{item['name']}] ERROR: {e}")

    # 4) Record a trace marker that this is the verification workflow.
    try:
        ctx.projects.execute({
            "name": "projects.trace",
            "arguments": {
                "project_id": project_id,
                "step_type": "decision",
                "content": "Initialized demo web chat-bot project and spawned role-based subagents only.",
                "tool_name": "projects.demo_webchat",
                "outcome": "ok",
            },
        })
    except Exception:
        pass

    return (
        f"[OK] Demo web chat-bot project created: {project_id}\n"
        f"Project: {title}\n"
        f"Spawned subagents:\n- " + "\n- ".join(spawned) +
        f"\n\nNext: check subagent.result for each spawned subagent and continue from there."
    )


async def _h_model_eval_dispatch(call: dict) -> str:
    import asyncio
    tool = call.get("_model_eval_tool")
    if tool is None:
        return "[ERROR] model_eval tool not configured"
    return await tool.execute(call)


def _h_model_eval(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.model_eval, "model_eval")
    if err:
        return err
    import json
    try:
        call = json.loads(arg) if arg.startswith("{") else {"name": "models.scoreboard", "arguments": {}}
    except Exception:
        call = {"name": "models.scoreboard", "arguments": {}}
    call["_model_eval_tool"] = ctx.model_eval
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _h_model_eval_dispatch(call))
                return future.result(timeout=300)
        else:
            return loop.run_until_complete(_h_model_eval_dispatch(call))
    except Exception:
        return asyncio.run(_h_model_eval_dispatch(call))


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
    "memory.recall_visual": _h_mem_recall_visual,
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
    "skills.register_runtime": _h_skills_register_runtime,
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
    "selfmod.outcomes": _h_selfmod_outcomes,
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
    # providers.* — manage own LLM key pool. См. tools/providers_tool.py
    "providers.list":     _h_providers_list,
    "providers.settings": _h_providers_settings,
    "providers.balance":  _h_providers_balance,
    "providers.health":   _h_providers_health,
    "providers.disable":  _h_providers_disable,
    "providers.enable":   _h_providers_enable,
    "providers.add":      _h_providers_add,
    "providers.set_active": _h_providers_set_active,
    "providers.models":    _h_providers_models,
    "subagent.spawn":      _h_subagent_spawn,
    "subagent.list":       _h_subagent_list,
    "subagent.result":     _h_subagent_result,
    # browser.* — Playwright. См. tools/browser_tool.py
    "browser.open":       _h_browser_open,
    "browser.click":      _h_browser_click,
    "browser.fill":       _h_browser_fill,
    "browser.text":       _h_browser_text,
    "browser.eval":       _h_browser_eval,
    "browser.screenshot": _h_browser_screenshot,
    "browser.wait":       _h_browser_wait,
    "browser.close":      _h_browser_close,
    # projects.* — project management, policy, traces, evolution pressure
    "projects.list":        _h_projects,
    "projects.check_policy": _h_projects,
    "projects.create":      _h_projects,
    "projects.trace":       _h_projects,
    "projects.pressure":    _h_projects,
    "projects.demo_webchat": _h_projects_demo_webchat,
    # model_eval suite — models.evaluate, models.scoreboard, models.set_champion
    "models.evaluate": _h_model_eval,
    "models.scoreboard": _h_model_eval,
    "models.set_champion": _h_model_eval,
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
    providers: Any | None = None,
    browser: Any | None = None,
    subagent: Any | None = None,
    substrate: Any | None = None,
    projects: Any | None = None,
    model_eval: Any | None = None,
    workspace_id: str = "",
) -> str:
    """Execute a tool by name. Returns observation string.

    Logs failures (exception) to continuity stream as ``internal.tool_error``.
    Records every invocation into tool_experiences for learning.
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
        providers=providers,
        browser=browser,
        subagent=subagent,
        substrate=substrate,
        projects=projects,
        workspace_id=workspace_id,
    )

    _t0 = time.monotonic()
    try:
        observation = handler(arg, ctx)
    except Exception as e:
        observation = f"[ERROR] {type(e).__name__}: {e}"
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

    elapsed_ms = int((time.monotonic() - _t0) * 1000)

    if substrate is not None:
        try:
            from sonya.memory.tool_experience import ToolExperience, classify_outcome, extract_tool_tags
            tx = ToolExperience(substrate)
            tx.record(
                tool_name=name,
                tool_arg_summary=(arg or "")[:200],
                outcome=classify_outcome(observation),
                outcome_detail=observation[:500],
                latency_ms=elapsed_ms,
                tags=extract_tool_tags(name, arg, observation),
                session_type="agent_session",
            )
        except Exception:
            pass

    return observation
