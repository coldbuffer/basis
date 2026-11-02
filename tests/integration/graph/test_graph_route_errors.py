"""Unit tests for Explorer HTTP → AdminError mapping."""

from fastapi import HTTPException

from basis.routes.workspace.graph.graph_route_errors import admin_error_from_graph_http


def test_semantic_neighborhood_404_maps_to_code() -> None:
    exc = HTTPException(status_code=404, detail="Node 'x' not found")
    admin = admin_error_from_graph_http(exc, context="semantic_neighborhood")
    assert admin.status == 404
    assert admin.code == "semantic_node_not_found"


def test_semantic_neighborhood_503_maps_to_code() -> None:
    exc = HTTPException(status_code=503, detail="Semantic similarity is unavailable")
    admin = admin_error_from_graph_http(exc, context="semantic_neighborhood")
    assert admin.status == 503
    assert admin.code == "semantic_unavailable"


def test_dict_detail_with_code_passthrough() -> None:
    exc = HTTPException(
        status_code=400,
        detail={"code": "bad_sparql", "message": "Malformed query"},
    )
    admin = admin_error_from_graph_http(exc)
    assert admin.status == 400
    assert admin.code == "bad_sparql"
    assert admin.message == "Malformed query"


def test_generic_explorer_404_maps_to_not_found() -> None:
    exc = HTTPException(status_code=404, detail="Decision missing")
    admin = admin_error_from_graph_http(exc, context="decisions")
    assert admin.code == "not_found"
