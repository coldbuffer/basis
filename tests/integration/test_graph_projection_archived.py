"""Projection archived nodes excluded from search/neighbors by default."""

from __future__ import annotations

from basis.domain.graph.projection.session import GraphSession
from basis.domain.graph.reads.read import list_neighbors, search_nodes
from basis.domain.graph.reads.projection_visibility import count_projection_nodes
from basis.domain.graph.session.basis_graph_session import BasisGraphSession
from basis.domain.graph.session.registry import GraphRuntime


def _runtime_with_nodes() -> GraphRuntime:
    session = GraphSession()
    session.add_node("active-1", "entity", content="Active", name="Active")
    session.add_node("archived-1", "entity", content="Archived", name="Archived", status="archived")
    session.add_edge("active-1", "archived-1", "related_to")
    basis = BasisGraphSession(session)
    return GraphRuntime(
        workspace_id="test-ws",
        projection_revision=0,
        basis=basis,
        adapter=None,
    )


def test_neighbors_exclude_archived_by_default() -> None:
    runtime = _runtime_with_nodes()
    rows = list_neighbors(runtime, "active-1", depth=1)
    assert len(rows) == 0


def test_neighbors_include_archived_when_requested() -> None:
    runtime = _runtime_with_nodes()
    rows = list_neighbors(runtime, "active-1", depth=1, include_archived=True)
    assert len(rows) == 1
    assert rows[0]["id"] == "archived-1"


def test_search_excludes_archived() -> None:
    runtime = _runtime_with_nodes()
    hits = search_nodes(runtime, query="Archived", limit=10)
    assert hits == []


def test_count_projection_nodes_splits_archived() -> None:
    runtime = _runtime_with_nodes()
    total, active, archived = count_projection_nodes(runtime)
    assert total == 2
    assert active == 1
    assert archived == 1
