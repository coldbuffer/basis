import asyncio

import pytest

pytest.importorskip("semantica")

from basis.domain.ontology.hub.create_write import create_ontology
from basis.domain.ontology.browse.health_read import ontology_health
from basis.domain.tenancy.admin.errors import AdminError


def test_ontology_health_for_scratch_ontology() -> None:
    nodes_store: dict[str, dict] = {}
    edges_store: list[dict] = []

    class _Session:
        graph = object()

        def add_nodes_and_edges(self, nodes, edges):
            for node in nodes:
                nodes_store[node["id"]] = node
            edges_store.extend(edges)
            return len(nodes), len(edges)

        def get_nodes(self, skip=0, limit=999_999):
            items = list(nodes_store.values())[skip : skip + limit]
            return items, len(nodes_store)

        def get_edges(self, skip=0, limit=999_999):
            items = edges_store[skip : skip + limit]
            return items, len(edges_store)

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
        namespace="http://example.org/hlth",
        name="Health Ont",
        mode="scratch",
    )
    uri = created["uri"]

    async def _run() -> dict:
        return await ontology_health(session, registry, {}, uri=uri)

    report = asyncio.run(_run())
    assert report["uri"] == uri
    assert report["name"] == "Health Ont"
    assert "total_score" in report
    assert len(report["dimensions"]) >= 4
    shacl = next(d for d in report["dimensions"] if d["key"] == "shacl")
    assert shacl["status"] != "critical" or "Ontology not found" not in shacl.get("detail", "")


def test_ontology_health_implicit_graph_ontology() -> None:
    """Scratch create registers in dict; graph-only ontologies still resolve via known URIs."""
    nodes_store: dict[str, dict] = {}
    edges_store: list[dict] = []

    class _Session:
        graph = object()

        def add_nodes_and_edges(self, nodes, edges):
            for node in nodes:
                nodes_store[node["id"]] = node
            edges_store.extend(edges)
            return len(nodes), len(edges)

        def get_nodes(self, skip=0, limit=999_999):
            items = list(nodes_store.values())[skip : skip + limit]
            return items, len(nodes_store)

        def get_edges(self, skip=0, limit=999_999):
            items = edges_store[skip : skip + limit]
            return items, len(edges_store)

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
    uri = "http://example.org/implicit#ontology"
    session.add_nodes_and_edges(
        [
            {
                "id": uri,
                "type": "owl:Ontology",
                "content": "Implicit",
                "properties": {"namespace": "http://example.org/implicit"},
            }
        ],
        [],
    )

    async def _run() -> dict:
        return await ontology_health(session, {}, {}, uri=uri)

    report = asyncio.run(_run())
    assert report["uri"] == uri
    assert report["name"] == "Implicit"


def test_ontology_health_alignment_issue_includes_entity_uri() -> None:
    nodes_store: dict[str, dict] = {}
    edges_store: list[dict] = []

    class _Session:
        graph = object()

        def get_nodes(self, skip=0, limit=999_999):
            items = list(nodes_store.values())[skip : skip + limit]
            return items, len(nodes_store)

        def get_edges(self, skip=0, limit=999_999):
            items = edges_store[skip : skip + limit]
            return items, len(edges_store)

        def iter_nodes(self, node_type=None):
            for node in nodes_store.values():
                if node_type is None or node.get("type") == node_type:
                    yield node

        def get_node(self, node_id):
            return nodes_store.get(node_id)

    session = _Session()
    uri = "http://example.org/align"
    nodes_store[uri] = {
        "id": uri,
        "type": "owl:Ontology",
        "content": "Align Ont",
        "properties": {"namespace": uri},
    }
    nodes_store["http://example.org/align#Person"] = {
        "id": "http://example.org/align#Person",
        "type": "owl:Class",
        "content": "Person",
        "properties": {"rdfs:label": "Person"},
    }

    async def _run() -> dict:
        return await ontology_health(session, {uri: {"name": "Align Ont", "uri": uri}}, {}, uri=uri)

    report = asyncio.run(_run())
    alignment_issues = [issue for issue in report["issues"] if issue.get("category") == "Alignment"]
    assert len(alignment_issues) == 1
    assert alignment_issues[0]["entity_uri"] == uri
    assert alignment_issues[0]["entity_label"] == "Align Ont"


def test_ontology_health_missing_registry_entry() -> None:
    class _Session:
        graph = object()

        def get_nodes(self, skip=0, limit=0):
            return [], 0

        def get_edges(self, skip=0, limit=0):
            return [], 0

        def iter_nodes(self, node_type=None):
            return iter([])

        def get_node(self, node_id):
            return None

    async def _run() -> None:
        with pytest.raises(AdminError) as exc:
            await ontology_health(_Session(), {}, {}, uri="http://missing#o")
        assert exc.value.status == 404

    asyncio.run(_run())
