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


def known_ontology_uris(session: Any, registry: dict[str, Any]) -> set[str]:
    known = set(registry)
    for node_type in _ONTOLOGY_TYPES:
        for node in session.iter_nodes(node_type=node_type):
            node_id = str(node.get("id", ""))
            if node_id:
                known.add(node_id)
    return known


def collect_core_nodes(
    session: Any,
    uri: str,
    known_ontology_uris_set: set[str],
) -> dict[str, dict[str, Any]]:
    core_nodes_by_id: dict[str, dict[str, Any]] = {}
    for node_type in _SCHEMA_NODE_TYPES:
        for node in session.iter_nodes(node_type=node_type):
            node_id = str(node.get("id", ""))
            if not node_id or not _node_belongs_to_ontology(
                node, uri, known_ontology_uris_set
            ):
                continue
            core_nodes_by_id[node_id] = node
            if len(core_nodes_by_id) > _MAX_ANALYSIS_NODES:
                raise GraphTruncationError(_GRAPH_TOO_LARGE_DETAIL)
    return core_nodes_by_id


def select_structure_edges(session: Any, core_node_ids: set[str]) -> list[dict[str, Any]]:
    selected_edges: list[dict[str, Any]] = []
    for edge_type in _STRUCTURE_EDGE_TYPES:
        for edge in session.iter_edges(edge_type=edge_type):
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
