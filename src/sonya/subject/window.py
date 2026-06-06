"""Unified `Window` abstraction over the 4 historic loop entry-points.

Background (Phase 2 of the unified-loop plan, MASTER §6.2 P1):
  Sonya currently has 4 separate functions running ReAct sessions:
    - InternalProcess._run_active_session   (every 2h, deep work, full tools)
    - InternalProcess._run_idle_thought     (every 30m, no tools, just text)
    - InternalProcess._run_task_worker_body (urgent tasks, 5 steps/60s)
    - main._on_incoming → run_tg_session    (TG reactive, 15 steps/150s)
  Each builds its own prompt, picks a provider, decides what tools to expose,
  chooses what counts as "done". This is the pre-RWKV cost-control workaround
  that grew into 4 parallel codepaths with subtle drift between them.

The plan (incremental, not big-bang):

  Phase 2A (this commit) — `Window` dataclass + thin `run_window()` wrapper.
    The 4 callers stay where they are; they just compose a Window instead of
    calling run_agent_session directly with N parameters. No behavior change.

  Phase 2B (next commit) — blocker reflex inside run_window. After every
    tool result, a heuristic checks for "looks blocked" markers (HTTP 4xx/5xx,
    exceptions, "credits", "rate limit", empty stdout >5s). If hit, an
    inline system message is injected before the next LLM turn telling the
    model what was blocked and asking for a different approach.

  Phase 2C — idle gets read-only tools (self_inspect, tasks.list, memory.recall,
    env.get, goals.list). Idle thought becomes a 1-3 step Window with limited
    tool surface, so Sonya can actually *check* state instead of guessing
    from context-builder injections.

  Phase 2D (later) — Scheduler picks Windows by priority. Today the 4 callers
    fire on independent timers, leading to "I'm waiting" while in fact nothing
    is queued.

Until 2D lands, this module is mostly a documentation + thin facade so caller
code reads `await run_window(window)` instead of `await run_agent_session(...)`
with 15 named parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sonya.state.continuity_stream import ContinuityStream
from sonya.subject.agent_session import (
    SessionResult,
    AgentProvider,
    run_agent_session,
)
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


# Window kinds. Used for routing + accountability + later scheduling.
WINDOW_KIND_TG = "tg_session"
WINDOW_KIND_ACTIVE = "active_session"
WINDOW_KIND_WORKER = "task_worker"
WINDOW_KIND_IDLE = "idle_thought"
WINDOW_KIND_PROJECT = "project_session"
WINDOW_KIND_SELF_EVO = "self_evolution"


@dataclass(slots=True)
class Window:
    """Description of one cognitive activation.

    A Window says: who's calling Sonya, what tools she has, how much budget,
    what initial context she sees. It does NOT pre-decide "done" — the model
    closes itself via [DONE]/[PAUSE]/budget exhaustion.

    Required:
      kind           — WINDOW_KIND_*; affects audit and (later) scheduling.
      system_prompt  — full assembled prompt (personality + memory + tasks +
                       channel suffix). Built by caller, not by run_window.
      tools          — dict of callable tool surfaces. None entries are skipped.

    Optional:
      initial_thought      — seed the first LLM turn with prior context.
      initial_user_text    — the literal incoming user message (TG path).
      initial_user_message — full chat-message-with-media (TG vision path).
      max_steps            — ReAct step cap (default per-kind).
      max_seconds          — wall-clock cap (default per-kind).
      outbound             — OutboundGate; if set, chat.tell_ivan is wired.
      inbox_drain          — () -> list[str], polled between steps for fresh
                              user turns mid-session (TG inbox-aware).
      purpose              — passed to provider for usage audit.
    """

    kind: str
    system_prompt: str
    tools: dict[str, Any]
    initial_thought: str = ""
    initial_user_text: str | None = None
    initial_user_message: list[dict[str, Any]] | None = None
    # Conversation history — list of {role: 'user'|'assistant', content: str}.
    # Goes between system prompt and initial_user_text so the LLM sees
    # continuity, not a cold start. Built by caller from continuity_events.
    prior_messages: list[dict[str, Any]] | None = None
    workspace_id: str = ""
    # Caller hint: this Window opened on an Ivan message that he is
    # actively waiting for a reply to. Forces the inbox-priority gate
    # in run_agent_session — chat.dialog must fire before [DONE]. Used
    # by the TG bridge and by active session when triggered by atrium.
    require_dialog_reply: bool = False
    max_steps: int = 0  # 0 = use per-kind default
    max_seconds: float = 0.0  # 0 = use per-kind default
    outbound: Any = None
    inbox_drain: Callable[[], list[str]] | None = None
    drives_callback: Callable[[], None] | None = None
    purpose: str = ""


_DEFAULT_BUDGETS: dict[str, tuple[int, float]] = {
    WINDOW_KIND_TG: (15, 150.0),
    # Active session: 60 steps / 30 min. Bumped from 30 because real tasks
    # (multi-step recon, selfmod cycle propose→validate→apply, register
    # multiple skills) regularly exceeded 30 steps and ate budget_exceeded.
    # Live audit on 2026-05-31: skill-creation session used 13 steps just
    # for one task; recon sessions on task-225 hit 30 cap repeatedly.
    # Time bucket stays 30min — that's the wall-clock cap for "she's busy
    # for too long, Ivan should see something move".
    WINDOW_KIND_ACTIVE: (60, 1800.0),
    WINDOW_KIND_WORKER: (5, 60.0),
    WINDOW_KIND_IDLE: (3, 60.0),
    WINDOW_KIND_PROJECT: (40, 1200.0),
    WINDOW_KIND_SELF_EVO: (20, 600.0),
}


def _resolve_budget(window: Window) -> tuple[int, float]:
    default_steps, default_seconds = _DEFAULT_BUDGETS.get(window.kind, (15, 300.0))
    steps = window.max_steps if window.max_steps > 0 else default_steps
    seconds = window.max_seconds if window.max_seconds > 0 else default_seconds
    return steps, seconds


async def run_window(
    window: Window,
    *,
    provider: AgentProvider,
    stream: ContinuityStream,
) -> SessionResult:
    """Execute a Window via the underlying agent session loop.

    Thin wrapper today. Phase 2B will add blocker reflex injection between
    steps. Phase 2C will let idle Windows run with a restricted tool subset
    (the tools dict will simply not include code/shell/web/selfmod for those).
    """
    steps, seconds = _resolve_budget(window)
    tools = window.tools or {}
    purpose = window.purpose or window.kind
    return await run_agent_session(
        provider=provider,
        stream=stream,
        self_inspect=tools.get("self_inspect"),
        filesystem=tools.get("filesystem"),
        system_prompt=window.system_prompt,
        selfmod=tools.get("selfmod"),
        tasks=tools.get("tasks"),
        web=tools.get("web"),
        code=tools.get("code"),
        shell=tools.get("shell"),
        memory=tools.get("memory"),
        env=tools.get("env"),
        skills=tools.get("skills"),
        knowledge=tools.get("knowledge"),
        providers=tools.get("providers"),
        browser=tools.get("browser"),
        projects=tools.get("projects"),
        outbound=window.outbound,
        initial_thought=window.initial_thought,
        initial_user_message=window.initial_user_message,
        initial_user_text=window.initial_user_text,
        prior_messages=window.prior_messages,
        workspace_id=window.workspace_id,
        require_dialog_reply=window.require_dialog_reply,
        max_steps=steps,
        max_seconds=seconds,
        purpose=purpose,
        inbox_drain=window.inbox_drain,
        drives_callback=window.drives_callback,
    )


__all__ = [
    "Window",
    "run_window",
    "WINDOW_KIND_TG",
    "WINDOW_KIND_ACTIVE",
    "WINDOW_KIND_WORKER",
    "WINDOW_KIND_IDLE",
    "WINDOW_KIND_PROJECT",
    "WINDOW_KIND_SELF_EVO",
]
