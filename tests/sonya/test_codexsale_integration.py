from __future__ import annotations

import asyncio

import pytest

from sonya.providers.keystore import KeyStore
from sonya.providers.llm_provider import LLMProvider
from sonya.state.substrate import Substrate
from sonya.tools.providers_tool import ProvidersTool
from sonya.tools.subagent_tool import SubagentTool


class _CaptureProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def complete_text(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return "[DONE] ok"


def test_providers_add_key_sets_codexsale_defaults(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "codex.db")
    try:
        out = ProvidersTool(sub).add_key(
            '{"provider":"codexsale","name":"codex-main","api_key":"sk-clb-test"}'
        )
        assert "[OK]" in out
        key = KeyStore(sub).list_keys("codexsale")[0]
        assert key.base_url == "https://codex.sale/v1"
        assert key.model == "gpt-5.4-mini"
    finally:
        sub.close()


def test_llm_provider_uses_explicit_provider_key(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "codex.db")
    try:
        store = KeyStore(sub)
        fw = store.add_key(
            provider="fireworks",
            name="fw",
            api_key="fw-key",
            base_url="https://fw.example/v1",
            model="accounts/fireworks/models/deepseek-v4-flash",
        )
        cx = store.add_key(
            provider="codexsale",
            name="cx",
            api_key="cx-key",
            base_url="https://codex.sale/v1",
            model="gpt-5.4-mini",
        )
        store.set_settings(active_provider="fireworks", default_model=fw.model, default_base_url=fw.base_url)

        async def _run() -> None:
            provider = LLMProvider(store)
            key = await store.acquire("codexsale")
            assert key is not None

        asyncio.run(_run())
        codex_key = next(k for k in store.list_keys() if k.provider == "codexsale")
        fw_key = next(k for k in store.list_keys() if k.provider == "fireworks")
        assert codex_key.request_count >= 1
        assert fw_key.request_count == 0
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_subagent_spawn_defaults_to_active_provider(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "codex.db")
    try:
        store = KeyStore(sub)
        store.set_settings(active_provider="codexsale", default_model="gpt-5.4-mini", default_base_url="https://codex.sale/v1")
        tool = SubagentTool(sub, provider=_CaptureProvider())
        out = tool.spawn('{"task":"check this"}')
        assert "provider: codexsale" in out
        await asyncio.gather(*tool._running.values())
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_subagent_runner_passes_explicit_provider(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "codex.db")
    try:
        fake = _CaptureProvider()
        tool = SubagentTool(sub, provider=fake)
        out = tool.spawn('{"task":"check this","provider":"codexsale","model":"gpt-5.4"}')
        assert "[OK]" in out
        task = next(iter(tool._running.values()))
        await asyncio.wait_for(task, timeout=2.0)
        assert fake.calls
        assert fake.calls[0]["_provider"] == "codexsale"
        assert fake.calls[0]["_model"] == "gpt-5.4"
    finally:
        sub.close()
