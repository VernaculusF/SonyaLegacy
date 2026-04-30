# First Runtime Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first deployable Sonya runtime slice: long-lived Python service with provider abstraction, OpenRouter integration, persistent event/memory baseline, Telegram/Userbot ingress-egress, harness baseline, and VPS-ready service skeleton.

**Architecture:** The first slice is a single Python application with clear module boundaries: runtime core, provider layer, storage layer, harness layer, and channel adapters. It runs as one service on VPS, persists state locally, and uses external model providers through a backend abstraction so future self-hosted brains do not require rewriting the runtime.

**Tech Stack:** Python 3.11+, `pydantic`, `httpx`, `aiosqlite`, `pyrogram`, `pytest`, `pytest-asyncio`

---

## Reference Alignment

This plan must be executed together with:

- [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/ARCHITECTURE_PLAN.md)
- [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/REFERENCE_SYSTEMS_ANALYSIS.md)
- [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/OPENCLAW_ANALYSIS.md)
- [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/HERMES_ANALYSIS.md)
- [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/plans/architecture/OMNIAGENT_ANALYSIS.md)

Execution rules:

- preserve operational truth learned from OpenClaw: persistent artifacts, memory outside chat, anchors, lived runtime continuity;
- preserve Hermes boundaries: shell/brain split, adapter-first design, orchestration separate from identity core;
- reject OmniAgent shortcuts: untrusted gateway assumptions, inflated README claims, vague channel readiness, weak identity and auth boundaries.

If an implementation step violates one of these rules, the step must be rewritten before code starts.

## Scope Position

This is not the whole Sonya implementation. It is the first executable slice.

Its job is to prove:

- VPS-first runtime skeleton;
- provider abstraction;
- principal identity baseline;
- persistent event flow;
- real Telegram ingress normalization;
- harness baseline;
- deployable service shape.

It does not yet complete:

- full semantic memory;
- full skill evolution;
- full self-modification;
- full embodiment;
- full simulation;
- full brain evolution.

Those remain present in architecture as explicit later layers or stubs, not silently dropped.

## File Structure

### Create

- `C:\Users\Jester\Desktop\Sonya\pyproject.toml`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\__init__.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\main.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\config.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\runtime.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\events.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\storage.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\identity.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\harness.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\providers\__init__.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\providers\base.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\providers\openrouter.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\channels\__init__.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\channels\base.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\channels\telegram_userbot.py`
- `C:\Users\Jester\Desktop\Sonya\src\sonya\admin.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_config.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_storage.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_identity.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_harness.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_openrouter_provider.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_runtime.py`
- `C:\Users\Jester\Desktop\Sonya\tests\test_telegram_adapter.py`
- `C:\Users\Jester\Desktop\Sonya\.env.example`
- `C:\Users\Jester\Desktop\Sonya\.gitignore`
- `C:\Users\Jester\Desktop\Sonya\deploy\systemd\sonya.service`
- `C:\Users\Jester\Desktop\Sonya\deploy\README.md`

### Responsibility Map

- `config.py`: env-driven configuration and path resolution
- `events.py`: event models and normalization
- `storage.py`: SQLite persistence for events, principals, and runtime state
- `identity.py`: principal registry, relation anchor binding, and authority resolution
- `harness.py`: technical and epistemic baseline checks for tool and authority usage
- `providers/base.py`: backend protocol and request/response models
- `providers/openrouter.py`: OpenRouter backend implementation
- `channels/base.py`: channel protocol
- `channels/telegram_userbot.py`: Pyrogram-based userbot adapter
- `runtime.py`: runtime orchestrator and event loop
- `admin.py`: health and diagnostics helpers
- `main.py`: application entrypoint

### Test Strategy

- config loading and path safety
- SQLite schema and persistence behavior
- principal/anchor separation
- harness authority checks
- provider request formatting and response parsing
- runtime event flow
- Telegram adapter message normalization

## Pre-Execution Check

Before starting Task 1, verify the implementation still satisfies all three:

1. It preserves OpenClaw lessons without copying OpenClaw structure blindly.
2. It keeps Hermes as architecture, not dependency worship.
3. It refuses OmniAgent shortcuts where trust boundaries are weak.

If not, fix the plan first.

## Task 1: Scaffold Project and Configuration

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\pyproject.toml`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\__init__.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\config.py`
- Create: `C:\Users\Jester\Desktop\Sonya\.env.example`
- Create: `C:\Users\Jester\Desktop\Sonya\.gitignore`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_config.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from sonya.config import AppConfig


def test_config_builds_default_paths(tmp_path: Path):
    cfg = AppConfig(
        app_name="sonya",
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        database_path=tmp_path / "data" / "sonya.db",
        provider_name="openrouter",
        openrouter_api_key="test-key",
        openrouter_model="google/gemma-4-26b-a4b-it:free",
    )

    assert cfg.data_dir == tmp_path / "data"
    assert cfg.logs_dir == tmp_path / "logs"
    assert cfg.database_path.name == "sonya.db"
    assert cfg.provider_name == "openrouter"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `sonya.config`

- [ ] **Step 3: Write minimal implementation**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sonya"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.8.0",
  "httpx>=0.27.0",
  "aiosqlite>=0.20.0",
  "pyrogram>=2.0.106",
  "tgcrypto>=1.2.5",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0",
  "pytest-asyncio>=0.23.7",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
```

