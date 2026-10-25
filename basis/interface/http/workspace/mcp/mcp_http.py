"""Per-workspace MCP over HTTP (JSON-RPC)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from basis.interface.http.shared.deps import get_store, resolve_bearer
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.mcp.protocol import handle_batch
from basis.application.tool_catalog import TOOL_NAMES
from basis.application.tool_catalog.mcp_access import mcp_tool_access
from basis.interface.mcp.dispatch import get_tool_definitions
from basis.interface.http.shared.http_operation_catalog import workspace_http_operation_entries
from basis.interface.mcp.resources import list_resources
from basis.interface.mcp.tools import CAPABILITIES, PROTOCOL_VERSION

router = APIRouter(tags=["mcp"])


@router.get("/{workspace_id}/mcp")
async def mcp_integration_info(
    workspace_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """
Mcp Integration Info. MCP JSON-RPC transport for agent integrations. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    user, _auth_kind = resolve_bearer(request, authorization)
    store = get_store(request)
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    tool_definitions = get_tool_definitions(ctx)
    tool_names = [t["name"] for t in tool_definitions]
    tool_entries = [
        {
            "name": name,
            "description": str(t.get("description") or name or "").strip(),
            "access": mcp_tool_access(name),
        }
        for t in tool_definitions
        if (name := str(t.get("name") or "").strip())
    ]
    base = str(request.base_url).rstrip("/")
    mcp_url = f"{base}/api/v1/workspaces/{workspace_id}/mcp"
    http_operation_entries = workspace_http_operation_entries(request.app)
    return {
        "workspace_id": workspace_id,
        "workspace_name": ctx.workspace.name,
        "mcp_url": mcp_url,
        "transport": "http",
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": CAPABILITIES,
        "auth": {"type": "bearer", "header": "Authorization", "prefix": "Bearer "},
        "tools": tool_names,
        "resources": [r["uri"] for r in list_resources()],
        "resource_entries": list_resources(),
        "tool_entries": tool_entries,
        "http_operation_entries": http_operation_entries,
        "static_tools": list(TOOL_NAMES),
        "cursor_example": {
            "mcpServers": {
                "basis-workspace": {
                    "url": mcp_url,
                    "headers": {"Authorization": "Bearer <your-api-token>"},
                }
            }
        },
    }


@router.post("/{workspace_id}/mcp")
async def mcp_jsonrpc(
    workspace_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> Any:
    """
MCP JSON-RPC over HTTP; tools match integration core operations (search, graph read, remember).
    """
    user, _auth_kind = resolve_bearer(request, authorization)
    store = get_store(request)
    body = await request.json()
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    semaphore: asyncio.Semaphore = request.app.state.mcp_semaphore
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=1.0)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "mcp_busy", "message": "MCP 请求过多，请稍后重试"},
        ) from exc
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(handle_batch, ctx, body),
            timeout=request.app.state.settings.mcp_timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail={"code": "mcp_timeout", "message": "MCP 工具执行超时"},
        ) from exc
    finally:
        semaphore.release()
