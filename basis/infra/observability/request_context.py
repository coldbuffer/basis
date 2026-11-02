"""Request-scoped correlation IDs (usable outside the HTTP layer)."""

from __future__ import annotations

import contextvars
import logging
import uuid

_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


def new_request_id() -> str:
    return uuid.uuid4().hex


def current_request_id() -> str | None:
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> contextvars.Token[str | None]:
    return _request_id_ctx.set(request_id.strip())


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    _request_id_ctx.reset(token)


class RequestIdLogFilter(logging.Filter):
    """Adds request_id to log records when inside a request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = current_request_id()
        if rid:
            record.request_id = rid  # type: ignore[attr-defined]
        return True


def install_request_id_logging() -> None:
    filt = RequestIdLogFilter()
    root = logging.getLogger("basis")
    if not any(isinstance(f, RequestIdLogFilter) for f in root.filters):
        root.addFilter(filt)