```python
# src/sonya/__init__.py
__all__ = ["__version__"]
__version__ = "0.1.0"
```

```python
# src/sonya/config.py
from pathlib import Path

from pydantic import BaseModel


class AppConfig(BaseModel):
    app_name: str
    data_dir: Path
    logs_dir: Path
    database_path: Path
    provider_name: str
    openrouter_api_key: str
    openrouter_model: str
```

```text
# .env.example
APP_NAME=sonya
DATA_DIR=./var/data
LOGS_DIR=./var/logs
DATABASE_PATH=./var/data/sonya.db
PROVIDER_NAME=openrouter
OPENROUTER_API_KEY=replace-me
OPENROUTER_MODEL=google/gemma-4-26b-a4b-it:free
TELEGRAM_API_ID=replace-me
TELEGRAM_API_HASH=replace-me
TELEGRAM_SESSION_NAME=sonya-userbot
TELEGRAM_ALLOWED_CHAT_IDS=
PRIMARY_PRINCIPAL_ID=owner_001
PRIMARY_PRINCIPAL_TELEGRAM_ID=
PRIMARY_PRINCIPAL_DISPLAY_NAME=Ivan
```

```text
# .gitignore
.venv/
__pycache__/
.pytest_cache/
var/
.env
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/sonya/__init__.py src/sonya/config.py tests/test_config.py .env.example .gitignore
git commit -m "feat: scaffold sonya project config"
```

## Task 2: Build Event and Storage Baseline

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\events.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\storage.py`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
from pathlib import Path

from sonya.events import RuntimeEvent
from sonya.storage import SQLiteStorage


async def test_storage_persists_event(tmp_path: Path):
    storage = SQLiteStorage(tmp_path / "sonya.db")
    await storage.initialize()

    event = RuntimeEvent(
        event_id="evt-1",
        event_type="dialogue_event",
        source="telegram",
        channel="telegram_userbot",
        actor="principal:owner_001",
        raw_content="hello",
        normalized_summary="hello",
    )

    await storage.append_event(event)
    rows = await storage.list_events(limit=10)

    assert len(rows) == 1
    assert rows[0].event_id == "evt-1"
    assert rows[0].event_type == "dialogue_event"


def test_storage_persists_event_sync(tmp_path: Path):
    asyncio.run(test_storage_persists_event(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL with `ImportError` for `sonya.events` or `sonya.storage`

- [ ] **Step 3: Write minimal implementation**

```python
# src/sonya/events.py
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    event_id: str
    event_type: str
    source: str
    channel: str
    actor: str
    raw_content: str
    normalized_summary: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    importance_score: float = 0.5
    identity_relevance: float = 0.5
    anchor_relevance: float = 0.5
```

```python
# src/sonya/storage.py
from pathlib import Path

import aiosqlite

