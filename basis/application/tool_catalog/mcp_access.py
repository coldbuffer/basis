"""Classify static MCP tools as read vs write for API token grants UI."""

from __future__ import annotations

from basis.application.tool_catalog.connector_mcp_tool_name import parse_connector_mcp_tool_name

# Write = requires workspace editor (mutations, approvals, connector vault writes, sync).
MCP_TOOL_ACCESS: dict[str, str] = {
    "list_processing_jobs": "read",
    "reset_workspace": "write",
    "search_chunks": "read",
    "get_chunk": "read",
    "entity_facts": "read",
    "list_derived_facts": "read",
    "list_typed_facts": "read",
    "list_mappings": "read",
    "list_surface_phrases": "read",
    "list_entity_type_object_labels": "read",
    "assign_entity_types": "write",
    "clear_entity_types": "write",
    "invalidate_entities": "write",
    "delete_document": "write",
    "delete_entity": "write",
    "propose_mapping": "write",
    "update_mapping_status": "write",
    "list_ontology_registry": "read",
    "get_ontology_graph": "read",
    "search_ontology_entities": "read",
    "suggest_alignment_target_uri": "read",
    "list_vocabulary_alignments": "read",
    "upsert_vocabulary_alignment": "write",
    "delete_vocabulary_alignment": "write",
    "suggest_vocabulary_alignments": "read",
    "list_ontology_proposals": "read",
    "save_ontology_draft": "write",
    "list_ontology_drafts": "read",
    "get_ontology_draft": "read",
    "submit_ontology_proposal": "write",
    "get_ontology_proposal": "read",
    "approve_ontology_proposal": "write",
    "reject_ontology_proposal": "write",
    "publish_ontology_proposal": "write",
    "comment_ontology_proposal": "write",
    "list_ontology_versions": "read",
    "compare_ontology_versions": "read",
    "restore_ontology_version_draft": "write",
    "toggle_ontology": "write",
    "get_statement": "read",
    "paths": "read",
    "extract_entities": "read",
    "extract_relations": "read",
    "query_decisions": "read",
    "find_precedents": "read",
    "get_causal_chain": "read",
    "get_graph_analytics": "read",
    "export_graph": "read",
    "get_graph_summary": "read",
    "query_graph": "read",
    "record_decision": "write",
    "add_entity": "write",
    "add_relationship": "write",
    "update_node": "write",
    "delete_node": "write",
    "list_rules": "read",
    "get_rule": "read",
    "list_review_items": "read",
    "get_review_item": "read",
    "list_connector_catalog": "read",
    "describe_connector_service": "read",
    "list_connector_connections": "read",
    "check_connector_connection": "read",
    "discover_connector_schema": "read",
    "list_connector_table_mappings": "read",
    "propose_remember": "write",
    "run_reasoning": "write",
    "approve_review_item": "write",
    "reject_review_item": "write",
    "upsert_connector_connection": "write",
    "delete_connector_connection": "write",
    "sync_connector_table_mapping": "write",
    "invoke_connector_primitive": "write",
    "execute_connector_tool": "write",
    "propose_entity_writeback": "write",
}


def mcp_tool_access(tool_name: str) -> str:
    """Return ``read`` or ``write`` for MCP / HTTP grant classification."""
    if tool_name in MCP_TOOL_ACCESS:
        return MCP_TOOL_ACCESS[tool_name]
    binding = parse_connector_mcp_tool_name(tool_name)
    if binding is not None:
        primitive = binding.get("primitive", "")
        if primitive in {"discover", "list"}:
            return "read"
        return "write"
    return "write"
