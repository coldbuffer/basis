"""Concurrency limit for /api/v1/* (R5 — mirrors MCP semaphore)."""

from __future__ import annotations

import asyncio

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from basis.http.http_path import original_http_path


class RestV1ConcurrencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = original_http_path(request.scope)
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        semaphore: asyncio.Semaphore = request.app.state.rest_v1_semaphore
        acquired = False
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=1.0)
            acquired = True
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": {
                        "code": "api_busy",
                        "message": "REST v1 请求过多，请稍后重试",
                    }
                },
            )
        try:
            return await call_next(request)
        finally:
            if acquired:
                semaphore.release()
