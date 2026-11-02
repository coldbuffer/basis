"""Decision graph reads and causal chains."""

from __future__ import annotations

from typing import Any

from basis.services.errors import AdminError


def _decision_payload(node: dict[str, Any]) -> dict[str, Any]:
    properties = node.get("properties", {}) or {}
    return {
        "decision_id": node.get("id", ""),
        "category": properties.get("category", ""),
        "scenario": properties.get("scenario", ""),
        "reasoning": properties.get("reasoning", ""),
        "outcome": properties.get("outcome", ""),
        "confidence": float(properties.get("confidence", 0.0) or 0.0),
        "timestamp": properties.get("timestamp"),
        "metadata": properties,
    }


def list_decisions(
    session: Any,
    *,
    category: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    nodes, _ = session.get_nodes(node_type="decision", skip=0, limit=999_999)
    if category:
        cat = category.lower()
        nodes = [
            node
            for node in nodes
            if str((node.get("properties") or {}).get("category", "")).lower() == cat
        ]
    window = nodes[skip : skip + limit]
    return [_decision_payload(node) for node in window]


def get_causal_chain(session: Any, decision_id: str) -> dict[str, Any]:
    node = session.get_node(decision_id)
    if node is None:
        raise AdminError(404, "decision_not_found", f"Decision '{decision_id}' not found")
    neighbors = session.get_neighbors(decision_id, 5)
    chain = [
        {
            "id": neighbor.get("id"),
            "type": neighbor.get("type"),
            "relationship": neighbor.get("relationship"),
            "hop": neighbor.get("hop"),
            "content": neighbor.get("content", ""),
        }
        for neighbor in neighbors
    ]
    return {"decision_id": decision_id, "chain": chain}
