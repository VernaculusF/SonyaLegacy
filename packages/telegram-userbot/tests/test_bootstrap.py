from pathlib import Path

from telegram_userbot.adapters.openclaw import OpenClawHost
from telegram_userbot.bootstrap import load_bootstrap_context


def test_bootstrap_loads_anchor_files_and_context(tmp_path: Path):
    root = tmp_path / ".openclaw"
    workspace = root / "workspace"
    memory = workspace / "memory_system"
    memory.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("agents", encoding="utf-8")
    (workspace / "SOUL.md").write_text("soul", encoding="utf-8")
    (workspace / "HEARTBEAT.md").write_text("heartbeat", encoding="utf-8")
    (workspace / "IDENTITY.md").write_text("identity", encoding="utf-8")
    (memory / "context_loader.py").write_text("# stub", encoding="utf-8")
    (memory / "post_response_hook.py").write_text("# stub", encoding="utf-8")
    (root / "openclaw.json").write_text("{}", encoding="utf-8")

    host = OpenClawHost(root)

    def fake_runner(script_path: Path, args: list[str]):
        assert script_path.name == "context_loader.py"
        assert args == ["full", "7"]
        return {"stdout": "memory-context", "stderr": "", "status": 0, "error": None}

    bootstrap = load_bootstrap_context(host, fake_runner)
    assert bootstrap["agents"] == "agents"
    assert bootstrap["soul"] == "soul"
    assert bootstrap["heartbeat"] == "heartbeat"
    assert bootstrap["identity"] == "identity"
    assert bootstrap["memoryContext"] == "memory-context"
