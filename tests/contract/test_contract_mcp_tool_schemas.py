"""MCP tool list metadata (catalog-owned schemas and descriptions)."""

from basis.application.tool_catalog import TOOL_NAMES
from basis.application.tool_catalog.catalog import OPERATIONS, mcp_exposed
from basis.application.tool_catalog.mcp_metadata import MCP_TOOL_METADATA
from basis.application.tool_catalog.run import description_for_tool, input_schema_for_tool
from basis.application.tool_catalog.validation import OPERATION_INPUT_MODELS
from basis.interface.mcp.dispatch import TOOL_DEFINITIONS


def test_every_static_tool_has_pydantic_input_model() -> None:
    assert set(OPERATION_INPUT_MODELS) == set(OPERATIONS)


def test_mcp_metadata_is_descriptions_only() -> None:
    for name, meta in MCP_TOOL_METADATA.items():
        assert set(meta.keys()) == {"description"}, name


def test_static_catalog_has_mcp_metadata_for_every_tool() -> None:
    mcp_names = {name for name in OPERATIONS if mcp_exposed(name)}
    assert set(TOOL_NAMES) == mcp_names
    for name in mcp_names:
        assert input_schema_for_tool(name) is not None, name
        assert description_for_tool(name), name


def test_mcp_tools_have_object_schemas() -> None:
    for name in OPERATIONS:
        schema = input_schema_for_tool(name)
        assert schema is not None, name
        assert schema.get("type") == "object"


def test_get_graph_summary_schema_empty_object() -> None:
    schema = input_schema_for_tool("get_graph_summary")
    assert schema is not None
    assert schema.get("type") == "object"
    assert not (schema.get("properties") or {})


def test_list_processing_jobs_schema_has_filters() -> None:
    schema = input_schema_for_tool("list_processing_jobs")
    assert schema is not None
    props = schema.get("properties") or {}
    assert "status" in props
    assert "limit" in props


def test_reasoning_run_openapi_response_includes_facts_source() -> None:
    from basis.interface.contract.openapi.spec import _spec_app
    from basis.interface.contract.openapi.v1_export import export_openapi_v1_workspaces

    spec = export_openapi_v1_workspaces(_spec_app())
    op = spec["paths"]["/api/v1/workspaces/{workspace_id}/reasoning/run"]["post"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    components = spec.get("components") or {}
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = components["schemas"][name]
    props = schema.get("properties") or {}
    assert "inferred_facts" in props
    assert "facts_source" in props
    assert "ground_facts" in props


def test_run_reasoning_schema_requires_rules_optional_facts() -> None:
    schema = input_schema_for_tool("run_reasoning")
    assert schema is not None
    props = schema.get("properties") or {}
    assert "rules" in props
    assert "facts" in props
    assert "facts_limit" in props
    assert "rules" in (schema.get("required") or [])
    assert "facts" not in (schema.get("required") or [])


def test_search_chunks_schema_uses_query_not_q() -> None:
    schema = input_schema_for_tool("search_chunks")
    assert schema is not None
    props = schema.get("properties") or {}
    assert "query" in props
    assert "q" not in props
    assert "query" in (schema.get("required") or [])


def test_approve_review_item_schema_merges_path_and_body() -> None:
    schema = input_schema_for_tool("approve_review_item")
    assert schema is not None
    props = schema.get("properties") or {}
    assert "item_id" in props
    assert "rationale" in props
    assert "item_id" in (schema.get("required") or [])


def test_reject_review_item_schema_merges_path_and_body() -> None:
    schema = input_schema_for_tool("reject_review_item")
    assert schema is not None
    props = schema.get("properties") or {}
    assert "item_id" in props
    assert "item_id" in (schema.get("required") or [])


def test_approve_review_openapi_response_includes_decision_id() -> None:
    from basis.interface.contract.openapi.spec import _spec_app
    from basis.interface.contract.openapi.v1_export import export_openapi_v1_workspaces

    spec = export_openapi_v1_workspaces(_spec_app())
    op = spec["paths"]["/api/v1/workspaces/{workspace_id}/review/items/{item_id}/approve"]["post"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    components = spec.get("components") or {}
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        schema = components["schemas"][name]
    props = schema.get("properties") or {}
    assert "item" in props
    assert "decision_id" in props


def test_tool_definitions_match_registry() -> None:
    by_name = {t["name"]: t for t in TOOL_DEFINITIONS}
    for name in TOOL_NAMES:
        assert name in by_name
        assert by_name[name]["inputSchema"]["type"] == "object"


def test_invoke_connector_primitive_schema() -> None:
    schema = input_schema_for_tool("invoke_connector_primitive")
    assert schema is not None
    props = schema.get("properties") or {}
    assert "service" in props
    assert "connection_scope" in props
    assert "action_id" in props
    assert "primitive" in props


def test_mcp_descriptions_from_catalog() -> None:
    for name in ("search_chunks", "get_graph_summary"):
        desc = description_for_tool(name)
        assert desc
        by_name = {t["name"]: t for t in TOOL_DEFINITIONS}
        assert by_name[name]["description"] == desc
