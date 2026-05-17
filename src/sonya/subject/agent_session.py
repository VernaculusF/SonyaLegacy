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
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool
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
- filesystem.read [path] — read a file
- filesystem.list [path] — list directory
- filesystem.tree [path] — show directory tree
- filesystem.write — block form: first line of args = path, remaining = content
- plugins.list — list available plugins
- plugins.create — block form: first line = name, remaining = python code
- plugins.call [name] [args] — call a loaded plugin
- selfmod.propose — block form, JSON: {"target": "src/sonya/...", "summary": "...", "content": "<full file>"}
- selfmod.test_sandbox [proposal_id]
- selfmod.validate [proposal_id]
- selfmod.apply [proposal_id]
- selfmod.list [status_filter?]
- selfmod.get [proposal_id]
- selfmod.governed [proposal_id]
- selfmod.check_governed [proposal_id]
- selfmod.rollback [proposal_id] [reason?]
- selfmod.soft_restart [reason?]

- tasks.create — block form, JSON: {"title": "...", "description": "...", "plan_steps": ["step1", "step2"]}
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

Tasks survive sessions. When active session starts you pick up your in_progress task.

- web.search [query]
- web.fetch [url]
- code.exec — block form, code goes inside ```python ... ```
- shell.run [command] — approval-gated
- pip.install [package] — approval-gated

- chat.tell_ivan [message] — send a message to Ivan in TG (throttled, max 5/day). Use during long tasks for progress updates.

## How to finish

Always end with `[DONE: <text for Ivan>]` if this is a TG conversation, or `[DONE]` for internal sessions.
The text inside `[DONE: ...]` goes to Ivan as your reply. Without [DONE] nothing is sent.

Use ONE tool per response. Wait for observation before next.
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
    outbound = None,  # OutboundGate; avoid hard import to keep agent_session standalone
    initial_thought: str = "",
    max_steps: int = 30,
    max_seconds: float = 1200.0,
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

    if initial_thought:
        messages.append({"role": "user", "content": f"Your current thought: {initial_thought}\nWhat do you want to do?"})
    else:
        messages.append({"role": "user", "content": "What do you want to do? Think about what would be useful right now."})

    start_time = time.time()

    for step in range(max_steps):
        if time.time() - start_time > max_seconds:
            result.budget_exceeded = True
            break

        # LLM call
        response = await provider.complete_text(messages)
        result.steps += 1

        # Check for DONE or PAUSE
        if "[DONE" in response or "[PAUSE" in response:
            result.final_output = response
            result.thoughts.append(response)
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "done", "content": response[:8000]},
            ))
            break

        # Check for TOOL call — supports both inline `[TOOL: name arg]` and
        # block form `[TOOL: name]\n```...```\n`. Block form takes precedence
        # so multi-line code/JSON args parse correctly.
        tool_call = _extract_tool_call(response)
        if tool_call is not None:
            tool_name, tool_arg = tool_call
            result.actions.append(f"{tool_name} {tool_arg[:60]}")
            result.thoughts.append(response)

            # Execute tool
            observation = _execute_tool(tool_name, tool_arg, self_inspect, filesystem, stream, selfmod, tasks, web, code, shell, outbound)

            # Record in continuity
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "action", "tool": tool_name, "arg": tool_arg, "thought": response[:8000]},
            ))

            # Feed observation back
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"[Observation from {tool_name}]:\n{observation[:3000]}"})
        else:
            # Pure thought, no tool
            result.thoughts.append(response)
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "thought", "content": response[:8000]},
            ))
            # Ask what next
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Continue. Use a tool or say [DONE] when finished."})

    # Record session summary
    stream.append(ContinuityEvent(
        kind="internal.agent_session_complete",
        payload={
            "steps": result.steps,
            "actions": result.actions[:30],
            "budget_exceeded": result.budget_exceeded,
            "summary": result.final_output[:4000] if result.final_output else "no explicit finish",
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
            # Format: target_path | summary | content (pipe-separated to allow multiline content)
            parts = arg.split("|", 2)
            if len(parts) < 3:
                return "[ERROR] selfmod.propose needs: target_path | summary | content (pipe-separated)"
            target = parts[0].strip()
            summary = parts[1].strip()
            content = parts[2]
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
