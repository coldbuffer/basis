"""Static tool name → handler registry.

New MCP tools: BC ``operations.op_*``, entry here, ``mcp_metadata`` description, and
``schemas.TOOL_INPUT_MODELS`` (see AGENTS.md). HTTP routes are registered separately.
"""

from __future__ import annotations

from typing import Any, Callable, NotRequired, TypedDict

from basis.application.connectors import operations as connector_ops
from basis.application.graph import operations as graph_ops
from basis.application.knowledge import operations as knowledge_ops
from basis.application.reasoning import operations as reasoning_ops
from basis.application.review import operations as review_ops
from basis.application.kernel import WorkspaceCoreContext
from basis.application.workspace import operations as workspace_ops
from basis.application.semantica_compat import operations as semantica_ops

OperationHandler = Callable[[WorkspaceCoreContext, dict[str, Any]], dict[str, Any]]


class OperationSpec(TypedDict):
    handler: OperationHandler
    mcp: NotRequired[bool]


OPERATIONS: dict[str, OperationSpec] = {
    "list_processing_jobs": {"handler": workspace_ops.op_list_processing_jobs},
    "search_chunks": {"handler": knowledge_ops.op_search_chunks},
    "get_chunk": {"handler": knowledge_ops.op_get_chunk},
    "entity_facts": {"handler": knowledge_ops.op_entity_facts},
    "list_derived_facts": {"handler": knowledge_ops.op_list_derived_facts},
    "list_typed_facts": {"handler": knowledge_ops.op_list_typed_facts},
    "list_mappings": {"handler": knowledge_ops.op_list_mappings},
    "get_statement": {"handler": knowledge_ops.op_get_statement},
    "propose_remember": {"handler": knowledge_ops.op_propose_remember},
    "paths": {"handler": graph_ops.op_paths},
    "extract_entities": {"handler": semantica_ops.op_extract_entities},
    "extract_relations": {"handler": semantica_ops.op_extract_relations},
    "record_decision": {"handler": semantica_ops.op_record_decision},
    "query_decisions": {"handler": semantica_ops.op_query_decisions},
    "find_precedents": {"handler": semantica_ops.op_find_precedents},
    "get_causal_chain": {"handler": semantica_ops.op_get_causal_chain},
    "add_entity": {"handler": semantica_ops.op_add_entity},
    "add_relationship": {"handler": semantica_ops.op_add_relationship},
    "get_graph_analytics": {"handler": semantica_ops.op_get_graph_analytics},
    "export_graph": {"handler": semantica_ops.op_export_graph},
    "get_graph_summary": {"handler": semantica_ops.op_get_graph_summary},
    "query_graph": {"handler": semantica_ops.op_query_graph},
    "update_node": {"handler": semantica_ops.op_update_node},
    "delete_node": {"handler": semantica_ops.op_delete_node},
    "list_rules": {"handler": reasoning_ops.op_list_rules},
    "get_rule": {"handler": reasoning_ops.op_get_rule},
    "run_reasoning": {"handler": reasoning_ops.op_run_reasoning},
    "list_review_items": {"handler": review_ops.op_list_review_items},
    "get_review_item": {"handler": review_ops.op_get_review_item},
    "approve_review_item": {"handler": review_ops.op_approve_review_item},
    "reject_review_item": {"handler": review_ops.op_reject_review_item},
    "list_connector_catalog": {"handler": connector_ops.op_list_connector_catalog},
    "describe_connector_service": {"handler": connector_ops.op_describe_connector_service},
    "list_connector_connections": {"handler": connector_ops.op_list_connector_connections},
    "upsert_connector_connection": {"handler": connector_ops.op_upsert_connector_connection},
    "delete_connector_connection": {"handler": connector_ops.op_delete_connector_connection},
    "check_connector_connection": {"handler": connector_ops.op_check_connector_connection},
    "discover_connector_schema": {"handler": connector_ops.op_discover_connector_schema},
    "list_connector_table_mappings": {"handler": connector_ops.op_list_connector_table_mappings},
    "sync_connector_table_mapping": {"handler": connector_ops.op_sync_connector_table_mapping},
    "invoke_connector_primitive": {"handler": connector_ops.op_invoke_connector_primitive},
    "execute_connector_tool": {"handler": connector_ops.op_execute_connector_tool},
    "propose_entity_writeback": {"handler": connector_ops.op_propose_entity_writeback},
}


def mcp_exposed(tool_name: str) -> bool:
    """Whether the tool appears on MCP tools/list (default true)."""
    return OPERATIONS[tool_name].get("mcp", True)
