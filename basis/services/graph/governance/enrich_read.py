"""Graph enrichment reads (link prediction, dedup)."""

from __future__ import annotations

import logging
from typing import Any

from basis.services.errors import AdminError

logger = logging.getLogger(__name__)

_LINK_PREDICTION_MAX_NODES = 10_000
_LINK_PREDICTION_MAX_EDGES = 50_000


def _safe_dict(obj: object) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return {key: value for key, value in obj.__dict__.items() if not key.startswith("_")}
    return {"value": str(obj)}


def predict_links(
    session: Any,
    *,
    node_id: str,
    top_n: int = 10,
    candidate_type: str | None = None,
    min_score: float = 0.0,
) -> dict[str, Any]:
    predictor = session.link_predictor
    if predictor is None:
        raise AdminError(
            503,
            "graph_runtime_unavailable",
            "LinkPredictor not available; KG extras may not be installed.",
        )

    node = session.get_node(node_id)
    if node is None:
        raise AdminError(404, "not_found", f"Node '{node_id}' not found")

    total_nodes, total_edges = session.get_raw_counts()
    if total_nodes > _LINK_PREDICTION_MAX_NODES:
        raise AdminError(
            413,
            "payload_too_large",
            (
                f"Graph has {total_nodes:,} nodes; link prediction is capped at "
                f"{_LINK_PREDICTION_MAX_NODES:,} nodes to prevent memory exhaustion. "
                "Use the graph search endpoint for large graphs."
            ),
        )
    if total_edges > _LINK_PREDICTION_MAX_EDGES:
        raise AdminError(
            413,
            "payload_too_large",
            (
                f"Graph has {total_edges:,} edges; link prediction is capped at "
                f"{_LINK_PREDICTION_MAX_EDGES:,} edges to prevent memory exhaustion. "
                "Use the graph search endpoint for large graphs."
            ),
        )

    nodes, _ = session.get_nodes(skip=0, limit=_LINK_PREDICTION_MAX_NODES)
    edges_out, _ = session.get_edges(source=node_id, skip=0, limit=_LINK_PREDICTION_MAX_NODES)
    edges_in, _ = session.get_edges(target=node_id, skip=0, limit=_LINK_PREDICTION_MAX_NODES)

    existing_neighbors = {edge.get("target") for edge in edges_out} | {
        edge.get("source") for edge in edges_in
    }

    results: list[dict[str, Any]] = []
    for candidate_node in nodes:
        candidate_id = candidate_node.get("id")
        if not candidate_id or candidate_id == node_id or candidate_id in existing_neighbors:
            continue
        if candidate_type and candidate_node.get("type") != candidate_type:
            continue
        try:
            score = predictor.score_link(session.graph, node_id, candidate_id)
        except Exception:
            continue
        if score >= min_score:
            results.append(
                {
                    "target": candidate_id,
                    "score": score,
                    "type": candidate_node.get("type", "entity"),
                    "label": candidate_node.get("content", candidate_id),
                }
            )
    results.sort(key=lambda item: item["score"], reverse=True)
    return {"node_id": node_id, "predictions": results[:top_n]}


def detect_duplicates(session: Any, *, threshold: float = 0.8) -> dict[str, Any]:
    try:
        from semantica.deduplication import DuplicateDetector
    except ImportError:
        raise AdminError(503, "graph_runtime_unavailable", "Deduplication module not available.")

    detector = DuplicateDetector()
    nodes, _ = session.get_nodes(skip=0, limit=999_999)
    entities = [
        {
            "id": node.get("id"),
            "text": node.get("content", node.get("id", "")),
            "type": node.get("type", "entity"),
        }
        for node in nodes
    ]
    try:
        duplicates = detector.detect_duplicates(entities, threshold=threshold)
    except Exception as exc:
        raise AdminError(422, "validation_error", f"Dedup scan failed: {exc}") from exc

    duplicate_list = duplicates if isinstance(duplicates, list) else getattr(duplicates, "duplicates", [])
    items = [_safe_dict(item) for item in duplicate_list]
    return {"duplicates": items, "total_flagged": len(items)}
