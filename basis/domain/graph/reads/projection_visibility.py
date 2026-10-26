"""Projection node visibility (archived soft-delete markers)."""

from __future__ import annotations

from typing import Any

from basis.domain.graph.session.registry import GraphRuntime


def properties_archived(properties: Any) -> bool:
    if not isinstance(properties, dict):
        return False
    return str(properties.get("status") or "").strip().lower() == "archived"


def _dict_archived(raw: dict[str, Any]) -> bool:
    props = raw.get("properties")
    if isinstance(props, dict) and properties_archived(props):
        return True
    meta = raw.get("metadata")
    if isinstance(meta, dict) and properties_archived(meta):
        return True
    return properties_archived(raw)


def node_record_archived(node: dict[str, Any] | None) -> bool:
    if not node:
        return False
    if properties_archived(node.get("properties")):
        return True
    return _dict_archived(node)


def is_node_archived(runtime: GraphRuntime, node_id: str) -> bool:
    from basis.domain.graph.reads.read import get_node

    graph = runtime.basis.graph
    raw = graph.find_node(node_id) if hasattr(graph, "find_node") else None
    if raw is not None:
        if isinstance(raw, dict):
            if _dict_archived(raw):
                return True
        else:
            if properties_archived(getattr(raw, "properties", None)):
                return True
            if properties_archived(getattr(raw, "metadata", None)):
                return True
    return node_record_archived(get_node(runtime, node_id))


def filter_neighbor_rows(
    runtime: GraphRuntime,
    neighbors: list[dict[str, Any]],
    *,
    include_archived: bool,
) -> list[dict[str, Any]]:
    if include_archived:
        return neighbors
    return [row for row in neighbors if not is_node_archived(runtime, str(row.get("id") or ""))]


def filter_search_results(
    runtime: GraphRuntime,
    results: list[dict[str, Any]],
    *,
    include_archived: bool,
) -> list[dict[str, Any]]:
    if include_archived:
        return results
    kept: list[dict[str, Any]] = []
    for row in results:
        node = row.get("node") if isinstance(row.get("node"), dict) else row
        node_id = str(node.get("id") or "") if isinstance(node, dict) else ""
        if node_id and is_node_archived(runtime, node_id):
            continue
        kept.append(row)
    return kept


def count_projection_nodes(runtime: GraphRuntime) -> tuple[int, int, int]:
    """Return (total, active, archived) projection nodes."""
    total = 0
    archived = 0
    if runtime.adapter is not None:
        basis = runtime.basis
    else:
        basis = runtime.basis
    for node in basis.graph.nodes.values():
        total += 1
        props = dict(node.properties) if isinstance(node.properties, dict) else {}
        if properties_archived(props):
            archived += 1
    active = total - archived
    return total, active, archived
