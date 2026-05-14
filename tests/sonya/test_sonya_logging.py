from __future__ import annotations

import io
import json
import logging

import pytest

from sonya.logging import JsonFormatter, get_logger, setup_logging


def _capture_logger_output(level: str = "INFO") -> tuple[logging.Logger, io.StringIO]:
    setup_logging(level)
    sonya_root = logging.getLogger("sonya")
    for h in list(sonya_root.handlers):
        sonya_root.removeHandler(h)
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    sonya_root.addHandler(handler)
    return sonya_root, buffer


def _parse_lines(buffer: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def _reset_sonya_logger() -> None:
    yield
    sonya_root = logging.getLogger("sonya")
    for h in list(sonya_root.handlers):
        sonya_root.removeHandler(h)
    sonya_root.setLevel(logging.NOTSET)


def test_logger_emits_structured_json() -> None:
    _, buffer = _capture_logger_output("INFO")
    log = get_logger("sonya.testA")
    log.info("hello", extra={"event": "boot", "subject_id": "s1"})

    lines = _parse_lines(buffer)
    assert lines
    last = lines[-1]
    assert last["msg"] == "hello"
    assert last["level"] == "INFO"
    assert last["component"] == "sonya.testA"
    assert last["event"] == "boot"
    assert last["subject_id"] == "s1"


def test_logger_respects_level() -> None:
    _, buffer = _capture_logger_output("WARNING")
    log = get_logger("sonya.testB")
    log.debug("hidden")
    log.warning("visible")

    lines = _parse_lines(buffer)
    levels = [entry["level"] for entry in lines]
    assert "WARNING" in levels
    assert "DEBUG" not in levels


def test_json_formatter_produces_valid_json() -> None:
    record = logging.LogRecord(
        name="sonya.x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=(),
        exc_info=None,
    )
    record.event = "test_event"  # type: ignore[attr-defined]
    formatted = JsonFormatter().format(record)
    parsed = json.loads(formatted)
    assert parsed["msg"] == "message"
    assert parsed["level"] == "INFO"
    assert parsed["component"] == "sonya.x"
    assert parsed["event"] == "test_event"


def test_get_logger_namespaces_under_sonya() -> None:
    log = get_logger("foo")
    assert log.name == "sonya.foo"
    log2 = get_logger("sonya.bar")
    assert log2.name == "sonya.bar"
