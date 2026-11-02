"""Parse/build dynamic connector MCP tool names (shared by catalog + MCP dispatch)."""

from __future__ import annotations

import re
from typing import Literal

CONNECTOR_TOOL_PREFIX = "connector_"
_SEGMENT_RE = re.compile(r"[^a-z0-9_]+")

MutateOpLiteral = Literal["create", "update", "upsert", "delete"]
_MUTATE_OPS: tuple[MutateOpLiteral, ...] = ("create", "update", "upsert", "delete")


def _sanitize_segment(value: str) -> str:
    cleaned = _SEGMENT_RE.sub("_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "action"


def connector_mcp_tool_name(
    service: str,
    action_id: str,
    primitive: str,
    *,
    operation: str | None = None,
) -> str:
    """Stable MCP tool name: ``connector_{service}__{action_id}__{suffix}``."""
    suffix = primitive
    if primitive == "mutate" and operation:
        suffix = f"mutate_{_sanitize_segment(operation)}"
    return (
        f"{CONNECTOR_TOOL_PREFIX}{_sanitize_segment(service)}"
        f"__{_sanitize_segment(action_id)}__{_sanitize_segment(suffix)}"
    )


def parse_connector_mcp_tool_name(name: str) -> dict[str, str] | None:
    """Decode a dynamic connector tool name into invoke_connector_primitive args."""
    if not name.startswith(CONNECTOR_TOOL_PREFIX):
        return None
    body = name[len(CONNECTOR_TOOL_PREFIX) :]
    parts = body.split("__")
    if len(parts) != 3:
        return None
    service, action_id, suffix = parts
    if not service or not action_id or not suffix:
        return None
    if suffix.startswith("mutate_"):
        operation = suffix[len("mutate_") :]
        if operation not in _MUTATE_OPS:
            return None
        return {
            "service": service,
            "action_id": action_id,
            "primitive": "mutate",
            "operation": operation,
        }
    if suffix in ("discover", "list", "invoke"):
        return {"service": service, "action_id": action_id, "primitive": suffix}
    return None
