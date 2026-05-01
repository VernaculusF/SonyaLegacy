from pathlib import Path

from telegram_userbot.app import create_openclaw_app


def test_create_openclaw_app_uses_openclaw_host():
    app = create_openclaw_app(Path(r"C:\Users\Jester\.openclaw"))
    assert app.host.config_path.name == "openclaw.json"
