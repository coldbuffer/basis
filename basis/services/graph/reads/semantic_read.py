"""Semantic graph reads (neighborhood, distance matrix)."""

from __future__ import annotations

import logging
import time
from typing import Any

from basis.services.errors import AdminError

logger = logging.getLogger(__name__)

_MAX_DISTANCE_MATRIX_NODES = 50


def _path_weight(graph: Any, path_nodes: list[str]) -> float:
    total = 0.0
    for index in range(len(path_nodes) - 1):
        data = graph.get_edge_data(path_nodes[index], path_nodes[index + 1]) or {}
        total += float(data.get("weight", 1.0))
    return total


def semantic_neighborhood(
    session: Any,
    node_id: str,
    *,
    top_k: int = 20,
    min_similarity: float = 0.0,
) -> dict[str, Any]:
    node = session.get_node(node_id)
    if node is None:
        raise AdminError(404, "semantic_node_not_found", "语义距离接口未找到所选节点")

    similarity = session.similarity
    if similarity is None:
        raise AdminError(503, "semantic_unavailable", "当前图谱不支持语义相似度")

    embeddings = session.get_cached_embeddings()
    query_embedding = embeddings.get(node_id)
    if not embeddings or query_embedding is None:
        raise AdminError(503, "semantic_unavailable", "当前图谱不支持语义相似度")

    neighbors: list[dict[str, Any]] = []
    try:
        similar = similarity.find_most_similar(
            embeddings,
            query_embedding,
            top_k=top_k * 2,
        )
    except Exception as exc:
        logger.debug("semantic_neighborhood similarity search failed: %s", exc)
        raise AdminError(503, "semantic_unavailable", "当前图谱不支持语义相似度") from exc

    for item in similar:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            nid, sim_score = item[0], item[1]
        elif isinstance(item, dict):
            nid = item.get("node_id") or item.get("id", "")
            sim_score = item.get("similarity", item.get("score", 0.0))
        else:
            continue
        if float(sim_score) < min_similarity or nid == node_id:
            continue
        neighbor_node = session.get_node(nid)
        if neighbor_node is None:
            continue
        neighbors.append(
            {
                "id": str(nid),
                "type": neighbor_node.get("type", ""),
                "content": neighbor_node.get("content", ""),
                "similarity": float(sim_score),
            }
        )
        if len(neighbors) >= top_k:
            break

    return {
        "anchor_node": node_id,
        "neighbors": neighbors,
        "total": len(neighbors),
    }


def distance_matrix(
    session: Any,
    *,
    node_ids: list[str],
    metric: str = "hops",
) -> dict[str, Any]:
    if len(node_ids) > _MAX_DISTANCE_MATRIX_NODES:
        raise AdminError(
            413,
            "payload_too_large",
            f"Too many nodes: {len(node_ids)} requested; maximum is {_MAX_DISTANCE_MATRIX_NODES} per request.",
        )

    if metric == "semantic" and session.similarity is None:
        raise AdminError(503, "semantic_unavailable", "当前图谱不支持语义相似度")

    started = time.perf_counter()
    path_finder = session.path_finder

    n = len(node_ids)
    matrix: list[list[float | None]] = [[None] * n for _ in range(n)]
    unreachable: list[tuple[str, str]] = []
    matrix_graph = None

    for i in range(n):
        matrix[i][i] = 0.0
        for j in range(i + 1, n):
            src, tgt = node_ids[i], node_ids[j]
            try:
                if metric == "semantic" and session.similarity is not None:
                    embeddings = session.get_cached_embeddings()
                    src_embedding = embeddings.get(src)
                    tgt_embedding = embeddings.get(tgt)

                    if src_embedding is None or tgt_embedding is None:
                        val = None
                    else:
                        import numpy as np

                        src_vec = np.array(src_embedding)
                        tgt_vec = np.array(tgt_embedding)
                        sim = np.dot(src_vec, tgt_vec) / (
                            np.linalg.norm(src_vec) * np.linalg.norm(tgt_vec)
                        )
                        val = 1.0 - float(sim) if isinstance(sim, (int, float)) else None

                    matrix[i][j] = val
                    matrix[j][i] = val
                elif path_finder is not None:
                    path_fn = (
                        path_finder.dijkstra_shortest_path
                        if metric == "weighted"
                        else path_finder.bfs_shortest_path
                    )
                    if matrix_graph is None:
                        matrix_graph = session.build_nx_graph()

                    for row, col, a, b in ((i, j, src, tgt), (j, i, tgt, src)):
                        result = path_fn(matrix_graph, a, b)
                        path_nodes = (
                            result.get("path", [])
                            if isinstance(result, dict)
                            else (result or [])
                        )
                        if not path_nodes:
                            unreachable.append((a, b))
                            continue
                        if metric == "weighted":
                            matrix[row][col] = (
                                float(result.get("total_weight", len(path_nodes) - 1))
                                if isinstance(result, dict)
                                else _path_weight(matrix_graph, path_nodes)
                            )
                        else:
                            matrix[row][col] = float(len(path_nodes) - 1)
            except Exception as exc:
                logger.debug("distance_matrix pair (%s, %s) failed: %s", src, tgt, exc)
                unreachable.append((src, tgt))
                unreachable.append((tgt, src))

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "nodes": node_ids,
        "metric": metric,
        "matrix": matrix,
        "unreachable_pairs": unreachable,
        "computation_time_ms": elapsed_ms,
    }
