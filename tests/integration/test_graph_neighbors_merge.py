"""Graph neighbor merge from explicit session edges."""

from __future__ import annotations

from basis.domain.graph.reads.graph_neighbors_merge import merge_session_edge_neighbors
from basis.domain.graph.session.registry import GraphRuntime


def test_merge_session_edge_neighbors_adds_outbound() -> None:
    class _Session:
        def get_edges(self, source=None, target=None, skip=0, limit=100):
            if source == "a":
                return [{"source": "a", "target": "b", "type": "INJECTED_INTO", "weight": 1.0}], 1
            if target == "a":
                return [], 0
            return [], 0

        def get_node(self, node_id: str):
            return {"id": node_id, "type": "owl:NamedIndividual", "content": node_id}

    runtime = GraphRuntime(
        workspace_id="ws",
        projection_revision=1,
        basis=_Session(),
        adapter=None,
    )
    merged = merge_session_edge_neighbors(runtime, "a", [])
    assert len(merged) == 1
    assert merged[0]["id"] == "b"
    assert merged[0]["relationship"] == "INJECTED_INTO"
