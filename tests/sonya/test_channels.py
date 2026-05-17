"""Tests for channel abstraction (registry, base contract)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from sonya.channels import (
    Channel,
    ChannelDeps,
    ChannelMessage,
    ChannelRegistry,
    OutgoingMessage,
)


class MockChannel:
    """In-memory channel for testing the registry contract."""

    def __init__(self, name: str = "mock") -> None:
        self.name = name
        self._running = False
        self._sent: list[tuple[str, OutgoingMessage]] = []
        self._fail_on_start = False
        self._deps: ChannelDeps | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, deps: ChannelDeps) -> None:
        if self._fail_on_start:
            raise RuntimeError("intentional start failure")
        self._deps = deps
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, chat_id: str, message: OutgoingMessage) -> None:
        if not self._running:
            raise RuntimeError("channel not running")
        self._sent.append((chat_id, message))

    async def simulate_incoming(self, msg: ChannelMessage) -> OutgoingMessage | None:
        """Test helper — pretend we got an inbound message."""
        if self._deps is None:
            return None
        return await self._deps.on_incoming(msg)


def test_channel_protocol_satisfied() -> None:
    ch = MockChannel()
    assert isinstance(ch, Channel)


def test_register_and_get() -> None:
    reg = ChannelRegistry()
    ch = MockChannel()
    reg.register(ch)
    assert reg.get("mock") is ch
    assert "mock" in reg.list_names()


def test_register_duplicate_raises() -> None:
    from sonya.channels.registry import ChannelRegistryError
    reg = ChannelRegistry()
    reg.register(MockChannel("a"))
    with pytest.raises(ChannelRegistryError):
        reg.register(MockChannel("a"))


@pytest.mark.asyncio
async def test_start_all_starts_each() -> None:
    reg = ChannelRegistry()
    a = MockChannel("a")
    b = MockChannel("b")
    reg.register(a)
    reg.register(b)

    deps = ChannelDeps(on_incoming=lambda m: _none_handler(m))
    await reg.start_all(deps)

    assert a.is_running
    assert b.is_running


@pytest.mark.asyncio
async def test_start_all_isolates_failures() -> None:
    reg = ChannelRegistry()
    bad = MockChannel("bad")
    bad._fail_on_start = True
    good = MockChannel("good")
    reg.register(bad)
    reg.register(good)

    deps = ChannelDeps(on_incoming=lambda m: _none_handler(m))
    await reg.start_all(deps)

    assert not bad.is_running
    assert good.is_running


@pytest.mark.asyncio
async def test_stop_all_stops_each() -> None:
    reg = ChannelRegistry()
    a = MockChannel("a")
    reg.register(a)
    deps = ChannelDeps(on_incoming=lambda m: _none_handler(m))
    await reg.start_all(deps)
    assert a.is_running

    await reg.stop_all()
    assert not a.is_running


@pytest.mark.asyncio
async def test_send_through_registry() -> None:
    reg = ChannelRegistry()
    ch = MockChannel("a")
    reg.register(ch)
    deps = ChannelDeps(on_incoming=lambda m: _none_handler(m))
    await reg.start_all(deps)

    ok = await reg.send("a", "chat-42", OutgoingMessage(text="hello"))
    assert ok
    assert ch._sent == [("chat-42", OutgoingMessage(text="hello"))]


@pytest.mark.asyncio
async def test_send_to_unknown_returns_false() -> None:
    reg = ChannelRegistry()
    ok = await reg.send("nope", "x", OutgoingMessage(text="x"))
    assert not ok


@pytest.mark.asyncio
async def test_send_to_stopped_returns_false() -> None:
    reg = ChannelRegistry()
    ch = MockChannel("a")
    reg.register(ch)
    # Don't start
    ok = await reg.send("a", "x", OutgoingMessage(text="x"))
    assert not ok


@pytest.mark.asyncio
async def test_incoming_routed_to_handler() -> None:
    received: list[ChannelMessage] = []

    async def handler(msg: ChannelMessage) -> OutgoingMessage | None:
        received.append(msg)
        return OutgoingMessage(text=f"echo:{msg.text}")

    reg = ChannelRegistry()
    ch = MockChannel("a")
    reg.register(ch)
    deps = ChannelDeps(on_incoming=handler)
    await reg.start_all(deps)

    msg = ChannelMessage(
        channel="a", chat_id="42", sender_id="user-1",
        text="hi", is_private=True,
    )
    response = await ch.simulate_incoming(msg)

    assert len(received) == 1
    assert received[0].text == "hi"
    assert response is not None
    assert response.text == "echo:hi"


def test_status() -> None:
    reg = ChannelRegistry()
    a = MockChannel("a")
    reg.register(a)
    status = reg.status()
    assert status == [{"name": "a", "running": False}]


async def _none_handler(_msg: ChannelMessage) -> OutgoingMessage | None:
    return None



# --- Auto-discovery via _build_channels in main ---


def test_build_channels_discovers_telegram_when_configured(tmp_path) -> None:
    """_build_channels finds telegram.py and calls its build(config)."""
    from sonya.config import AppConfig
    from sonya.main import _build_channels

    # Telegram needs api_id; with 0 the build returns None
    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
        tg_api_id=0,  # build() returns None
        tg_api_hash="",
        tg_session_path="",
        enable_telegram=True,
    )
    channels = _build_channels(cfg)
    # Should be empty because tg_api_id=0 means build() returned None
    assert channels == []


def test_build_channels_returns_telegram_when_credentials_present(tmp_path) -> None:
    from sonya.config import AppConfig
    from sonya.main import _build_channels

    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
        tg_api_id=12345,
        tg_api_hash="testhash",
        tg_session_path="./tg.session",
        enable_telegram=True,
    )
    channels = _build_channels(cfg)
    # TelegramChannel should be present
    names = [c.name for c in channels]
    assert "telegram" in names


def test_build_channels_skips_disabled_telegram(tmp_path) -> None:
    from sonya.config import AppConfig
    from sonya.main import _build_channels

    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
        tg_api_id=12345,
        tg_api_hash="testhash",
        tg_session_path="./tg.session",
        enable_telegram=False,  # disabled
    )
    channels = _build_channels(cfg)
    assert channels == []
