"""Mark unversioned /api/* responses as deprecated (R2)."""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from basis.http.http_path import original_http_path


class LegacyApiDeprecationMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = original_http_path(scope)
        mark_deprecated = path.startswith("/api/") and not path.startswith("/api/v1/")

        async def send_wrapper(message: dict) -> None:
            if mark_deprecated and message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"deprecation", b"true"))
                headers.append((b"link", b'</openapi/v1.json>; rel="describedby"'))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
