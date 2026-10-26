"""MCP input schemas for ledger mapping and ontology hub tools."""

from __future__ import annotations

import pytest

from basis.application.tool_catalog.run import input_schema_for_tool

LEDGER_MAPPING_TOOLS: dict[str, set[str]] = {
    "list_mappings": set(),
    "list_surface_phrases": set(),
    "list_entity_type_object_labels": set(),
    "assign_entity_types": {"assignments"},
    "clear_entity_types": {"subject_ids"},
    "invalidate_entities": {"entity_ids"},
    "delete_document": {"document_id"},
    "delete_entity": {"entity_id"},
    "propose_mapping": set(),
    "update_mapping_status": {"mapping_id", "status"},
}

ONTOLOGY_HUB_TOOLS: dict[str, set[str]] = {
    "list_ontology_registry": set(),
    "get_ontology_graph": {"uri"},
    "search_ontology_entities": {"q"},
    "save_ontology_draft": {"ontology_uri", "diff"},
    "list_ontology_drafts": {"ontology_uri"},
    "get_ontology_draft": {"draft_id"},
    "submit_ontology_proposal": {"draft_id", "ontology_uri"},
    "list_ontology_proposals": set(),
    "get_ontology_proposal": {"proposal_id"},
    "approve_ontology_proposal": {"proposal_id"},
    "reject_ontology_proposal": {"proposal_id"},
    "publish_ontology_proposal": {"proposal_id"},
    "comment_ontology_proposal": {"proposal_id", "element_uri", "text"},
    "list_ontology_versions": {"ontology_uri"},
    "compare_ontology_versions": {"ontology_uri", "version1", "version2"},
    "restore_ontology_version_draft": {"ontology_uri", "target_version"},
    "toggle_ontology": {"ontology_uri"},
}


@pytest.mark.parametrize(
    ("tool_name", "required_fields"),
    [
        *((name, fields) for name, fields in LEDGER_MAPPING_TOOLS.items()),
        *((name, fields) for name, fields in ONTOLOGY_HUB_TOOLS.items()),
    ],
)
def test_ledger_and_ontology_tool_schemas(tool_name: str, required_fields: set[str]) -> None:
    schema = input_schema_for_tool(tool_name)
    assert schema is not None, tool_name
    assert schema.get("type") == "object"
    props = set((schema.get("properties") or {}).keys())
    assert required_fields <= props, (tool_name, required_fields - props)
    declared_required = set(schema.get("required") or [])
    assert required_fields <= declared_required, (tool_name, required_fields - declared_required)
