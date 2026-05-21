"""Single-stream agent session with tool use.

Not a parallel process. Part of the one event loop.
Called from InternalProcess on active_timeout or when tools needed for response.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

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
- filesystem.read [path] — read a file
- filesystem.list [path] — list directory
- filesystem.tree [path] — show directory tree
- filesystem.write — block form: first line of args = path, remaining = content
- plugins.list — list available plugins
- plugins.create — block form: first line = name, remaining = python code
- plugins.call [name] [args] — call a loaded plugin
- selfmod.propose — block form, JSON: {"target": "src/sonya/...", "summary": "...", "content": "<full file>"} OR pipe-separated: target | summary | content
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
- tasks.plan — block form, JSON: {"task_id": "...", "steps": ["a", "b"]}
- tasks.step — block form, JSON: {"task_id": "...", "step_idx": 0, "summary": "did it"}
- tasks.complete — block form, JSON: {"task_id": "...", "result": "..."}
- tasks.fail — block form, JSON: {"task_id": "...", "reason": "..."}
- tasks.block — block form, JSON: {"task_id": "...", "blocker": "..."}
- tasks.unblock [task_id]
- tasks.pause [task_id]
- tasks.handoff — block form, JSON: {"task_id": "...", "notes": "where I left off", "next_step": "what next session should do first"}
  Call BEFORE [DONE] when ending a session on an unfinished task. Bumps sessions_used. If max_sessions reached, task auto-fails. Without handoff next session starts blind.

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
_TOOL_INLINE_RE = re.compile(r"\[TOOL:\s*([^\s\]]+)(?:\s+([^\n\]]*))?\]")
# Block form: [TOOL: name]\n```optional-lang\n<arg>\n```
_TOOL_BLOCK_RE = re.compile(
    r"\[TOOL:\s*([^\s\]]+)\s*\]\s*\n```[a-zA-Z0-9_-]*\n(.*?)\n```",
    re.DOTALL,
)


def _extract_tool_call(response: str) -> tuple[str, str] | None:
    """Return (tool_name, arg) if response contains a tool invocation.

    Block form takes precedence so multi-line code/JSON args work.
    """
    m = _TOOL_BLOCK_RE.search(response)
    if m:
        return m.group(1), m.group(2)
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
            observation = _execute_tool(tool_name, tool_arg, self_inspect, filesystem, stream, selfmod, tasks, web, code, shell, outbound, memory, env, skills)

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
        # Ask what next — kept short and language-agnostic to avoid leaking
        # English meta-reasoning into the next turn.
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": "Продолжай. Если закончила — `[DONE]`."})

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
) -> str:
    """Execute a tool by name. Returns observation string. Logs failures to continuity stream."""
    try:
        if name == "self_inspect.identity":
            return self_inspect.read_identity()
        elif name == "self_inspect.state":
            return self_inspect.read_subject_state()
        elif name == "self_inspect.thoughts":
            return self_inspect.read_recent_thoughts()
        elif name == "self_inspect.memories":
            return self_inspect.read_recent_memories()
        elif name == "self_inspect.intentions":
            return self_inspect.read_active_intentions()
        elif name == "self_inspect.code":
            return self_inspect.read_own_code(arg)
        elif name == "self_inspect.modules":
            return self_inspect.list_own_modules()
        elif name == "filesystem.read":
            return filesystem.read(arg)
        elif name == "filesystem.list":
            return filesystem.list_dir(arg)
        elif name == "filesystem.tree":
            return filesystem.tree(arg)
        elif name == "filesystem.write":
            parts = arg.split(" ", 1)
            if len(parts) < 2:
                return "[ERROR] filesystem.write needs: path content"
            return filesystem.write(parts[0], parts[1])
        elif name == "memory.recall":
            if memory is None:
                return "[ERROR] memory tool not configured"
            return memory.recall(arg.strip())
        elif name == "memory.index_status":
            if memory is None:
                return "[ERROR] memory tool not configured"
            return memory.index_status()
        elif name == "env.set":
            if env is None:
                return "[ERROR] env tool not configured"
            return env.set(arg)
        elif name == "env.get":
            if env is None:
                return "[ERROR] env tool not configured"
            return env.get(arg)
        elif name == "env.list":
            if env is None:
                return "[ERROR] env tool not configured"
            return env.list_all()
        elif name == "env.clear":
            if env is None:
                return "[ERROR] env tool not configured"
            return env.clear(arg)
        elif name == "skills.list":
            if skills is None:
                return "[ERROR] skills tool not configured"
            return skills.list_skills()
        elif name == "skills.run":
            if skills is None:
                return "[ERROR] skills tool not configured"
            return skills.run(arg)
        elif name == "skills.register_builtins":
            if skills is None:
                return "[ERROR] skills tool not configured"
            return skills.register_builtins()
        elif name == "plugins.list":
            from sonya.tools.hot_loader import list_plugins
            plugins = list_plugins()
            return "\n".join(plugins) if plugins else "No plugins loaded."
        elif name == "plugins.create":
            from sonya.tools.hot_loader import ensure_plugins_dir, load_plugin
            parts = arg.split(" ", 1)
            if len(parts) < 2:
                return "[ERROR] plugins.create needs: name python_code"
            plugin_name = parts[0]
            plugin_code = parts[1]
            plugin_path = ensure_plugins_dir() / f"{plugin_name}.py"
            plugin_path.write_text(plugin_code, encoding="utf-8")
            load_plugin(plugin_name)
            return f"[OK] Plugin '{plugin_name}' created and loaded."
        elif name == "plugins.call":
            from sonya.tools.hot_loader import get_plugin, load_plugin
            parts = arg.split(" ", 1)
            plugin_name = parts[0]
            plugin_args = parts[1] if len(parts) > 1 else ""
            module = get_plugin(plugin_name)
            if module is None:
                module = load_plugin(plugin_name)
            if hasattr(module, "run"):
                result = module.run(plugin_args)
                return str(result)
            return f"[ERROR] Plugin '{plugin_name}' has no run() function"

        # --- selfmod.* family ---
        elif name == "selfmod.propose":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            # Accept BOTH formats:
            #   pipe-separated: target_path | summary | content
            #   JSON block: {"target": "...", "summary": "...", "content": "..."}
            arg_stripped = arg.strip()
            if arg_stripped.startswith("{"):
                try:
                    data = json.loads(arg_stripped)
                    target = data.get("target", "").strip()
                    summary = data.get("summary", "").strip()
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
                target = parts[0].strip()
                summary = parts[1].strip()
                content = parts[2]
            if not target or not summary:
                return "[ERROR] selfmod.propose: target and summary are required"
            return selfmod.propose(target, summary, new_content=content)
        elif name == "selfmod.validate":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.validate(arg.strip())
        elif name == "selfmod.test_sandbox":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.test_sandbox(arg.strip())
        elif name == "selfmod.apply":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.apply(arg.strip())
        elif name == "selfmod.list":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.list_proposals(arg.strip())
        elif name == "selfmod.get":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.get_proposal(arg.strip())
        elif name == "selfmod.governed":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.request_governed(arg.strip())
        elif name == "selfmod.check_governed":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.check_governed(arg.strip())
        elif name == "selfmod.rollback":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            parts = arg.split(" ", 1)
            pid = parts[0].strip()
            reason = parts[1].strip() if len(parts) > 1 else ""
            return selfmod.rollback(pid, reason=reason)
        elif name == "selfmod.soft_restart":
            if selfmod is None:
                return "[ERROR] selfmod tool not configured"
            return selfmod.soft_restart_runtime(arg.strip())

        # --- tasks.* family ---
        elif name == "tasks.create":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.create(arg)
        elif name == "tasks.list":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.list(arg)
        elif name == "tasks.get":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.get(arg)
        elif name == "tasks.pick":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.pick(arg)
        elif name == "tasks.plan":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.plan(arg)
        elif name == "tasks.step":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.step(arg)
        elif name == "tasks.complete":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.complete(arg)
        elif name == "tasks.fail":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.fail(arg)
        elif name == "tasks.block":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.block(arg)
        elif name == "tasks.unblock":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.unblock(arg)
        elif name == "tasks.pause":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.pause(arg)
        elif name == "tasks.handoff":
            if tasks is None:
                return "[ERROR] tasks tool not configured"
            return tasks.handoff(arg)

        # --- web.* family ---
        elif name == "web.search":
            if web is None:
                return "[ERROR] web tool not configured"
            return web.search(arg)
        elif name == "web.fetch":
            if web is None:
                return "[ERROR] web tool not configured"
            return web.fetch(arg)

        # --- code.exec ---
        elif name == "code.exec":
            if code is None:
                return "[ERROR] code tool not configured"
            return code.exec_python(arg)

        # --- shell.run / pip.install (approval-gated) ---
        elif name == "shell.run":
            if shell is None:
                return "[ERROR] shell tool not configured"
            return shell.run_shell(arg)
        elif name == "pip.install":
            if shell is None:
                return "[ERROR] shell tool not configured"
            return shell.install_pip(arg)

        # --- chat.tell_ivan (initiative) ---
        elif name == "chat.tell_ivan":
            if outbound is None:
                return "[ERROR] initiative gate not configured (set SONYA_PRIMARY_USER_TG_ID)"
            from sonya.initiative.outbound import call_outbound_sync
            return call_outbound_sync(outbound, arg)

        else:
            return f"[ERROR] Unknown tool: {name}"
    except Exception as e:
        # S-11 fix: log tool failures to continuity stream so Sonya can see what broke
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
