"""Ontology schema subgraph for SHACL / health analysis (same scope as GET /graph)."""

from __future__ import annotations

from typing import Any

from basis.services.ontology.browse.graph_scope import (
    GraphTruncationError,
    collect_core_nodes,
    known_ontology_uris,
    select_structure_edges,
)
from basis.services.errors import AdminError


def load_ontology_analysis_graph(
    session: Any,
    registry: dict[str, Any],
    uri: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    known = known_ontology_uris(session, registry)
    if uri not in known:
        raise AdminError(404, "not_found", "Ontology not found in registry.")

    try:
        core_nodes_by_id = collect_core_nodes(session, uri, known)
        if not core_nodes_by_id:
            return [], []
        core_node_ids = set(core_nodes_by_id)
        selected_edges = select_structure_edges(session, core_node_ids)
    except GraphTruncationError as exc:
        raise AdminError(413, "payload_too_large", str(exc)) from exc

    external_node_ids = {
        node_id
        for edge in selected_edges
        for node_id in (str(edge.get("source", "")), str(edge.get("target", "")))
    } - core_node_ids
    external_nodes = [session.get_node(node_id) for node_id in external_node_ids]
    selected_nodes = list(core_nodes_by_id.values())
    selected_nodes.extend(node for node in external_nodes if node is not None)
    return selected_nodes, selected_edges
