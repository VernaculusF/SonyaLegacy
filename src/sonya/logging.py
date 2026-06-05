from __future__ import annotations

import json
import logging
import sys
from typing import Any


_RESERVED_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class SafeExtraLogger(logging.Logger):
    """Logger that prevents `extra` collisions with LogRecord internals.

    Python raises KeyError before our formatter runs if a caller passes
    extra={"module": ...} or any other reserved LogRecord attribute. Runtime
    plugins/selfmods can still do that accidentally, so sanitize at logger
    entry instead of trusting every call site.
    """

    def makeRecord(  # noqa: N802 - logging API
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: object,
        args: object,
        exc_info: object,
        func: str | None = None,
        extra: dict[str, Any] | None = None,
        sinfo: str | None = None,
    ) -> logging.LogRecord:
        if isinstance(extra, dict):
            clean: dict[str, Any] = {}
            for key, value in extra.items():
                if key in _RESERVED_LOG_RECORD_ATTRS or key.startswith("_"):
                    clean[f"extra_{key.lstrip('_')}"] = value
                else:
                    clean[key] = value
            extra = clean
        return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)


if not issubclass(logging.getLoggerClass(), SafeExtraLogger):
    logging.setLoggerClass(SafeExtraLogger)


class JsonFormatter(logging.Formatter):
    """Render LogRecord as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "component": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure root sonya logger with a single JSON handler."""
    root = logging.getLogger("sonya")
    if not isinstance(root, SafeExtraLogger):
        root.__class__ = SafeExtraLogger
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.propagate = False


def get_logger(component: str) -> logging.Logger:
    """Return a namespaced logger under sonya.*."""
    if not component.startswith("sonya"):
        component = f"sonya.{component}"
    logger = logging.getLogger(component)
    if not isinstance(logger, SafeExtraLogger):
        logger.__class__ = SafeExtraLogger
    return logger
