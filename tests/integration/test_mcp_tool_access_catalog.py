"""MCP read/write classification covers the static tool catalog."""

from __future__ import annotations

from basis.application.tool_catalog.catalog import OPERATIONS
from basis.application.tool_catalog.mcp_access import MCP_TOOL_ACCESS, mcp_tool_access


def test_every_static_operation_has_mcp_access_entry() -> None:
    missing = sorted(set(OPERATIONS) - set(MCP_TOOL_ACCESS))
    assert missing == []


def test_ontology_and_mapping_access_classes() -> None:
    assert mcp_tool_access("list_ontology_registry") == "read"
    assert mcp_tool_access("get_ontology_proposal") == "read"
    assert mcp_tool_access("propose_mapping") == "write"
    assert mcp_tool_access("publish_ontology_proposal") == "write"
    assert mcp_tool_access("update_mapping_status") == "write"
