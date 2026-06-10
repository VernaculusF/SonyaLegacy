from pathlib import Path


def test_backup_script_uses_python_sqlite_backup_when_cli_is_missing() -> None:
    script = (Path(__file__).parents[2] / "deploy" / "backup.sh").read_text(encoding="utf-8")

    assert 'cp -p "$SUBSTRATE" "$DAILY"' not in script
    assert "src.backup(dst)" in script
    assert 'python3 - "$SUBSTRATE" "$DAILY"' in script
