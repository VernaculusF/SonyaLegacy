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
- filesystem.write [path] [content] — write a file

To use a tool, write: [TOOL: tool_name arg]
To finish, write: [DONE] or [DONE: summary]
"""


async def run_agent_session(
    *,
    provider: AgentProvider,
    stream: ContinuityStream,
    self_inspect: SelfInspectTool,
    filesystem: FilesystemTool,
    system_prompt: str,
    initial_thought: str = "",
    max_steps: int = 20,
    max_seconds: float = 300.0,
) -> SessionResult:
    """Run a ReAct agent session within the single stream.

    Returns when model says [DONE], budget exceeded, or max time hit.
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

        # Check for DONE
        if "[DONE" in response:
            result.final_output = response
            result.thoughts.append(response)
            stream.append(ContinuityEvent(
                kind="internal.agent_step",
                payload={"step": step, "type": "done", "content": response[:500]},
            ))
            break

        # Check for TOOL call
        tool_match = re.search(r'\[TOOL:\s*(\S+)\s*(.*?)\]', response)
        if tool_match:
            tool_name = tool_match.group(1)
            tool_arg = tool_match.group(2).strip()
            result.actions.append(f"{tool_name} {tool_arg}")
            result.thoughts.append(response)

            # Execute tool
            observation = _execute_tool(tool_name, tool_arg, self_inspect, filesystem)

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


def _execute_tool(name: str, arg: str, self_inspect: SelfInspectTool, filesystem: FilesystemTool) -> str:
    """Execute a tool by name. Returns observation string."""
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
            # Parse: first token = path, rest = content
            parts = arg.split(" ", 1)
            if len(parts) < 2:
                return "[ERROR] filesystem.write needs: path content"
            return filesystem.write(parts[0], parts[1])
        else:
            return f"[ERROR] Unknown tool: {name}"
    except Exception as e:
        return f"[ERROR] {type(e).__name__}: {e}"
