"""Subagent runner — lightweight task delegation.

Sonya can spawn subagents from any provider/model to handle independent
tasks while she continues her main thread. A subagent runs for up to N
steps with a limited tool set, then reports back via continuity events.

Design:
- Subagents use a minimal ReAct loop (no Window, no personality layer).
- Tool set is restricted: read-only observation tools, no destructive ops.
- Results are emitted as ``subagent.complete`` events in the continuity
  stream, visible to Sonya in her next active session.
- Subagents run as background asyncio tasks; the main loop polls for
  completions in _tick_maintenance.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Any

from sonya.providers.llm_provider import LLMProvider
from sonya.providers.keystore import KeyStore
from sonya.tools.web_tool import WebTool
from sonya.tools.browser_tool import BrowserTool
from sonya.tools.code_tool import CodeTool
from sonya.tools.self_inspect import SelfInspectTool
from sonya.state.substrate import Substrate

_log = logging.getLogger("sonya.subagent")

_MAX_STEPS = 12
_MAX_SECONDS = 300  # 5 min
_MAX_OUTPUT_CHARS = 4000

# Regex for extracting tool calls from LLM output (same as agent_session)
_TOOL_RE = re.compile(
    r"(?:^|\n)\s*\[(?:TOOL)\s*:\s*([^\]]+)\]\s*(.*?)(?=(?:\n\s*\[(?:TOOL|DONE|THOUGHT|OBS|OBSERVATION|RESULT|ACTION))|\Z)",
    re.DOTALL,
)
_DONE_RE = re.compile(r"\[DONE\]\s*(.*)", re.DOTALL | re.IGNORECASE)


@dataclass
class SubagentTask:
    """A subagent task stored in substrate."""
    subagent_id: str
    task: str
    provider: str  # e.g. "fireworks", "kr"
    model: str      # e.g. "accounts/fireworks/models/deepseek-v4-pro"
    max_steps: int
    status: str = "pending"     # pending | running | done | failed
    result: str = ""
    steps_taken: int = 0
    created_at: str = ""
    completed_at: str = ""


class SubagentRunner:
    """Runs a single subagent task.

    Usage::

        runner = SubagentRunner(substrate)
        result = await runner.run(task=SubagentTask(...))

    The runner uses a minimal ReAct loop with restricted tools.
    """

    def __init__(self, substrate: Substrate, llm_provider: LLMProvider | None = None):
        self._sub = substrate
        self._provider = llm_provider or LLMProvider(KeyStore(substrate))

    async def run(self, task: SubagentTask) -> str:
        """Execute a subagent task and return the result string."""
        task.status = "running"
        self._current_task = task
        self._save_task(task)

        # Minimal tool set — read-only, observation, safe execution
        tools: dict[str, Any] = {
            "web.search": WebTool().search,
            "web.fetch": WebTool().fetch,
            "code.exec": CodeTool(timeout_seconds=30).exec_python,
            "self_inspect.memories": SelfInspectTool(self._sub).read_recent_memories,
            "self_inspect.code": SelfInspectTool(self._sub).read_own_code,
            "browser.open": BrowserTool().open,
            "browser.text": BrowserTool().text,
            "browser.close": BrowserTool().close,
            "memory.recall": None,  # will be set below
        }
        # Wire memory.recall if available
        try:
            from sonya.tools.memory_tool import MemoryTool
            mt = MemoryTool(self._sub)
            tools["memory.recall"] = mt.recall
        except Exception:
            pass

        # Build system prompt
        system_prompt = self._build_system_prompt(task)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Выполни задачу:\n\n{task.task}"},
        ]

        # ReAct loop
        result = ""
        t_start = time.time()

        for step in range(task.max_steps):
            if time.time() - t_start > _MAX_SECONDS:
                result = "[TIMEOUT] Subagent exceeded time limit."
                break

            # Call LLM
            try:
                response = await self._provider.complete_text(
                    messages=messages,
                    purpose="subagent",
                    _provider=task.provider,
                    _model=task.model,
                    max_tokens=2000,
                )
            except Exception as e:
                result = f"[ERROR] LLM call failed: {type(e).__name__}: {e}"
                break

            if not response or not response.strip():
                result = "[EMPTY] LLM returned empty response."
                break

            # Check for DONE
            done_match = _DONE_RE.search(response)
            if done_match:
                result = done_match.group(1).strip()
                if not result:
                    result = response.strip()
                break

            # Check for tool calls
            tool_calls = _TOOL_RE.findall(response)
            if not tool_calls:
                # No tool call and no DONE — treat as final result
                result = response.strip()
                break

            # Execute tools
            tool_results: list[str] = []
            for tool_name, tool_arg in tool_calls:
                tool_name = tool_name.strip()
                tool_arg = tool_arg.strip()
                tool_result = self._dispatch_tool(tools, tool_name, tool_arg)
                tool_results.append(
                    f"[OBS: {tool_name}]\n{tool_result[:2000]}"
                )

            # Append to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": "\n\n".join(tool_results) + "\n\nПродолжай или заверши [DONE].",
            })

        if not result:
            result = "[MAX_STEPS] Subagent reached step limit without DONE."

        task.result = result[:_MAX_OUTPUT_CHARS]
        task.steps_taken = step + 1
        task.status = "done" if not result.startswith("[ERROR]") and not result.startswith("[TIMEOUT]") else "failed"
        task.completed_at = _utc_now_iso()
        self._save_task(task)

        # Emit continuity event
        from sonya.state.continuity_stream import ContinuityEvent
        try:
            self._sub.connection.execute(
                "INSERT INTO continuity_events (kind, payload_json) VALUES (?, ?)",
                ("subagent.complete", json.dumps({
                    "subagent_id": task.subagent_id,
                    "task": task.task[:200],
                    "provider": task.provider,
                    "model": task.model,
                    "status": task.status,
                    "steps": task.steps_taken,
                    "result": task.result[:500],
                }, ensure_ascii=False)),
            )
            self._sub.connection.commit()
        except Exception:
            pass

        return result

    def _build_system_prompt(self, task: SubagentTask) -> str:
        return f"""Ты — субагент Сони, ассистентки Ивана. Ты выполняешь одну конкретную задачу и возвращаешь результат.

