from pathlib import Path


def test_entry_script_exists():
    assert Path(r"C:\Users\Jester\Desktop\Sonya\scripts\run-openclaw-bridge.ps1").exists()
