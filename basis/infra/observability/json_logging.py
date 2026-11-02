"""Optional JSON log lines for the `basis` logger tree (X-02)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from basis.infra.observability.redaction import redact_log_field, redact_string

_LOG_RECORD_SKIP = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "message",
        "taskName",
    }
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_string(record.getMessage()),
        }
        rid = getattr(record, "request_id", None)
        if isinstance(rid, str) and rid.strip():
            payload["request_id"] = rid.strip()
        for key, raw in record.__dict__.items():
            if key in _LOG_RECORD_SKIP or key.startswith("_"):
                continue
            if key == "request_id":
                continue
            payload[key] = redact_log_field(key, raw)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def install_json_logging() -> None:
    log = logging.getLogger("basis")
    if any(isinstance(h.formatter, JsonLogFormatter) for h in log.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    log.addHandler(handler)
    if log.level == logging.NOTSET:
        log.setLevel(logging.INFO)
    log.propagate = False
