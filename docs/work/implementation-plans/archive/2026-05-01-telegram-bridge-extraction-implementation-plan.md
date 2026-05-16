# Telegram Bridge Extraction Implementation Plan

**Status:** Archived
**Archived:** 2026-05-13
**Superseded by:** the real code under `packages/tg-bridge` (+ its tests) and the runtime wiring described in [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md)
**Type:** Work Doc
**Scope:** Historical stepwise plan for extracting the working OpenClaw Telegram bridge into a reusable Sonya package
**Depends on:** [2026-04-30-telegram-bridge-extraction-design.md](C:/Users/Jester/Desktop/Sonya/docs/work/designs/2026-04-30-telegram-bridge-extraction-design.md), [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md), [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md), [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)
**Used by:** historical reference only
**Last reviewed:** 2026-05-13

> **Archived note (2026-05-13):** Every task in this plan was executed. The bridge now lives under `packages/tg-bridge`, is covered by tests in `packages/tg-bridge/tests`, and is wired to the reusable runtime slice at `src/sonya_runtime`. For the current shape of the bridge and how it plugs into `sonya_runtime`, read [architecture/CHANNELS_AND_TELEGRAM_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/CHANNELS_AND_TELEGRAM_PLAN.md) and [architecture/TASK_AND_ACTION_RUNTIME_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/TASK_AND_ACTION_RUNTIME_PLAN.md) instead of this plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the working OpenClaw Telegram bridge into the Sonya repository as a reusable, test-covered package while preserving current behavior and keeping `.openclaw` as the host runtime environment.

**Architecture:** The extraction is wrapper-first and parity-driven. The code moves from a single OpenClaw `telegram-bridge.mjs` runtime into a Python package under `packages/tg-bridge`, with a strict OpenClaw host adapter isolating all host-specific file topology, memory hooks, and runtime contracts.

**Tech Stack:** Python 3.11+, `pytest`, `pytest-asyncio`, `httpx`, `pydantic`, `respx` or `httpx.MockTransport`, standard library `pathlib`, `json`, `subprocess`

---

## Reference Inputs

This plan must be implemented together with:

- [2026-04-30-telegram-bridge-extraction-design.md](C:/Users/Jester/Desktop/Sonya/docs/work/designs/2026-04-30-telegram-bridge-extraction-design.md)
- [ARCHITECTURE_PLAN.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/ARCHITECTURE_PLAN.md)
- [REFERENCE_SYSTEMS_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/REFERENCE_SYSTEMS_ANALYSIS.md)
- [OPENCLAW_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OPENCLAW_ANALYSIS.md)
- [HERMES_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/HERMES_ANALYSIS.md)
- [OMNIAGENT_ANALYSIS.md](C:/Users/Jester/Desktop/Sonya/docs/architecture/reference/OMNIAGENT_ANALYSIS.md)

Implementation rules:

- preserve OpenClaw operational behavior before optimizing internals;
- do not introduce dead compatibility layers;
- do not move OpenClaw memory system into this package;
- keep `.openclaw` as host runtime and consumer during this migration;
- use tests as parity guards, not as afterthoughts.

## File Structure

### Create

