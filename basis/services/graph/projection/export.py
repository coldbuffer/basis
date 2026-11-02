"""Read-only export of in-memory ContextGraph for HTTP adapters."""

from __future__ import annotations

from typing import Any

from basis.services.graph.projection.session import GraphSession

_MAX_NODES = 500
_MAX_EDGES = 1000


def _node_label(node: Any) -> str:
    content = node.content
    if isinstance(content, str) and content.strip():
        text = content.strip()
        return text[:120] + ("…" if len(text) > 120 else "")
    props = node.properties if isinstance(node.properties, dict) else {}
    for key in ("name", "rdfs:label", "text"):
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
    return node.node_id


def _iter_edges(session: GraphSession) -> list[Any]:
    edges = session.graph.edges
    if isinstance(edges, dict):
        return list(edges.values())
    return list(edges)


def graph_snapshot(
    session: GraphSession,
    *,
    limit_nodes: int = 200,
    limit_edges: int = 400,
) -> dict[str, Any]:
    limit_nodes = min(max(1, limit_nodes), _MAX_NODES)
    limit_edges = min(max(1, limit_edges), _MAX_EDGES)

    all_nodes = sorted(session.graph.nodes.values(), key=lambda n: n.node_id)
    total_nodes = len(all_nodes)
    node_slice = all_nodes[:limit_nodes]

    nodes_out: list[dict[str, Any]] = []
    for node in node_slice:
        props = node.properties if isinstance(node.properties, dict) else {}
        nodes_out.append(
            {
                "id": node.node_id,
                "type": node.node_type,
                "label": _node_label(node),
                "statement_id": props.get("statement_id"),
                "ledger_document_id": props.get("ledger_document_id"),
            }
        )

    all_edges = sorted(
        _iter_edges(session),
        key=lambda e: (e.source_id, e.target_id, e.edge_type),
    )
    total_edges = len(all_edges)
    edge_slice = all_edges[:limit_edges]

    edges_out: list[dict[str, Any]] = []
    for edge in edge_slice:
        props = getattr(edge, "metadata", None)
        if not isinstance(props, dict):
            props = getattr(edge, "properties", None)
        if not isinstance(props, dict):
            props = {}
        edges_out.append(
            {
                "source": edge.source_id,
                "target": edge.target_id,
                "type": edge.edge_type,
                "statement_id": props.get("statement_id"),
                "evidence_id": props.get("evidence_id"),
                "projection_layer": props.get("projection_layer"),
            }
        )

    stats = session.stats()
    return {
        "stats": stats,
        "nodes": nodes_out,
        "edges": edges_out,
        "truncated": {
            "nodes": total_nodes > limit_nodes,
            "edges": total_edges > limit_edges,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
        },
    }
