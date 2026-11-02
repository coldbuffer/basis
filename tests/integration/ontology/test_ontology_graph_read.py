import pytest

from basis.services.ontology.hub.registry_write import create_ontology
from basis.services.ontology.browse.graph_read import get_ontology_graph, search_entities
from basis.services.errors import AdminError


def test_search_entities_requires_query() -> None:
    class _Session:
        def search(self, *_a: object, **_k: object) -> list:
            return []

    with pytest.raises(AdminError) as exc:
        search_entities(_Session(), q="  ", limit=10)
    assert exc.value.status == 422


def test_create_and_graph_scratch_ontology() -> None:
    nodes_store: dict[str, dict] = {}
    edges_store: list[dict] = []

    class _Session:
        graph = object()

        def add_nodes_and_edges(self, nodes, edges):
            for node in nodes:
                nodes_store[node["id"]] = node
            edges_store.extend(edges)
            return len(nodes), len(edges)

        def iter_nodes(self, node_type=None):
            for node in nodes_store.values():
                if node_type is None or node.get("type") == node_type:
                    yield node

        def iter_edges(self, edge_type=None):
            for edge in edges_store:
                if edge_type is None or edge.get("type") == edge_type:
                    yield edge

        def get_node(self, node_id):
            return nodes_store.get(node_id)

    session = _Session()
    registry: dict = {}
    created = create_ontology(
        session,
        registry,
        namespace="http://example.org/ont",
        name="Demo",
        mode="scratch",
    )
    uri = created["uri"]
    assert uri in registry

    graph = get_ontology_graph(session, registry, uri=uri)
    assert graph["uri"] == uri
    assert any(n.get("type") == "owl:Ontology" for n in graph["nodes"])