- `C:\Users\Jester\Desktop\Sonya\pyproject.toml`
- `C:\Users\Jester\Desktop\Sonya\.gitignore`
- `C:\Users\Jester\Desktop\Sonya\README.md`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\README.md`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\pyproject.toml`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\__init__.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\app.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\paths.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\config.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\state.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\sessions.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\logging.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\bootstrap.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\prompts.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\formatting.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\media.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\telegram_api.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\model_client.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\hooks.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\handlers.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\update_loop.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\adapters\__init__.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\adapters\openclaw.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\telegram_update_text.json`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\telegram_update_photo.json`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\telegram_update_sticker.json`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\openrouter_image_stream.txt`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_formatting.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_media.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_sessions.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_bootstrap.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_model_client.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_handlers.py`
- `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_openclaw_adapter.py`
- `C:\Users\Jester\Desktop\Sonya\scripts\run-openclaw-bridge.ps1`

### Modify

- `C:\Users\Jester\.openclaw\start-telegram-bridge.cmd`
- `C:\Users\Jester\.openclaw\gateway.cmd`

### Responsibility Map

- root `pyproject.toml`: workspace package/tooling baseline
- package `pyproject.toml`: package-local metadata and test config
- `paths.py`: bridge path contracts
- `config.py`: bridge-relevant host config parsing
- `state.py`: Telegram update offset persistence
- `sessions.py`: rolling per-chat session storage
- `logging.py`: append-only runtime log helpers
- `bootstrap.py`: workspace anchor and memory context loading
- `prompts.py`: prompt assembly using bootstrap + short session history
- `formatting.py`: Telegram-safe formatting and chunking
- `media.py`: input classification, attachment extraction, stream parsing
- `telegram_api.py`: Telegram HTTP API wrappers
- `model_client.py`: omniroute/OpenRouter-compatible completion calls
- `hooks.py`: post-response hook invocation
- `handlers.py`: per-update decision paths
- `update_loop.py`: bridge polling loop
- `adapters/openclaw.py`: all OpenClaw-specific filesystem and runtime assumptions
- `app.py`: package composition root
- `scripts/run-openclaw-bridge.ps1`: repo-local entrypoint for OpenClaw bridge execution

## Task 1: Bootstrap Repository and Package Skeleton

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\pyproject.toml`
- Create: `C:\Users\Jester\Desktop\Sonya\.gitignore`
- Create: `C:\Users\Jester\Desktop\Sonya\README.md`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\README.md`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\pyproject.toml`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\__init__.py`

- [ ] **Step 1: Write the failing test**

```python
from importlib.metadata import version


def test_package_metadata_exists():
    assert version("tg-bridge") == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests -v`
Expected: FAIL because package metadata and test tree do not exist yet

- [ ] **Step 3: Write minimal implementation**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sonya-workspace"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []
```

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tg-bridge"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27.0",
  "pydantic>=2.8.0",
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
__all__ = ["__version__"]
__version__ = "0.1.0"
```

```text
.venv/
__pycache__/
.pytest_cache/
dist/
build/
*.egg-info/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests -v`
Expected: PASS for metadata presence once package and basic test tree exist

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore README.md packages/tg-bridge
git commit -m "feat: scaffold telegram userbot package"
```

## Task 2: Port Formatting Helpers with Parity Tests

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\formatting.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_formatting.py`

- [ ] **Step 1: Write the failing test**

```python
from tg_bridge.formatting import chunk_plain_text, render_telegram_html


def test_render_telegram_html_formats_headings_code_and_bullets():
    input_text = "**Formatting:**\n\nUse `parse_mode`.\n\n- one\n- two"
    output = render_telegram_html(input_text)
    assert "<b>Formatting:</b>" in output
    assert "<code>parse_mode</code>" in output
    assert "- one" in output


def test_chunk_plain_text_splits_long_text():
    text = "\n\n".join(["a" * 2000, "b" * 2000, "c" * 2000])
    chunks = chunk_plain_text(text, 3500)
    assert len(chunks) == 3
    assert all(len(chunk) <= 3500 for chunk in chunks)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_formatting.py -v`
Expected: FAIL with missing module

- [ ] **Step 3: Write minimal implementation**

Port behavior from:
- [telegram-bridge-format.mjs](C:/Users/Jester/.openclaw/workspace/tools/telegram-bridge-format.mjs)

Required exported functions:

```python
def render_telegram_html(markdown_text: str) -> str: ...
def chunk_plain_text(text: str, max_len: int = 3500) -> list[str]: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_formatting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/formatting.py packages/tg-bridge/tests/test_formatting.py
git commit -m "feat: port telegram formatting helpers"
```

## Task 3: Port Media Helpers with Fixtures

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\media.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\telegram_update_photo.json`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\telegram_update_sticker.json`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\openrouter_image_stream.txt`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_media.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from tg_bridge.media import classify_prompt, extract_telegram_input, parse_openrouter_event_stream


