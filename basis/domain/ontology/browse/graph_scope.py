"""Ontology schema subgraph scope (known URIs, core nodes, structure edges)."""

from __future__ import annotations

from typing import Any

from basis.domain.ontology.hub.catalog import (
    _CLASS_TYPES,
    _CONCEPT_TYPES,
    _INDIVIDUAL_TYPES,
    _ONTOLOGY_TYPES,
    _PROPERTY_TYPES,
    _SCHEME_TYPES,
    _node_belongs_to_ontology,
    _node_source_ontology,
    published_entity_uris_for_ontology,
)

_MAX_ANALYSIS_NODES = 5_000
_GRAPH_TOO_LARGE_DETAIL = (
    "Ontology editor graph exceeds the maximum size "
    f"({_MAX_ANALYSIS_NODES} nodes or edges)."
)

_SCHEMA_NODE_TYPES = _CLASS_TYPES | _PROPERTY_TYPES | _CONCEPT_TYPES | _ONTOLOGY_TYPES
_SEARCHABLE_TYPES = _CLASS_TYPES | _PROPERTY_TYPES | _INDIVIDUAL_TYPES | _CONCEPT_TYPES | _SCHEME_TYPES
_STRUCTURE_EDGE_TYPES = frozenset({
    "rdf:type",
    "rdfs:subClassOf",
    "rdfs:domain",
    "rdfs:range",
    "owl:onProperty",
    "owl:someValuesFrom",
    "owl:disjointWith",
    "owl:equivalentClass",
    "owl:equivalentProperty",
    "owl:inverseOf",
    "skos:broader",
    "skos:narrower",
    "skos:related",
})


class GraphTruncationError(Exception):
    """Raised when a graph exceeds analysis limits."""


def searchable_node_types() -> frozenset[str]:
    return _SEARCHABLE_TYPES


def _node_dict_from_raw(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    props = dict(getattr(raw, "properties", {}) or {})
    return {
        "id": str(getattr(raw, "node_id", "") or ""),
        "type": str(getattr(raw, "node_type", "") or ""),
        "content": getattr(raw, "content", None),
        "properties": props,
    }


def _iter_session_nodes(session: Any, node_type: str | None = None):
    if hasattr(session, "iter_nodes"):
        for node in session.iter_nodes(node_type=node_type):
            yield node
        return
    if hasattr(session, "get_nodes"):
        nodes, _ = session.get_nodes(skip=0, limit=999_999)
        for node in nodes or []:
            if node_type is None or node.get("type") == node_type:
                yield node
        return
    graph = getattr(session, "graph", None)
    if graph is not None and hasattr(graph, "nodes"):
        for raw in graph.nodes.values():
            node = _node_dict_from_raw(raw)
            if node_type is None or node.get("type") == node_type:
                yield node


def _iter_session_edges(session: Any, edge_type: str | None = None):
    if hasattr(session, "iter_edges"):
        for edge in session.iter_edges(edge_type=edge_type):
            yield edge
        return
    graph = getattr(session, "graph", None)
    if graph is None or not hasattr(graph, "edges"):
        return
    edges = graph.edges
    edge_values = edges.values() if isinstance(edges, dict) else edges
    for raw in edge_values:
        edge = raw if isinstance(raw, dict) else {
            "id": getattr(raw, "edge_id", None),
            "source": getattr(raw, "source_id", ""),
            "target": getattr(raw, "target_id", ""),
            "type": getattr(raw, "edge_type", ""),
            "properties": dict(getattr(raw, "properties", {}) or {}),
        }
        if edge_type is None or edge.get("type") == edge_type:
            yield edge


def known_ontology_uris(session: Any, registry: dict[str, Any]) -> set[str]:
    known = set(registry)
    for node_type in _ONTOLOGY_TYPES:
        for node in _iter_session_nodes(session, node_type=node_type):
            node_id = str(node.get("id", ""))
            if node_id:
                known.add(node_id)
    return known


def collect_core_nodes(
    session: Any,
    uri: str,
    known_ontology_uris_set: set[str],
    *,
    versions: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    published_entity_uris = published_entity_uris_for_ontology(versions, uri)
    core_nodes_by_id: dict[str, dict[str, Any]] = {}
    for node_type in _SCHEMA_NODE_TYPES:
        for node in _iter_session_nodes(session, node_type=node_type):
            node_id = str(node.get("id", ""))
            if not node_id or not _node_belongs_to_ontology(
                node,
                uri,
                known_ontology_uris_set,
                published_entity_uris=published_entity_uris,
            ):
                continue
            core_nodes_by_id[node_id] = node
            if len(core_nodes_by_id) > _MAX_ANALYSIS_NODES:
                raise GraphTruncationError(_GRAPH_TOO_LARGE_DETAIL)
    return core_nodes_by_id


def select_structure_edges(session: Any, core_node_ids: set[str]) -> list[dict[str, Any]]:
    selected_edges: list[dict[str, Any]] = []
    for edge_type in _STRUCTURE_EDGE_TYPES:
        for edge in _iter_session_edges(session, edge_type=edge_type):
            if str(edge.get("source", "")) not in core_node_ids:
                continue
            selected_edges.append(edge)
            if len(selected_edges) > _MAX_ANALYSIS_NODES:
                raise GraphTruncationError(_GRAPH_TOO_LARGE_DETAIL)
    return selected_edges


def resolve_owning_ontology(node: dict[str, Any], known_ontology_uris_set: set[str]) -> str | None:
    nid = str(node.get("id", ""))
    if not nid:
        return None

    if nid in known_ontology_uris_set:
        return nid

    explicit_owner = _node_source_ontology(node)
    if explicit_owner:
        return explicit_owner

    longest_namespace: str | None = None
    for candidate in known_ontology_uris_set:
        stem = candidate.rstrip("#/")
        if not nid.startswith((stem + "#", stem + "/")):
            continue
        if longest_namespace is None or len(candidate) > len(longest_namespace):
            longest_namespace = candidate
    if longest_namespace is None:
        return None

    local_name = nid[len(longest_namespace.rstrip("#/")) + 1 :]
    if "#" in local_name or "/" in local_name:
        return None
    return longest_namespace
