"""Supplement graph neighbor lists from explicit session edges."""

from __future__ import annotations

from typing import Any

from basis.domain.graph.session.registry import GraphRuntime


def merge_session_edge_neighbors(
    runtime: GraphRuntime,
    node_id: str,
    neighbors: list[dict[str, Any]],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """When hop-walk returns sparse results, include direct in/out edges from the session."""
    session = runtime.basis
    if session is None or not node_id:
        return neighbors

    seen = {
        (str(n.get("id") or ""), str(n.get("relationship") or n.get("edge_type") or ""))
        for n in neighbors
    }
    merged = list(neighbors)
    remaining = max(0, limit - len(merged))

    def _append_edge(edge: dict[str, Any], target_id: str, relationship: str, direction: str) -> None:
        nonlocal remaining
        if remaining <= 0 or not target_id:
            return
        key = (target_id, relationship)
        if key in seen:
            return
        seen.add(key)
        node = session.get_node(target_id) if hasattr(session, "get_node") else None
        merged.append(
            {
                "id": target_id,
                "type": str((node or {}).get("type") or "entity"),
                "content": str((node or {}).get("content") or target_id),
                "relationship": relationship,
                "weight": float(edge.get("weight", 1.0) or 1.0),
                "hop": 1,
                "projection_layer": "graph",
                "direction": direction,
            }
        )
        remaining -= 1

    try:
        out_edges, _ = session.get_edges(source=node_id, skip=0, limit=limit)
        for edge in out_edges or []:
            rel = str(edge.get("type") or edge.get("edge_type") or "related_to")
            _append_edge(edge, str(edge.get("target") or ""), rel, "out")
        in_edges, _ = session.get_edges(target=node_id, skip=0, limit=limit)
        for edge in in_edges or []:
            rel = str(edge.get("type") or edge.get("edge_type") or "related_to")
            _append_edge(edge, str(edge.get("source") or ""), rel, "in")
    except Exception:
        return merged

    return merged