def test_classify_prompt_detects_image_generation():
    assert classify_prompt("/img red square", False) == "image_generation"
    assert classify_prompt("hello", False) == "text"


def test_extract_telegram_input_uses_best_photo(tmp_path: Path):
    payload = json.loads((Path(__file__).parent / "fixtures" / "telegram_update_photo.json").read_text(encoding="utf-8"))
    result = extract_telegram_input(payload)
    assert result.mode == "vision"
    assert result.attachments[0]["file_id"] == "big"


def test_parse_openrouter_event_stream_extracts_images():
    raw = (Path(__file__).parent / "fixtures" / "openrouter_image_stream.txt").read_text(encoding="utf-8")
    parsed = parse_openrouter_event_stream(raw)
    assert len(parsed["images"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_media.py -v`
Expected: FAIL with missing module or fixtures

- [ ] **Step 3: Write minimal implementation**

Port behavior from:
- [telegram-bridge-media.mjs](C:/Users/Jester/.openclaw/workspace/tools/telegram-bridge-media.mjs)

Required exported functions:

```python
def classify_prompt(text: str, has_image: bool = False) -> str: ...
def extract_telegram_input(update: dict) -> object: ...
def parse_openrouter_event_stream(raw_text: str) -> dict: ...
```

Fixtures must preserve current OpenClaw assumptions:
- best-photo selection by file size
- sticker fallback prompt
- event stream image extraction

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_media.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/media.py packages/tg-bridge/tests
git commit -m "feat: port telegram media helpers"
```

## Task 4: Implement State and Session Persistence

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\state.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\sessions.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_sessions.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from tg_bridge.sessions import load_session, save_session
from tg_bridge.state import read_state, write_state


def test_state_round_trip(tmp_path: Path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {"offset": 123})
    assert read_state(state_path)["offset"] == 123


def test_session_is_truncated_to_last_20_messages(tmp_path: Path):
    session_dir = tmp_path / "sessions"
    payload = {"messages": [{"role": "user", "content": str(i)} for i in range(30)]}
    save_session(session_dir, 555, payload)
    loaded = load_session(session_dir, 555)
    assert len(loaded["messages"]) == 20
    assert loaded["messages"][0]["content"] == "10"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_sessions.py -v`
Expected: FAIL with missing modules

- [ ] **Step 3: Write minimal implementation**

Implement parity with current bridge behavior:
- state defaults to `{"offset": 0}` when missing
- session defaults to `{"messages": []}` when missing
- session save truncates to last 20 messages

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_sessions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/state.py packages/tg-bridge/src/tg_bridge/sessions.py packages/tg-bridge/tests/test_sessions.py
git commit -m "feat: add bridge state and session persistence"
```

## Task 5: Implement OpenClaw Paths, Config, and Bootstrap Loader

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\paths.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\config.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\bootstrap.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\adapters\__init__.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\adapters\openclaw.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_bootstrap.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_openclaw_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from tg_bridge.adapters.openclaw import OpenClawHost


def test_openclaw_host_resolves_expected_paths():
    host = OpenClawHost(Path(r"C:\Users\Jester\.openclaw"))
    assert host.config_path.name == "openclaw.json"
    assert host.workspace_root.name == "workspace"
    assert host.bridge_log_path.name == "telegram-bridge.log"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_openclaw_adapter.py -v`
Expected: FAIL with missing module

- [ ] **Step 3: Write minimal implementation**

Required behavior:
- centralize all `.openclaw` path assumptions in adapter
- load `openclaw.json` with BOM-safe reading
- expose workspace anchor file paths
- expose `context_loader.py` and `post_response_hook.py` script paths
- expose media, raw updates, state, session, and log paths

`bootstrap.py` must preserve:
- reading `AGENTS.md`, `SOUL.md`, `HEARTBEAT.md`, optional `IDENTITY.md`
- invoking `context_loader.py full 7`
- returning the same bootstrap payload shape needed by prompt assembly

- [ ] **Step 4: Run tests to verify they pass**

Run:
- `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_bootstrap.py -v`
- `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_openclaw_adapter.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/paths.py packages/tg-bridge/src/tg_bridge/config.py packages/tg-bridge/src/tg_bridge/bootstrap.py packages/tg-bridge/src/tg_bridge/adapters packages/tg-bridge/tests/test_bootstrap.py packages/tg-bridge/tests/test_openclaw_adapter.py
git commit -m "feat: add openclaw host adapter and bootstrap loader"
```

## Task 6: Implement Prompt Assembly and Model Client

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\prompts.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\src\tg_bridge\model_client.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_model_client.py`

- [ ] **Step 1: Write the failing test**

```python
from tg_bridge.model_client import resolve_model_name
from tg_bridge.prompts import build_messages


def test_resolve_model_name_strips_omniroute_prefix():
    cfg = {"agents": {"defaults": {"model": "omniroute/openrouter/google/gemma-4-26b-a4b-it:free"}}}
    assert resolve_model_name(cfg) == "openrouter/google/gemma-4-26b-a4b-it:free"


def test_build_messages_includes_bootstrap_and_user_message():
    bootstrap = {"agents": "a", "soul": "b", "heartbeat": "c", "identity": "", "memoryContext": "d"}
    session = {"messages": []}
    messages = build_messages(bootstrap, session, "hello", "English")
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_model_client.py -v`
Expected: FAIL with missing module

- [ ] **Step 3: Write minimal implementation**

Implement:
- model resolution from OpenClaw config
- payload builders for text, vision, and image generation
- response parsing for text payloads
- event-stream image response parsing path wired to `media.py`

Use `httpx` transport injection or mockable client design so tests do not hit network.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_model_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/prompts.py packages/tg-bridge/src/tg_bridge/model_client.py packages/tg-bridge/tests/test_model_client.py
git commit -m "feat: add prompt assembly and model client"
```

## Task 7: Implement Telegram API Wrapper, Hooks, and Handlers

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\telegram_api.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\hooks.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\handlers.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\fixtures\telegram_update_text.json`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_handlers.py`

- [ ] **Step 1: Write the failing test**

```python
from tg_bridge.handlers import should_allow_sender


def test_should_allow_sender_checks_allowlist():
    allowed = {"5785127604"}
    assert should_allow_sender(allowed, "5785127604", "5785127604") is True
    assert should_allow_sender(allowed, "123", "456") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_handlers.py -v`
Expected: FAIL with missing module

- [ ] **Step 3: Write minimal implementation**

Required behavior:
- `/start` returns current OpenClaw bridge online text
- allowlist matches current bridge logic
- text path uses text completion
- media path uses vision completion
- image-generation path sends photo(s) then optional text
- post-response hook receives:
  - `OPENCLAW_SESSION_ID`
  - `OPENCLAW_LAST_USER_MSG`
  - `OPENCLAW_LAST_ASSISTANT_MSG`

Network-side Telegram HTTP functions must be mockable.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests\test_handlers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/telegram_api.py packages/tg-bridge/src/tg_bridge/hooks.py packages/tg-bridge/src/tg_bridge/handlers.py packages/tg-bridge/tests/test_handlers.py packages/tg-bridge/tests/fixtures/telegram_update_text.json
git commit -m "feat: add telegram api wrapper and update handlers"
```

## Task 8: Implement Poll Loop and App Composition Root

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\logging.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\update_loop.py`
- Create: `C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\src\tg_bridge\app.py`

- [ ] **Step 1: Write the failing test**

```python
from tg_bridge.logging import format_error


def test_format_error_includes_cause_when_present():
    err = RuntimeError("outer")
    err.__cause__ = ValueError("inner")
    text = format_error(err)
    assert "outer" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests -k logging -v`
Expected: FAIL with missing module

- [ ] **Step 3: Write minimal implementation**

Required behavior:
- append-only bridge log writes
- polling loop with update offset persistence
- raw update append to JSONL
- error backoff on poll failure
- top-level `app.py` composition with OpenClaw adapter

- [ ] **Step 4: Run focused verification**

Run:
- `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests -v`

Expected: all existing package tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge/src/tg_bridge/logging.py packages/tg-bridge/src/tg_bridge/update_loop.py packages/tg-bridge/src/tg_bridge/app.py
git commit -m "feat: add bridge polling loop and app composition"
```

## Task 9: Add Repo Entry Script and Switch OpenClaw Launch Path

**Files:**
- Create: `C:\Users\Jester\Desktop\Sonya\scripts\run-openclaw-bridge.ps1`
- Modify: `C:\Users\Jester\.openclaw\start-telegram-bridge.cmd`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path


def test_entry_script_exists():
    assert Path(r"C:\Users\Jester\Desktop\Sonya\scripts\run-openclaw-bridge.ps1").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests -k entry_script_exists -v`
Expected: FAIL because script does not yet exist

- [ ] **Step 3: Write minimal implementation**

`run-openclaw-bridge.ps1` must:
- set package root
- activate or bootstrap local venv if the chosen execution model requires it
- run package entrypoint against `.openclaw`

`start-telegram-bridge.cmd` must be changed from:
- direct `node telegram-bridge.mjs`

to:
- launch Sonya-repo bridge entrypoint

while preserving:
- network wait behavior
- restart-loop behavior
- launcher logging

- [ ] **Step 4: Run verification**

Run:
- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Jester\Desktop\Sonya\scripts\run-openclaw-bridge.ps1`

Expected:
- process starts without immediate crash
- OpenClaw host paths are used

- [ ] **Step 5: Commit**

```bash
git add scripts/run-openclaw-bridge.ps1
git commit -m "feat: switch openclaw bridge entrypoint to sonya repo"
```

## Task 10: Parity Verification Against Current OpenClaw Behavior

**Files:**
- Reuse test files above
- Modify tests as needed to lock parity behaviors

- [ ] **Step 1: Capture final parity assertions**

Verify all of the following explicitly:
- formatting output matches prior bridge expectations
- media classification behavior matches prior bridge expectations
- session truncation matches prior bridge expectations
- `/start` handling matches prior bridge expectations
- allowlist handling matches prior bridge expectations
- raw update log append format is preserved
- post-response hook invocation contract is preserved

- [ ] **Step 2: Run full package test suite**

Run:
```bash
pytest C:\Users\Jester\Desktop\Sonya\packages\tg-bridge\tests -v
```

Expected: PASS

- [ ] **Step 3: Run live OpenClaw health check**

Run:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Jester\.openclaw\health-check.ps1
```

Expected:
- `Overall result: OK`

- [ ] **Step 4: Manually smoke test Telegram**

Manual steps:
1. Send `/start` to the bot
2. Send plain text
3. Send photo with caption
4. Send sticker
5. Send `/img ...`

Expected:
- text reply path works
- image reply path works
- no fresh `poll failed` loop in bridge log

- [ ] **Step 5: Commit**

```bash
git add packages/tg-bridge
git commit -m "test: verify telegram bridge extraction parity"
```

## Self-Review

### Spec coverage

- repository bootstrap: covered by Task 1
- formatting extraction: covered by Task 2
- media extraction: covered by Task 3
- persistence extraction: covered by Task 4
- OpenClaw adapter and bootstrap: covered by Task 5
- prompt/model path: covered by Task 6
- handlers and Telegram API path: covered by Task 7
- app and update loop: covered by Task 8
- entrypoint migration: covered by Task 9
- parity and live validation: covered by Task 10

### Placeholder scan

- no `TODO`
- no `TBD`
- no "implement later"
- no vague "add error handling" placeholders

### Type consistency

- helper names are consistent across modules
- OpenClaw remains host environment through all tasks
- extraction path remains parity-first through all tasks

## Execution Handoff

Plan complete and saved to `C:\Users\Jester\Desktop\Sonya\docs\work\implementation-plans\2026-05-01-telegram-bridge-extraction-implementation-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - task-by-task implementation with review between tasks

**2. Inline Execution** - implement in this session sequentially with checkpoints
