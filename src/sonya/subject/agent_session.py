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
- memory.recall [query] — semantic search over your full episodic history (returns top-5 relevant memories with similarity score)
- memory.index_status — diagnostic: how many events are embedded vs pending
- env.set [key value] — record what you observe about Ivan / context (e.g. `env.set ivan_status спит`, `env.set mood уставший`, `env.set activity работает`). Used to suppress initiative when Ivan is busy/asleep — OutboundGate respects ivan_status='спит' / 'занят'.
- env.get [key] — read a previously recorded observation
- env.list — list all current observations
- env.clear [key] — drop an observation when no longer relevant
- skills.list — show registered skills and their status
- skills.run [skill_id] [query] — execute a skill (e.g. `skills.run skill-memory-search что мы обсуждали вчера`)
- skills.register_builtins — seed built-in skills (memory-search, identity-check, dialog-tone) into registry. Call once.
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
                    "content": f"[NEW MESSAGE FROM IVAN]: {m}",
                })
                stream.append(ContinuityEvent(
                    kind="internal.inbox_injected",
                    payload={"step": step, "preview": m[:300]},
                ))

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
            result.actions.append(f"{tool_name} {tool_arg[:60]}")
            result.thoughts.append(response)

            # Execute tool
            observation = _execute_tool(
                tool_name, tool_arg, self_inspect, filesystem, stream,
                selfmod, tasks, web, code, shell, outbound, memory, env, skills,
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


def _h_tasks_complete(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.complete(arg)


def _h_tasks_fail(arg: str, ctx: _ToolContext) -> str:
    err = _require(ctx.tasks, "tasks")
    return err if err else ctx.tasks.fail(arg)


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
    from sonya.initiative.outbound import call_outbound_sync
    result = call_outbound_sync(ctx.outbound, arg)
    # Record sent text so channel_session can suppress a [DONE: ...] echo
    # of the same content (prevents duplicate messages to Ivan).
    if ctx.outbound_sent is not None and arg.strip():
        ctx.outbound_sent.append(arg.strip())
    return result


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
        outbound=outbound,
        outbound_sent=outbound_sent,
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
