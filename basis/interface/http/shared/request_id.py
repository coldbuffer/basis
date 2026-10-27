"""HTTP middleware for X-Request-ID (X-02)."""

from __future__ import annotations

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from basis.infra.runtime.observability.request_context import (
    current_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)

REQUEST_ID_HEADER = "X-Request-ID"

__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIdLogFilter",
    "RequestIdMiddleware",
    "attach_request_id_to_detail",
    "current_request_id",
    "get_request_id",
    "install_request_id_logging",
    "new_request_id",
]


def get_request_id(request: Request) -> str | None:
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return None


def attach_request_id_to_detail(request: Request, detail: dict[str, object]) -> dict[str, object]:
    rid = get_request_id(request)
    if rid:
        return {**detail, "request_id": rid}
    return detail


class RequestIdLogFilter(logging.Filter):
    """Adds request_id to log records when inside a request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = current_request_id()
        if rid:
            record.request_id = rid  # type: ignore[attr-defined]
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming and incoming.strip() else new_request_id()
        request.state.request_id = request_id
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def install_request_id_logging() -> None:
    filt = RequestIdLogFilter()
    root = logging.getLogger("basis")
    if not any(isinstance(f, RequestIdLogFilter) for f in root.filters):
        root.addFilter(filt)
