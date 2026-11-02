"""Dispatch static tools and expose MCP tools/list metadata (description + inputSchema)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from basis.services.kernel import WorkspaceCoreContext
from basis.services.tenancy.admin.api_token_grants import token_allows_mcp_operation
from basis.mcp.catalog import OPERATIONS, mcp_exposed
from basis.mcp.mcp_metadata import MCP_TOOL_METADATA
from basis.mcp.validation import (
    OPERATION_INPUT_MODELS,
    coerce_operation_args,
    validation_error_payload,
    validate_operation_response,
)

__all__ = [
    "TOOL_NAMES",
    "description_for_tool",
    "input_schema_for_tool",
    "run",
]


def _assert_catalog_aligned() -> None:
    catalog = set(OPERATIONS)
    meta = set(MCP_TOOL_METADATA)
    models = set(OPERATION_INPUT_MODELS)
    if catalog != meta:
        missing = catalog - meta
        extra = meta - catalog
        raise RuntimeError(
            "MCP_TOOL_METADATA keys must match OPERATIONS: "
            f"missing={sorted(missing)!r} extra={sorted(extra)!r}"
        )
    if catalog != models:
        missing = catalog - models
        extra = models - catalog
        raise RuntimeError(
            "OPERATION_INPUT_MODELS keys must match OPERATIONS: "
            f"missing={sorted(missing)!r} extra={sorted(extra)!r}"
        )


_assert_catalog_aligned()

TOOL_NAMES: tuple[str, ...] = tuple(name for name in OPERATIONS if mcp_exposed(name))


def description_for_tool(tool_name: str) -> str:
    meta = MCP_TOOL_METADATA.get(tool_name)
    if not meta:
        return tool_name
    text = meta.get("description")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return tool_name


def input_schema_for_tool(tool_name: str) -> dict[str, Any]:
    model = OPERATION_INPUT_MODELS[tool_name]
    return model.model_json_schema(mode="serialization")


def run(ctx: WorkspaceCoreContext, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Run a registered static operation; returns a plain JSON-serializable dict."""
    if ctx.api_token is not None and not token_allows_mcp_operation(ctx.api_token, name):
        return {
            "error": "forbidden",
            "code": "forbidden",
            "message": f"令牌未授权操作：{name}",
        }
    spec = OPERATIONS.get(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    handler = spec["handler"]
    try:
        args = coerce_operation_args(name, arguments)
    except ValidationError as exc:
        return validation_error_payload(exc)
    result = handler(ctx, args)
    if isinstance(result, dict) and "error" not in result:
        return validate_operation_response(name, result)
    return result
