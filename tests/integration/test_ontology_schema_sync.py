"""Re-materialize ontology schema after ledger projection rebuild."""

from __future__ import annotations

from basis.domain.ontology.hub.catalog import list_registry
from basis.domain.ontology.hub.schema_sync import sync_enabled_ontology_schema
from basis.domain.ontology.browse.graph_read import get_ontology_graph


def test_sync_replays_published_versions_into_empty_graph_session() -> None:
    ontology_uri = "https://basis.local/ontology/trellis#"
    registry = {
        ontology_uri: {
            "uri": ontology_uri,
            "name": "Trellis",
            "format": "turtle",
            "status": "active",
            "enabled": True,
        }
    }
    versions = {
        ontology_uri: [
            {
                "version_id": "1.1.0",
                "diff_summary": {
                    "added_classes": ["urn:trellis:Class", "urn:trellis:Document"],
                    "added_properties": ["urn:trellis:contains"],
                    "added_edges": [
                        {
                            "source": "urn:trellis:Document",
                            "target": "urn:trellis:Class",
                            "type": "rdfs:subClassOf",
                        }
                    ],
                },
            }
        ]
    }

    class _Session:
        def __init__(self) -> None:
            self._nodes: dict[str, dict] = {}
            self._edges: list[dict] = []

        def get_nodes(self, skip=0, limit=999_999):
            return list(self._nodes.values()), 0

        def iter_nodes(self, node_type=None):
            for node in self._nodes.values():
                if node_type is None or node.get("type") == node_type:
                    yield node

        def iter_edges(self, edge_type=None):
            for edge in self._edges:
                if edge_type is None or edge.get("type") == edge_type:
                    yield edge

        def get_node(self, node_id: str):
            return self._nodes.get(node_id)

        def add_nodes(self, nodes: list[dict]) -> int:
            added = 0
            for node in nodes:
                nid = node["id"]
                if nid not in self._nodes:
                    added += 1
                self._nodes[nid] = node
            return added

        def add_nodes_and_edges(self, nodes: list[dict], edges: list[dict]) -> tuple[int, int]:
            nodes_added = self.add_nodes(nodes)
            edges_added = 0
            for edge in edges:
                self._edges.append(edge)
                edges_added += 1
            return nodes_added, edges_added

    session = _Session()
    result = sync_enabled_ontology_schema(session, registry, versions)
    assert result["repaired"] is True
    assert "urn:trellis:Class" in session._nodes

    rows = list_registry(registry, session, versions=versions)
    assert rows[0]["class_count"] == 2
    assert rows[0]["property_count"] == 1

    graph = get_ontology_graph(session, registry, uri=ontology_uri, versions=versions)
    assert len(graph["nodes"]) >= 2
