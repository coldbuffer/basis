"""Apply ontology editor draft diffs onto a workspace graph session."""

from __future__ import annotations

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


def as_draft_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {}


def _session_graph(session: Any) -> Any | None:
    return getattr(session, "graph", None)


def _purge_node(session: Any, node_id: str) -> bool:
    graph = _session_graph(session)
    if graph is None or not node_id:
        return False
    if not graph.find_node(node_id):
        return False
    if hasattr(graph, "purge_node"):
        return bool(graph.purge_node(node_id))
    if hasattr(graph, "add_node_attribute"):
        graph.add_node_attribute(node_id, {"status": "archived"})
        return True
    return False


def _purge_edge(session: Any, edge_id: str) -> bool:
    graph = _session_graph(session)
    if graph is None or not edge_id:
        return False
    if hasattr(graph, "purge_edge"):
        return bool(graph.purge_edge(edge_id))
    if hasattr(graph, "retract_edge"):
        return bool(graph.retract_edge(edge_id))
    return False


def _restriction_namespace(ontology_uri: str) -> str:
    stem = str(ontology_uri).rstrip("/#")
    if stem.endswith("#ontology"):
        stem = stem[: -len("#ontology")].rstrip("/#")
    return stem or ontology_uri


def materialize_restrictions(
    ontology_uri: str,
    restrictions: list[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    ns = _restriction_namespace(ontology_uri)
    for raw in restrictions:
        data = as_draft_mapping(raw)
        restriction_type = str(data.get("type", "")).strip()
        class_uri = str(data.get("class_uri") or data.get("subject") or "").strip()
        on_property = str(data.get("onProperty") or "").strip()
        filler = str(data.get("filler_class") or data.get("onClass") or data.get("value") or "").strip()
        if restriction_type != "someValuesFrom":
            continue
        if not class_uri or not on_property or not filler:
            continue
        restriction_uri = f"{ns}/_restriction/{uuid.uuid4().hex[:12]}"
        nodes.append(
            {
                "id": restriction_uri,
                "type": "owl:Restriction",
                "content": "",
                "properties": {
                    "owl:onProperty": on_property,
                    "owl:someValuesFrom": filler,
                },
            }
        )
        edges.append(
            {
                "source": class_uri,
                "target": restriction_uri,
                "type": "rdfs:subClassOf",
                "weight": 1.0,
            }
        )
        edges.append(
            {
                "source": restriction_uri,
                "target": on_property,
                "type": "owl:onProperty",
                "weight": 1.0,
            }
        )
        edges.append(
            {
                "source": restriction_uri,
                "target": filler,
                "type": "owl:someValuesFrom",
                "weight": 1.0,
            }
        )
    return nodes, edges


def apply_removals(
    session: Any,
    diff: Any,
    *,
    diff_list: Any,
) -> tuple[int, int]:
    """Archive/purge nodes and edges listed in the draft diff. Returns (nodes_removed, edges_removed)."""
    nodes_removed = 0
    edges_removed = 0
    for edge_id in diff_list(diff, "removed_edges"):
        if _purge_edge(session, str(edge_id)):
            edges_removed += 1
    for node_id in diff_list(diff, "removed_classes"):
        if _purge_node(session, str(node_id)):
            nodes_removed += 1
    for node_id in diff_list(diff, "removed_properties"):
        if _purge_node(session, str(node_id)):
            nodes_removed += 1
    for node_id in diff_list(diff, "removed_individuals"):
        if _purge_node(session, str(node_id)):
            nodes_removed += 1
    return nodes_removed, edges_removed
