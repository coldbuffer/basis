"""MCP JSON-RPC server, tool catalog, and dynamic connector tool bindings."""

from basis.mcp.catalog import OPERATIONS, OperationHandler, OperationSpec, mcp_exposed
from basis.mcp.mcp_metadata import MCP_TOOL_METADATA
from basis.mcp.run import (
    TOOL_NAMES,
    description_for_tool,
    input_schema_for_tool,
    run,
)
from basis.mcp.validation import (
    OPERATION_INPUT_MODELS,
    OPERATION_RESPONSE_MODELS,
    coerce_operation_args,
    validate_operation_response,
    validation_error_payload,
)

__all__ = [
    "MCP_TOOL_METADATA",
    "OPERATIONS",
    "OPERATION_INPUT_MODELS",
    "OPERATION_RESPONSE_MODELS",
    "OperationHandler",
    "OperationSpec",
    "TOOL_NAMES",
    "coerce_operation_args",
    "description_for_tool",
    "input_schema_for_tool",
    "mcp_exposed",
    "run",
    "validate_operation_response",
    "validation_error_payload",
]
