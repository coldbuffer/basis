"""Optional block of unversioned /api/* (R6 — enable via BASIS_LEGACY_API_ENABLED=0)."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from basis.http.http_path import original_http_path

_LEGACY_ALLOWED_PREFIXES = (
    "/api/v1/",
    "/openapi/",
    "/health",
)


class LegacyApiGateMiddleware:
    def __init__(self, app: ASGIApp, *, legacy_enabled: bool) -> None:
        self.app = app
        self.legacy_enabled = legacy_enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or self.legacy_enabled:
            await self.app(scope, receive, send)
            return

        path = original_http_path(scope)
        if path.startswith("/api/") and not any(
            path.startswith(prefix) for prefix in _LEGACY_ALLOWED_PREFIXES
        ):
            if scope["type"] == "websocket":
                from starlette.websockets import WebSocket

                ws = WebSocket(scope, receive, send)
                await ws.close(code=1008, reason="legacy_api_removed")
                return
            response = JSONResponse(
                status_code=410,
                content={
                    "detail": {
                        "code": "legacy_api_removed",
                        "message": "Unversioned /api/* is disabled; use /api/v1/*",
                        "link": "/openapi/v1.json",
                    }
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
