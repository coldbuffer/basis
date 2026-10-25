"""MCP adapter — re-exports core operations and protocol metadata."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext, WorkspaceToolContext
from basis.application.tool_catalog import TOOL_NAMES
from basis.interface.mcp.dispatch import execute as call_tool, get_tool_definitions

SERVER_INFO = {"name": "basis-workspace-mcp", "version": "0.1.0"}
CAPABILITIES = {
    "tools": {"listChanged": False},
    "resources": {"listChanged": False, "subscribe": False},
}
PROTOCOL_VERSION = "2024-11-05"

__all__ = [
    "CAPABILITIES",
    "WorkspaceCoreContext",
    "WorkspaceToolContext",
    "PROTOCOL_VERSION",
    "SERVER_INFO",
    "TOOL_DEFINITIONS",
    "TOOL_NAMES",
    "call_tool",
    "get_tool_definitions",
]


def __getattr__(name: str) -> Any:
    if name == "TOOL_DEFINITIONS":
        return get_tool_definitions()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