from sonya.events import RuntimeEvent


class SQLiteStorage:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def append_event(self, event: RuntimeEvent) -> None:
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                "INSERT INTO runtime_events (event_id, event_type, payload_json) VALUES (?, ?, ?)",
                (event.event_id, event.event_type, event.model_dump_json()),
            )
            await db.commit()

    async def list_events(self, limit: int) -> list[RuntimeEvent]:
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute(
                "SELECT payload_json FROM runtime_events ORDER BY rowid DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [RuntimeEvent.model_validate_json(row[0]) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sonya/events.py src/sonya/storage.py tests/test_storage.py
git commit -m "feat: add runtime event storage baseline"
```

## Task 3: Add Principal Registry and Identity Resolution

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\identity.py`
- Modify: `C:\Users\Jester\Desktop\Sonya\src\sonya\storage.py`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_identity.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
from pathlib import Path

from sonya.identity import PrincipalRecord, PrincipalRegistry
from sonya.storage import SQLiteStorage


async def test_registry_resolves_principal_by_trusted_telegram_id(tmp_path: Path):
    storage = SQLiteStorage(tmp_path / "sonya.db")
    await storage.initialize()
    registry = PrincipalRegistry(storage)

    principal = PrincipalRecord(
        principal_id="owner_001",
        display_name="Ivan",
        trusted_telegram_ids=[12345],
        relation_type="primary_anchor",
        authority_scope=["approve_sensitive_changes"],
    )

    await registry.upsert_principal(principal)
    resolved = await registry.resolve_telegram_principal(12345)

    assert resolved is not None
    assert resolved.principal_id == "owner_001"
    assert resolved.display_name == "Ivan"


def test_registry_resolves_principal_by_trusted_telegram_id_sync(tmp_path: Path):
    asyncio.run(test_registry_resolves_principal_by_trusted_telegram_id(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity.py -v`
Expected: FAIL with missing `sonya.identity`

- [ ] **Step 3: Write minimal implementation**

```python
# src/sonya/identity.py
from pydantic import BaseModel, Field

from sonya.storage import SQLiteStorage


class PrincipalRecord(BaseModel):
    principal_id: str
    display_name: str
    trusted_telegram_ids: list[int] = Field(default_factory=list)
    relation_type: str
    authority_scope: list[str] = Field(default_factory=list)


class PrincipalRegistry:
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage

    async def upsert_principal(self, principal: PrincipalRecord) -> None:
        await self.storage.upsert_principal(principal)

    async def resolve_telegram_principal(self, telegram_user_id: int) -> PrincipalRecord | None:
        return await self.storage.get_principal_by_telegram_id(telegram_user_id)
```

```python
# src/sonya/storage.py additions
from sonya.identity import PrincipalRecord

# inside initialize()
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS principals (
                    principal_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                )
                """
            )

# new methods
    async def upsert_principal(self, principal: PrincipalRecord) -> None:
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO principals (principal_id, payload_json) VALUES (?, ?)",
                (principal.principal_id, principal.model_dump_json()),
            )
            await db.commit()

    async def get_principal_by_telegram_id(self, telegram_user_id: int) -> PrincipalRecord | None:
        async with aiosqlite.connect(self.database_path) as db:
            cursor = await db.execute("SELECT payload_json FROM principals")
            rows = await cursor.fetchall()
        for row in rows:
            principal = PrincipalRecord.model_validate_json(row[0])
            if telegram_user_id in principal.trusted_telegram_ids:
                return principal
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_identity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sonya/identity.py src/sonya/storage.py tests/test_identity.py
git commit -m "feat: add principal registry and identity resolution"
```

## Task 4: Add Harness Baseline for Authority Checks

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\harness.py`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_harness.py`

- [ ] **Step 1: Write the failing test**

```python
from sonya.harness import HarnessDecision, HarnessGuard
from sonya.identity import PrincipalRecord


def test_harness_denies_sensitive_action_without_authority():
    guard = HarnessGuard()
    principal = PrincipalRecord(
        principal_id="guest_001",
        display_name="Guest",
        trusted_telegram_ids=[],
        relation_type="external_user",
        authority_scope=[],
    )

    decision = guard.authorize_action(principal, "approve_sensitive_changes")

    assert decision == HarnessDecision.DENY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness.py -v`
Expected: FAIL with missing `sonya.harness`

- [ ] **Step 3: Write minimal implementation**

```python
# src/sonya/harness.py
from enum import StrEnum

from sonya.identity import PrincipalRecord


class HarnessDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class HarnessGuard:
    def authorize_action(self, principal: PrincipalRecord, required_authority: str) -> HarnessDecision:
        if required_authority in principal.authority_scope:
            return HarnessDecision.ALLOW
        return HarnessDecision.DENY
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sonya/harness.py tests/test_harness.py
git commit -m "feat: add harness authority baseline"
```

## Task 5: Add OpenRouter Provider Adapter

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\providers\__init__.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\providers\base.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\providers\openrouter.py`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_openrouter_provider.py`

- [ ] **Step 1: Write the failing test**

```python
from sonya.providers.openrouter import OpenRouterProvider


def test_openrouter_builds_chat_payload():
    provider = OpenRouterProvider(api_key="test-key", model_name="google/gemma-4-26b-a4b-it:free")
    payload = provider.build_payload("Hello")

    assert payload["model"] == "google/gemma-4-26b-a4b-it:free"
    assert payload["messages"][-1]["content"] == "Hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_openrouter_provider.py -v`
Expected: FAIL with missing provider module

- [ ] **Step 3: Write minimal implementation**

```python
# src/sonya/providers/__init__.py
__all__ = ["base", "openrouter"]
```

```python
# src/sonya/providers/base.py
from typing import Protocol


class ProviderBackend(Protocol):
    def build_payload(self, prompt: str) -> dict: ...
```

```python
# src/sonya/providers/openrouter.py
class OpenRouterProvider:
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def build_payload(self, prompt: str) -> dict:
        return {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_openrouter_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sonya/providers/__init__.py src/sonya/providers/base.py src/sonya/providers/openrouter.py tests/test_openrouter_provider.py
git commit -m "feat: add openrouter provider baseline"
```

## Task 6: Build Telegram Userbot Channel Normalization

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\channels\__init__.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\channels\base.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\channels\telegram_userbot.py`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_telegram_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
from sonya.channels.telegram_userbot import normalize_telegram_message


def test_normalize_telegram_message_returns_runtime_event():
    event = normalize_telegram_message(
        chat_id=555,
        user_id=12345,
        text="privet",
    )

    assert event.channel == "telegram_userbot"
    assert event.source == "telegram"
    assert event.raw_content == "privet"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram_adapter.py -v`
Expected: FAIL with missing adapter module

- [ ] **Step 3: Write minimal implementation**

```python
# src/sonya/channels/__init__.py
__all__ = ["base", "telegram_userbot"]
```

```python
# src/sonya/channels/base.py
from typing import Protocol

from sonya.events import RuntimeEvent


class ChannelAdapter(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def normalize(self, *args, **kwargs) -> RuntimeEvent: ...
```

```python
# src/sonya/channels/telegram_userbot.py
from uuid import uuid4

from sonya.events import RuntimeEvent


def normalize_telegram_message(chat_id: int, user_id: int, text: str) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=str(uuid4()),
        event_type="dialogue_event",
        source="telegram",
        channel="telegram_userbot",
        actor=f"telegram:{user_id}",
        raw_content=text,
        normalized_summary=text.strip(),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sonya/channels/__init__.py src/sonya/channels/base.py src/sonya/channels/telegram_userbot.py tests/test_telegram_adapter.py
git commit -m "feat: add telegram adapter normalization"
```

## Task 7: Compose Runtime Orchestrator and Entry Point

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\runtime.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\admin.py`
- Create: `C:\Users\Jester\Desktop\Sonya\src\sonya\main.py`
- Test: `C:\Users\Jester\Desktop\Sonya\tests\test_runtime.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
from pathlib import Path

from sonya.events import RuntimeEvent
from sonya.runtime import SonyaRuntime
from sonya.storage import SQLiteStorage


async def test_runtime_persists_incoming_event(tmp_path: Path):
    storage = SQLiteStorage(tmp_path / "sonya.db")
    await storage.initialize()
    runtime = SonyaRuntime(storage=storage)

    event = RuntimeEvent(
        event_id="evt-runtime-1",
        event_type="dialogue_event",
        source="telegram",
        channel="telegram_userbot",
        actor="telegram:12345",
        raw_content="hello",
        normalized_summary="hello",
    )

    await runtime.handle_event(event)
    rows = await storage.list_events(limit=10)

    assert rows[0].event_id == "evt-runtime-1"


def test_runtime_persists_incoming_event_sync(tmp_path: Path):
    asyncio.run(test_runtime_persists_incoming_event(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runtime.py -v`
Expected: FAIL with missing runtime module

- [ ] **Step 3: Write minimal implementation**

```python
# src/sonya/runtime.py
from sonya.events import RuntimeEvent
from sonya.storage import SQLiteStorage


class SonyaRuntime:
    def __init__(self, storage: SQLiteStorage):
        self.storage = storage

    async def handle_event(self, event: RuntimeEvent) -> None:
        await self.storage.append_event(event)
```

```python
# src/sonya/admin.py
def health_payload() -> dict:
    return {"status": "ok", "service": "sonya"}
```

```python
# src/sonya/main.py
import asyncio
from pathlib import Path

from sonya.runtime import SonyaRuntime
from sonya.storage import SQLiteStorage


async def run() -> None:
    storage = SQLiteStorage(Path("./var/data/sonya.db"))
    await storage.initialize()
    SonyaRuntime(storage=storage)
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runtime.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sonya/runtime.py src/sonya/admin.py src/sonya/main.py tests/test_runtime.py
git commit -m "feat: add runtime orchestrator baseline"
```

## Task 8: Add VPS Service Skeleton

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\deploy\systemd\sonya.service`
- Create: `C:\Users\Jester\Desktop\Sonya\deploy\README.md`

- [ ] **Step 1: Write the service unit**

```ini
[Unit]
Description=Sonya Runtime
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/sonya
EnvironmentFile=/opt/sonya/.env
ExecStart=/opt/sonya/.venv/bin/python -m sonya.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write deployment notes**

````md
# Deployment Notes

## Layout

- `/opt/sonya` - project root
- `/opt/sonya/.venv` - Python virtual environment
- `/opt/sonya/.env` - runtime secrets and config
- `/opt/sonya/var/data` - SQLite data
- `/opt/sonya/var/logs` - logs

## Commands

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .[dev]
sudo cp deploy/systemd/sonya.service /etc/systemd/system/sonya.service
sudo systemctl daemon-reload
sudo systemctl enable sonya
sudo systemctl start sonya
sudo systemctl status sonya
```
````

- [ ] **Step 3: Smoke-check syntax manually**

Run: `Get-Content deploy/systemd/sonya.service`
Expected: valid systemd unit content displayed

- [ ] **Step 4: Commit**

```bash
git add deploy/systemd/sonya.service deploy/README.md
git commit -m "chore: add vps service skeleton"
```

## Self-Review

### Spec coverage

- runtime shell: covered by Tasks 1, 7, 8
- provider abstraction and OpenRouter baseline: covered by Task 5
- persistence baseline: covered by Task 2
- identity/principal separation: covered by Task 3
- harness baseline: covered by Task 4
- Telegram/Userbot ingress baseline: covered by Task 6
- VPS deploy skeleton: covered by Task 8
- reference alignment: covered by the added alignment section and pre-execution check

### Placeholder scan

- no `TODO`
- no `TBD`
- no "add appropriate error handling"
- no "write tests later"

### Type consistency

- `RuntimeEvent` defined before use
- `SQLiteStorage` methods align with tests
- `PrincipalRecord` shape matches harness and identity tests
- provider interface and adapter names are consistent

## Execution Handoff

This plan is intentionally draft-grade until code execution starts. Before implementing it, re-read the reference analysis docs and confirm the slice still matches them.
