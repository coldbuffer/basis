"""Core operation dispatch (R1)."""

from basis.application.tool_catalog import TOOL_NAMES
from basis.interface.mcp.dispatch import execute


def test_tool_names_match_registry() -> None:
    assert len(TOOL_NAMES) == 70
    assert "search_chunks" in TOOL_NAMES
    assert "list_connector_catalog" in TOOL_NAMES
    assert "list_typed_facts" in TOOL_NAMES
    assert "run_reasoning" in TOOL_NAMES
    assert "get_graph_summary" in TOOL_NAMES
    assert "list_processing_jobs" in TOOL_NAMES
    assert "query_graph" in TOOL_NAMES
    assert "extract_entities" in TOOL_NAMES
    assert "reset_workspace" in TOOL_NAMES
    assert "restore_ontology_version_draft" in TOOL_NAMES


def test_execute_unknown_operation() -> None:
    # Minimal ctx stub — only name dispatch is tested.
    class _Workspace:
        id = "ws1"

    class _Ctx:
        workspace = _Workspace()

    result = execute(_Ctx(), "not_a_tool", {})  # type: ignore[arg-type]
    assert result["isError"] is True
