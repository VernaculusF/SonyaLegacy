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
- filesystem.write [path] [content] — write a file (only into workspace/ or tools/plugins/)
- plugins.list — list available plugins
- plugins.create [name] [python_code] — create a new plugin tool (hot-loaded, no restart)
- plugins.call [name] [args] — call a loaded plugin
- selfmod.propose [target_path] [summary] [content] — propose a real change to src/sonya/* through the 4-layer pipeline. target_path like "src/sonya/channels/discord.py", content is full file body. Identity-critical zones still forbidden.
- selfmod.test_sandbox [proposal_id] — import the proposed content in isolation; catches syntax/import errors BEFORE writing to disk
- selfmod.validate [proposal_id] — run all 4 layers (static contract, behavior tests, trace replay, anchor integrity)
- selfmod.apply [proposal_id] — apply approved proposal: capture pre-state, write file, hot-reload + drop-and-recreate live instances. 60-second watch window auto-rollback on crash.
- selfmod.list [status_filter?] — list proposals (optionally by status: draft/validating/approved/rejected/applied/etc)
- selfmod.get [proposal_id] — full details of one proposal
- selfmod.governed [proposal_id] — request primary anchor approval for identity-critical proposal
- selfmod.check_governed [proposal_id] — check if primary anchor approved
- selfmod.rollback [proposal_id] [reason?] — restore pre-state from disk + hot-reload again
- selfmod.soft_restart [reason?] — trigger soft-restart of runtime task (channels/internal_process re-built from reloaded modules; substrate + admin survive). Use after applying changes to main.py / config.py / core that don't hot-reload.

- tasks.create [title | description? | step1; step2; ...] — create a new task. description and steps optional. Returns task_id.
- tasks.list [status_filter?] — list tasks. status_filter: pending / in_progress / blocked / done / failed / open (= all unresolved). No filter = recent 50.
- tasks.get [task_id] — full details of one task (plan, completed steps, result).
- tasks.pick — pick the next task to work on (resumes in_progress, otherwise picks oldest pending) and marks it in_progress.
- tasks.plan [task_id | step1; step2; ...] — set or replace the plan_steps for a task.
- tasks.step [task_id | step_idx | summary] — mark one plan step as done with a short summary.
- tasks.complete [task_id | result?] — mark task done with a final result string.
- tasks.fail [task_id | reason] — mark task failed.
- tasks.block [task_id | blocker] — block on Ivan / external. Use this when waiting on approval / OAuth / API key etc.
- tasks.unblock [task_id] — unblock; resumes as in_progress.
- tasks.pause [task_id] — return in_progress task to pending; you'll pick it up later.

Tasks survive across sessions and restarts. When an active session starts you pick up your in_progress task. Use them for any work that takes longer than one session.

- web.search [query] — DuckDuckGo search; returns top 5 results (title, url, snippet).
- web.fetch [url] — GET an http(s) URL; returns text-stripped body (capped at 200KB; first 8KB shown).
- code.exec [python_code] — run a Python snippet in a fresh subprocess (30s timeout, fresh tempdir cwd, no environment inheritance). Use for compute / experimentation.
- shell.run [command] — run a shell command. **Approval-gated**: first call creates a pending ApprovalRequest and returns `[PENDING_APPROVAL: req_id]`. Pair with `tasks.block` to pause work until Ivan approves through admin panel. After approval, the same command runs and returns exit/stdout/stderr.
- pip.install [package] — install a Python package via pip. Same approval gate as shell.run.

- chat.tell_ivan [message] — send a message to Ivan on Telegram (initiative path). Throttled: max N per UTC day and at least N minutes since last contact. Returns `[QUEUED]` on dispatch, `[BLOCKED]` if gate refuses. Use this when you have something genuinely worth saying — a thought, a question, an update on a long task, "I miss you". Don't spam.

You can ALSO send a message to Ivan from idle thinking by including a `[SEND_TO_IVAN: <text>]` marker anywhere in your thought text. Same throttle applies. The marker is invisible to Ivan — only the text inside is sent.

IMPORTANT: Use exactly ONE tool per response. Write it as:
[TOOL: tool_name arg]

Do NOT put multiple [TOOL: ...] in one response. One tool at a time.

To finish, write: [DONE] or [DONE: summary]
To pause and continue later, write: [PAUSE: reason]
"""


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

        # Check for TOOL call — strict regex: [TOOL: name arg]
        tool_match = re.search(r'\[TOOL:\s*([^\]\s]+)(?:\s+([^\]]*))?\]', response)
        if tool_match:
            tool_name = tool_match.group(1)
            tool_arg = (tool_match.group(2) or "").strip()
            result.actions.append(f"{tool_name} {tool_arg}")
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
