"""Minimal MCP JSON-RPC over HTTP (initialize, tools, resources, ping)."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.interface.mcp.dispatch import execute, get_tool_definitions
from basis.interface.mcp.resources import list_resources, read_resource
from basis.interface.mcp.tools import CAPABILITIES, PROTOCOL_VERSION, SERVER_INFO

WorkspaceToolContext = WorkspaceCoreContext
call_tool = execute


def handle_jsonrpc(ctx: WorkspaceToolContext, req: dict[str, Any]) -> dict[str, Any] | None:
    method = req.get("method", "")
    params = req.get("params") or {}
    req_id = req.get("id")

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    if req_id is None and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return ok(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": CAPABILITIES,
                "serverInfo": SERVER_INFO,
            }
        )

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return ok({})

    if method == "tools/list":
        return ok({"tools": get_tool_definitions(ctx)})

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            return ok(call_tool(ctx, name, arguments))
        except Exception as exc:
            return err(-32603, str(exc))

    if method == "resources/list":
        return ok({"resources": list_resources()})

    if method == "resources/read":
        uri = str(params.get("uri") or "")
        if not uri:
            return err(-32602, "uri is required")
        try:
            return ok(read_resource(ctx, uri))
        except Exception as exc:
            return err(-32603, str(exc))

    if method == "prompts/list":
        return ok({"prompts": []})

    if req_id is None:
        return None

    return err(-32601, f"Method not found: {method}")


def handle_batch(ctx: WorkspaceToolContext, body: Any) -> Any:
    if isinstance(body, list):
        out: list[dict[str, Any]] = []
        for item in body:
            if not isinstance(item, dict):
                continue
            resp = handle_jsonrpc(ctx, item)
            if resp is not None:
                out.append(resp)
        return out
    if isinstance(body, dict):
        resp = handle_jsonrpc(ctx, body)
        if resp is None:
            return {}
        return resp
    return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON-RPC"}}
