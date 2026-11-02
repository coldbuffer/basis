import pytest

pytest.importorskip("semantica")

from basis.services.ontology.hub.registry_write import create_ontology
from basis.services.ontology.shacl.shacl_generate import generate_shacl
from basis.services.errors import AdminError


def test_generate_shacl_unknown_uri() -> None:
    class _Session:
        graph = object()

        def iter_nodes(self, node_type=None):
            return iter([])

        def iter_edges(self, edge_type=None):
            return iter([])

        def get_node(self, _node_id):
            return None

    with pytest.raises(AdminError) as exc:
        generate_shacl(_Session(), {}, uri="http://missing#ont")
    assert exc.value.status == 404


def test_generate_shacl_after_scratch_create() -> None:
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
        namespace="http://example.org/sh",
        name="SHACL Test",
        mode="scratch",
    )
    uri = created["uri"]
    result = generate_shacl(session, registry, uri=uri)
    assert result["uri"] == uri
    assert isinstance(result["shacl_turtle"], str)
    assert result["shape_count"] >= 0
