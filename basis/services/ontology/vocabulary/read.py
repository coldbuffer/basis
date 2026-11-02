"""SKOS vocabulary reads for workspace Explorer HTTP."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _concept_summary(
    node: dict[str, Any],
    scheme_uri: str | None = None,
    parent_uri: str | None = None,
) -> dict[str, Any]:
    properties = node.get("properties", {})
    alt_labels = properties.get("alt_labels") or []
    if isinstance(alt_labels, str):
        alt_labels = [alt_labels]
    return {
        "uri": node.get("id", ""),
        "pref_label": properties.get("pref_label")
        or properties.get("content", node.get("content", node.get("id", ""))),
        "alt_labels": list(alt_labels),
        "description": properties.get("description"),
        "notation": properties.get("notation"),
        "scheme_uri": scheme_uri,
        "parent_uri": parent_uri,
    }


def _collect_scheme_members(edges: list[dict[str, Any]], scheme_uri: str) -> set[str]:
    members: set[str] = set()
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type")
        if target == scheme_uri and edge_type in {"skos:inScheme", "skos:topConceptOf"}:
            members.add(source)
        elif source == scheme_uri and edge_type == "skos:hasTopConcept":
            members.add(target)
    return members


def _collect_parent_map(member_ids: set[str], edges: list[dict[str, Any]]) -> dict[str, str]:
    parent_by_child: dict[str, str] = {}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        edge_type = edge.get("type")
        if source not in member_ids or target not in member_ids:
            continue
        if edge_type == "skos:broader":
            parent_by_child.setdefault(source, target)
        elif edge_type == "skos:narrower":
            parent_by_child.setdefault(target, source)
    return parent_by_child


def _build_hierarchy(
    concepts: dict[str, dict[str, Any]],
    parent_by_child: dict[str, str],
) -> list[dict[str, Any]]:
    children_by_parent: dict[str, list[str]] = defaultdict(list)
    for child_uri, parent_uri in parent_by_child.items():
        if child_uri != parent_uri:
            children_by_parent[parent_uri].append(child_uri)

    def attach(uri: str, trail: set[str]) -> dict[str, Any]:
        concept = concepts[uri]
        child_nodes = [
            attach(child_uri, trail | {uri})
            for child_uri in sorted(children_by_parent.get(uri, []))
            if child_uri not in trail
        ]
        out = dict(concept)
        out["children"] = child_nodes or None
        return out

    root_ids = [uri for uri in sorted(concepts.keys()) if uri not in parent_by_child]
    if not root_ids:
        root_ids = sorted(concepts.keys())
    return [attach(uri, {uri}) for uri in root_ids]


def list_schemes(session: Any) -> list[dict[str, Any]]:
    nodes, _ = session.get_nodes(node_type="skos:ConceptScheme", skip=0, limit=999_999)
    return [
        {
            "uri": node.get("id", ""),
            "label": node.get("properties", {}).get("content", node.get("content", node.get("id", ""))),
            "description": node.get("properties", {}).get("description"),
        }
        for node in nodes
    ]


def list_concepts(
    session: Any,
    *,
    scheme: str,
    search: str | None = None,
) -> list[dict[str, Any]]:
    nodes, _ = session.get_nodes(node_type="skos:Concept", search=search, skip=0, limit=999_999)
    edges, _ = session.get_edges(skip=0, limit=999_999)
    member_ids = _collect_scheme_members(edges, scheme)
    parent_by_child = _collect_parent_map(member_ids, edges)

    concepts = []
    for node in nodes:
        node_id = node.get("id")
        if node_id not in member_ids:
            continue
        concepts.append(
            _concept_summary(node, scheme_uri=scheme, parent_uri=parent_by_child.get(node_id))
        )
    return sorted(concepts, key=lambda concept: (concept["pref_label"].lower(), concept["uri"]))


def get_hierarchy(session: Any, *, scheme: str) -> list[dict[str, Any]]:
    nodes, _ = session.get_nodes(node_type="skos:Concept", skip=0, limit=999_999)
    edges, _ = session.get_edges(skip=0, limit=999_999)
    member_ids = _collect_scheme_members(edges, scheme)
    parent_by_child = _collect_parent_map(member_ids, edges)

    concepts: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id = node.get("id")
        if node_id not in member_ids:
            continue
        concepts[node_id] = _concept_summary(
            node,
            scheme_uri=scheme,
            parent_uri=parent_by_child.get(node_id),
        )
    return _build_hierarchy(concepts, parent_by_child)
