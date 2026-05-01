from pathlib import Path

from telegram_userbot.adapters.openclaw import OpenClawHost


def test_openclaw_host_resolves_expected_paths():
    host = OpenClawHost(Path(r"C:\Users\Jester\.openclaw"))
    assert host.config_path.name == "openclaw.json"
    assert host.workspace_root.name == "workspace"
    assert host.bridge_log_path.name == "telegram-bridge.log"
