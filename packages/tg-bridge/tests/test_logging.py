from pathlib import Path

from tg_bridge.logging import append_log_line, format_error


def test_format_error_includes_cause_when_present():
    err = RuntimeError("outer")
    err.__cause__ = ValueError("inner")
    text = format_error(err)
    assert "RuntimeError" in text
    assert "outer" in text
    assert "cause=inner" in text


def test_append_log_line_writes_timestamped_line(tmp_path: Path):
    log_path = tmp_path / "bridge.log"
    append_log_line(log_path, "bridge starting")
    content = log_path.read_text(encoding="utf-8")
    assert "bridge starting" in content