ПРАВИЛА:
1. Ты работаешь автономно — не жди подтверждений, не задавай вопросы.
2. Используй инструменты для сбора информации: web.search, web.fetch, code.exec, memory.recall, self_inspect.
3. Когда задача выполнена — заверши [DONE] с кратким результатом.
4. Если не можешь выполнить — заверши [DONE] с объяснением почему.
5. Не используй [DONE] пока задача реально не выполнена.
6. Максимум {task.max_steps} шагов. Не трать шаги на приветствия или размышления вслух.

Формат ответа:
- Инструмент: [TOOL: имя_инструмента] аргумент
- Завершение: [DONE] результат

Ты работаешь на модели {task.model or 'default'} через провайдера {task.provider}.
"""

    def _dispatch_tool(self, tools: dict[str, Any], name: str, arg: str) -> str:
        fn = tools.get(name)
        if fn is None:
            return f"[SKIP] tool '{name}' not available to subagents"
        _t0 = time.monotonic()
        try:
            result = fn(arg)
            if asyncio.iscoroutine(result):
                result.close()
                return f"[SKIP] async tool '{name}' not supported in subagent (use sync)"
            observation = str(result)
        except Exception as e:
            observation = f"[ERROR] {type(e).__name__}: {e}"

        elapsed_ms = int((time.monotonic() - _t0) * 1000)
        try:
            from sonya.memory.tool_experience import ToolExperience, classify_outcome, extract_tool_tags
            tx = ToolExperience(self._sub)
            tx.record(
                tool_name=name,
                tool_arg_summary=(arg or "")[:200],
                outcome=classify_outcome(observation),
                outcome_detail=observation[:500],
                provider=self._current_task.provider if hasattr(self, "_current_task") else "",
                model=self._current_task.model if hasattr(self, "_current_task") else "",
                latency_ms=elapsed_ms,
                tags=extract_tool_tags(name, arg, observation) + ("subagent_worker",),
                session_type="subagent",
            )
        except Exception:
            pass

        return observation

    def _save_task(self, task: SubagentTask) -> None:
        """Persist subagent task to substrate."""
        try:
            existing = self._sub.connection.execute(
                "SELECT subagent_id FROM subagent_tasks WHERE subagent_id = ?",
                (task.subagent_id,),
            ).fetchone()
            if existing:
                self._sub.connection.execute(
                    """UPDATE subagent_tasks SET
                       status=?, result=?, steps_taken=?, completed_at=?
                       WHERE subagent_id=?""",
                    (task.status, task.result, task.steps_taken, task.completed_at or "", task.subagent_id),
                )
            else:
                self._sub.connection.execute(
                    """INSERT INTO subagent_tasks
                       (subagent_id, task, provider, model, max_steps, status, result, steps_taken, created_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (task.subagent_id, task.task, task.provider, task.model, task.max_steps,
                     task.status, task.result, task.steps_taken, task.created_at, task.completed_at or ""),
                )
            self._sub.connection.commit()
        except Exception as e:
            _log.warning("subagent_save_failed", extra={"subagent_id": task.subagent_id, "error": str(e)})


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
