"""MCP tools/list and tools/call dispatch (wraps :mod:`basis.mcp`)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from basis.services.kernel import CoreError, WorkspaceCoreContext
from basis.mcp import (
    OPERATIONS,
    TOOL_NAMES,
)
from basis.mcp.catalog import mcp_exposed
from basis.mcp import run as run_static_operation
from basis.services.errors import AdminError
from basis.mcp.format import mcp_text_result
from basis.mcp.run import description_for_tool, input_schema_for_tool
from basis.services.tenancy.admin.api_token_grants import token_allows_mcp_operation

__all__ = [
    "TOOL_DEFINITIONS",
    "TOOL_NAMES",
    "execute",
    "get_static_tool_definitions",
    "get_tool_definitions",
    "run",
]


@lru_cache(maxsize=1)
def get_static_tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "description": description_for_tool(name),
            "inputSchema": input_schema_for_tool(name),
        }
        for name in OPERATIONS
        if mcp_exposed(name)
    ]


def get_tool_definitions(ctx: WorkspaceCoreContext | None = None) -> list[dict[str, Any]]:
    """MCP tools/list payload."""
    tools = list(get_static_tool_definitions())
    record = ctx.api_token if ctx is not None else None
    if record is not None and record.mcp_allowed_operations is not None:
        tools = [t for t in tools if token_allows_mcp_operation(record, str(t.get("name", "")))]
    return tools


def __getattr__(name: str) -> Any:
    if name == "TOOL_DEFINITIONS":
        return get_tool_definitions()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _is_known_mcp_tool(name: str) -> bool:
    return name in OPERATIONS


def run(ctx: WorkspaceCoreContext, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Run a static MCP tool; plain JSON dict."""
    if ctx.api_token is not None and not token_allows_mcp_operation(ctx.api_token, name):
        return {
            "error": "forbidden",
            "code": "forbidden",
            "message": f"令牌未授权操作：{name}",
        }
    return run_static_operation(ctx, name, arguments)


def execute(ctx: WorkspaceCoreContext, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """MCP tools/call envelope."""
    if not _is_known_mcp_tool(name):
        return mcp_text_result({"error": f"unknown tool: {name}"}, is_error=True)
    try:
        payload = run(ctx, name, arguments)
    except CoreError as exc:
        return mcp_text_result(exc.detail, is_error=True)
    except AdminError as exc:
        return mcp_text_result({"code": exc.code, "message": exc.message}, is_error=True)
    return mcp_text_result(payload)
