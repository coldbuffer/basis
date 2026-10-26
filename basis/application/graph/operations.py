"""Graph application services."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.application.kernel import graph_search_max_limit
from basis.domain.graph.reads.derived_neighbors import merge_derived_fact_neighbors
from basis.domain.graph.reads.graph_neighbors_merge import merge_session_edge_neighbors
from basis.domain.graph.reads.read import find_path, list_neighbors, search_nodes


def op_graph_search(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query is required"}
    limit = int(args.get("limit", 20))
    max_limit = graph_search_max_limit(ctx, args, limit)
    at = str(args.get("at") or "").strip() or None
    include_archived = bool(args.get("include_archived"))
    runtime = ctx.graph_runtime()
    results = search_nodes(
        runtime,
        query=query,
        limit=limit,
        max_limit=max_limit,
        at=at,
        include_archived=include_archived,
    )
    engine = "explorer" if runtime.adapter is not None else "snapshot"
    payload: dict[str, Any] = {"results": results, "engine": engine}
    if at:
        payload["at"] = at
        payload["temporal_filter"] = True
    return payload


def op_find_entities(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query is required"}
    limit = int(args.get("limit", 20))
    entities = ctx.knowledge.find_entities(ctx.workspace.id, query=query, limit=limit)
    graph_hits = search_nodes(ctx.graph_runtime(), query=query, limit=limit)
    return {
        "query": query,
        "ledger_entities": entities,
        "graph_nodes": graph_hits,
    }


def op_neighbors(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    node_id = str(args.get("node_id", "")).strip()
    if not node_id:
        return {"error": "node_id is required"}
    depth = int(args.get("depth", 1))
    include_archived = bool(args.get("include_archived"))
    runtime = ctx.graph_runtime()
    neighbors = list_neighbors(
        runtime,
        node_id,
        depth=depth,
        include_archived=include_archived,
    )
    neighbors = merge_session_edge_neighbors(runtime, node_id, neighbors)
    neighbors = merge_derived_fact_neighbors(
        ctx.knowledge,
        ctx.workspace.id,
        node_id,
        neighbors,
    )
    return {
        "node_id": node_id,
        "depth": min(max(1, depth), 5),
        "neighbors": neighbors,
    }


def op_paths(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    source = str(args.get("source", "")).strip()
    target = str(args.get("target", "")).strip()
    if not source or not target:
        return {"error": "source and target are required"}
    algorithm = str(args.get("algorithm", "bfs"))
    directed = bool(args.get("directed", True))
    if algorithm not in {"bfs", "dijkstra"}:
        algorithm = "bfs"
    return find_path(
        ctx.graph_runtime(),
        source=source,
        target=target,
        algorithm=algorithm,
        directed=directed,
    )
