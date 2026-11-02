"""BasisGraphSession adapter tests."""

from basis.services.graph.session.basis_graph_session import BasisGraphSession
from basis.services.graph.projection.session import GraphSession


def test_basis_graph_session_round_trip_nodes_edges() -> None:
    basis = GraphSession()
    session = BasisGraphSession(basis)
    session.add_node("a", "entity", content="Alpha")
    session.add_node("b", "entity", content="Beta")
    session.add_edge("a", "b", "related_to")

    node = session.get_node("a")
    assert node is not None
    assert node["content"] == "Alpha"

    nodes, total = session.get_nodes(skip=0, limit=10)
    assert total == 2
    assert {n["id"] for n in nodes} == {"a", "b"}

    edges, edge_total = session.get_edges(skip=0, limit=10)
    assert edge_total == 1
    assert edges[0]["source"] == "a"
    assert edges[0]["target"] == "b"

    hits = session.search("alpha", limit=5)
    assert len(hits) == 1
    assert hits[0]["node"]["id"] == "a"
