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
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool
from sonya.tools.selfmod_tool import SelfModTool


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
- selfmod.validate [proposal_id] — run all 4 layers (static contract, behavior tests, trace replay, anchor integrity)
- selfmod.apply [proposal_id] — apply approved proposal to disk (writes target file). Process restart needed unless target is a hot-loaded module.
- selfmod.list [status_filter?] — list proposals (optionally by status: draft/validating/approved/rejected/applied/etc)
- selfmod.get [proposal_id] — full details of one proposal
- selfmod.governed [proposal_id] — request primary anchor approval for identity-critical proposal
- selfmod.check_governed [proposal_id] — check if primary anchor approved
- selfmod.rollback [proposal_id] [reason?] — mark applied proposal as REVERTED (manual file revert still needed)

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
                payload={"step": step, "type": "done", "content": response[:500]},
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
            observation = _execute_tool(tool_name, tool_arg, self_inspect, filesystem, stream, selfmod)

            # Record in continuity
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "action", "tool": tool_name, "arg": tool_arg, "thought": response[:300]},
            ))

            # Feed observation back
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"[Observation from {tool_name}]:\n{observation[:3000]}"})
        else:
            # Pure thought, no tool
            result.thoughts.append(response)
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "thought", "content": response[:500]},
            ))
            # Ask what next
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Continue. Use a tool or say [DONE] when finished."})

    # Record session summary
    stream.append(ContinuityEvent(
        kind="internal.agent_session_complete",
        payload={
            "steps": result.steps,
            "actions": result.actions[:10],
            "budget_exceeded": result.budget_exceeded,
            "summary": result.final_output[:300] if result.final_output else "no explicit finish",
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
