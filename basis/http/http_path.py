"""HTTP path helpers for middleware."""

from __future__ import annotations

from starlette.types import Scope


def original_http_path(scope: Scope) -> str:
    if scope.get("type") not in ("http", "websocket"):
        return ""
    return scope.get("path") or ""
