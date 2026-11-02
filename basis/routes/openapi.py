"""Serve OpenAPI v1 from the running FastAPI app (`app.openapi()` + Basis export)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from basis.http.openapi.v1_export import (
    cached_openapi_v1_full,
    cached_openapi_v1_workspaces,
    cached_openapi_v1_platform,
)

router = APIRouter(tags=["openapi"])


@router.get("/openapi/v1.json")
async def get_openapi_v1_full(request: Request) -> JSONResponse:
    """Return the live Basis OpenAPI v1 document exported from this app."""
    return JSONResponse(cached_openapi_v1_full(request.app))


@router.get("/openapi/v1/platform.json")
async def get_openapi_v1_platform(request: Request) -> JSONResponse:
    """Return the live platform/admin OpenAPI slice exported from this app."""
    return JSONResponse(cached_openapi_v1_platform(request.app))


@router.get("/openapi/v1/workspaces.json")
async def get_openapi_v1_workspaces(request: Request) -> JSONResponse:
    """Return the live workspace integration OpenAPI slice exported from this app."""
    return JSONResponse(cached_openapi_v1_workspaces(request.app))
