import asyncio
import json
import pytest
from pathlib import Path
from typing import Any

from sonya.state.substrate import Substrate
from sonya.providers.keystore import KeyStore
from sonya.tools.subagent_tool import SubagentTool
from sonya.subject.subagent_runner import SubagentRunner, SubagentTask
from sonya.subject.internal_loop import InternalProcess
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.pending import PendingIntentionStore


class _CapturingProvider:
    """Mock LLM Provider for deterministic subagent execution."""
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.last_messages: list[dict[str, Any]] = []
        self.calls = 0

    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        self.calls += 1
        self.last_messages = list(messages)
        return self._responses.pop(0) if self._responses else "[DONE]"


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "subagent.db")
    try:
        store = KeyStore(sub)
        # Seed test provider
        store.upsert_provider(
            provider_id="test_provider",
            display_name="Test Provider",
            adapter_kind="openai_compatible",
            status="active",
        )
        acc = store.add_provider_account(
            provider_id="test_provider",
            name="test-acc",
            secret_ref="manual:test"
        )
        store.upsert_provider_model(
            model_id="test_model",
            provider="test_provider",
            model_name="Test Model",
            text_loop_ok=1,
            enabled=1,
            role_preference="executor",
        )
        store.set_account_offering(acc.account_id, "test_model", enabled=True)
        yield sub
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_subagent_spawn_and_execution_success(substrate):
    # Setup mock provider that does a tool call then finishes
    provider = _CapturingProvider([
        "[TOOL: web.search] example query",
        '[DONE] {"result": "success", "data": [1, 2, 3]}'
    ])
    
    # Init tool and spawn
    tool = SubagentTool(substrate, provider=provider)
    spawn_res = tool.spawn('{"task": "test task", "provider": "test_provider", "model": "test_model"}')
    
    assert "[OK] Subagent spawned:" in spawn_res
    subagent_id = spawn_res.split("Subagent spawned: ")[1].split("\n")[0].strip()
    
    # Wait for the background task to complete
    assert subagent_id in tool._running
    await tool._running[subagent_id]
    
    # Check result
    result_str = tool.result(subagent_id)
    assert "Status: done" in result_str
    assert '{"result": "success", "data": [1, 2, 3]}' in result_str
    
    # Verify the LLM was called correctly
    assert provider.calls == 2
    last_msg = provider.last_messages[-1]
    assert last_msg["role"] == "user"
    assert "[OBS: web.search]" in last_msg["content"]


@pytest.mark.asyncio
async def test_subagent_emits_continuity_events_to_internal_loop(substrate):
    provider = _CapturingProvider([
        '[DONE] {"status": "ok"}'
    ])
    tool = SubagentTool(substrate, provider=provider)
    spawn_res = tool.spawn('{"task": "quick task"}')
    subagent_id = spawn_res.split("Subagent spawned: ")[1].split("\n")[0].strip()
    
    await tool._running[subagent_id]
    
    # Poll using internal loop mechanism
    stream = ContinuityStream(substrate)
    intentions = PendingIntentionStore(substrate)
    process = InternalProcess(stream, intentions, substrate=substrate)
    
    # Internal loop polling
    process._check_subagent_completions()
    
    # Verify continuity event was written
    events = list(stream.read_since(0))
    complete_events = [e for e in events if e.kind == "subagent.complete"]
    assert len(complete_events) == 1
    assert complete_events[0].payload["subagent_id"] == subagent_id
    assert complete_events[0].payload["status"] == "done"
    assert '{"status": "ok"}' in complete_events[0].payload.get("result", complete_events[0].payload.get("result_preview", ""))


@pytest.mark.asyncio
async def test_subagent_tool_restriction(substrate):
    # Try to use a tool that shouldn't exist in subagent (like drive mutations or unknown tool)
    provider = _CapturingProvider([
        "[TOOL: unknown.tool] hack",
        "[DONE] oops"
    ])
    
    tool = SubagentTool(substrate, provider=provider)
    spawn_res = tool.spawn('{"task": "hack task"}')
    subagent_id = spawn_res.split("Subagent spawned: ")[1].split("\n")[0].strip()
    
    await tool._running[subagent_id]
    
    assert provider.calls == 2
    last_msg = provider.last_messages[-1]
    assert "[OBS: unknown.tool]" in last_msg["content"]
    assert "[SKIP] tool 'unknown.tool' not available" in last_msg["content"]
