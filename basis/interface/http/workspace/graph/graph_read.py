"""Workspace projected graph read and rebuild routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    graph_for,
    graph_runtime_for,
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_runtime_limits,
    get_store,
    rebuild_graph_projection,
)
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.application.graph.operations import op_graph_search, op_neighbors, op_paths
from basis.interface.http.shared.operation_http import http_response_from_payload
from basis.infra.runtime.limits import RuntimeLimits
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.graph.reads.projection_visibility import count_projection_nodes
from basis.domain.graph.reads.read import get_node, paginate_edges
from basis.domain.graph.projection.export import graph_snapshot
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.interface.http.workspace.graph.graph_models import (
    GraphSearchRequest,
    ResolveNodeLabelsRequest,
)

router = APIRouter(tags=["workspaces"])


@router.post("/{workspace_id}/graph/rebuild")
async def rebuild_graph(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Rebuild Graph. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    meta = await asyncio.to_thread(rebuild_graph_projection, request, workspace_id)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.graph.projection_rebuild",
        extra={
            "projection_revision": meta.get("projection_revision"),
            "projection_status": meta.get("projection_status"),
            "node_count": meta.get("node_count"),
            "edge_count": meta.get("edge_count"),
        },
    )
    return meta


@router.get("/{workspace_id}/graph/projection")
async def graph_projection_status(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Graph Projection Status. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    knowledge = get_knowledge_store(request)
    projection = knowledge.get_projection_state(workspace_id)
    session = graph_for(request, workspace_id)
    live = session.stats()
    return {
        **projection,
        "node_count": live.get("node_count"),
        "edge_count": live.get("edge_count"),
    }


@router.get("/{workspace_id}/graph/stats")
async def graph_stats(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, int]:
    """
Graph Stats. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    live = graph_for(request, workspace_id).stats()
    _total, active, archived = count_projection_nodes(runtime)
    return {
        "node_count": int(live.get("node_count") or 0),
        "node_count_active": active,
        "node_count_archived": archived,
        "edge_count": int(live.get("edge_count") or 0),
    }


@router.get("/{workspace_id}/graph/nodes")
async def graph_nodes_route(
    workspace_id: str,
    request: Request,
    node_type: str | None = None,
    search: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> dict[str, Any]:
    """
Graph Nodes Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    page_limit = min(max(1, limit), limits.graph_page_max_nodes)
    if runtime.adapter is not None:
        nodes, total, next_cursor = runtime.adapter.paginate_nodes(
            node_type=node_type,
            search=search,
            limit=page_limit,
            cursor=cursor,
        )
        return {
            "nodes": nodes,
            "total": total,
            "next_cursor": next_cursor,
            "engine": "explorer",
        }
    snap = graph_snapshot(runtime.basis, limit_nodes=page_limit)
    nodes = snap["nodes"]
    if search:
        query = search.lower()
        nodes = [n for n in nodes if query in n["id"].lower() or query in n["label"].lower()]
    return {"nodes": nodes, "total": len(nodes), "next_cursor": None, "engine": "snapshot"}


@router.post("/{workspace_id}/graph/resolve-labels")
async def resolve_graph_node_labels(
    workspace_id: str,
    body: ResolveNodeLabelsRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Resolve Graph Node Labels. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    ids = [str(i).strip() for i in body.ids if str(i).strip()]
    labels = knowledge.entity_labels_by_ids(workspace_id, ids)
    runtime = graph_runtime_for(request, workspace_id)
    for node_id in ids:
        if labels.get(node_id):
            continue
        node = await asyncio.to_thread(get_node, runtime, node_id)
        if node is None:
            continue
        content = str(node.get("content") or "").strip()
        props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
        name = str(props.get("name") or props.get("pref_label") or "").strip()
        labels[node_id] = content or name or None
    return {"labels": labels}


@router.get("/{workspace_id}/graph/nodes/{node_id}")
async def graph_node_route(
    workspace_id: str,
    node_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Graph Node Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    node = await asyncio.to_thread(get_node, runtime, node_id)
    if node is None:
        raise AdminError(404, "not_found", "节点不存在")
    return {"node": node}


@router.get(
    "/{workspace_id}/graph/nodes/{node_id}/neighbors",
)
async def graph_neighbors_route(
    workspace_id: str,
    node_id: str,
    request: Request,
    depth: int = 1,
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Graph Neighbors Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_neighbors,
        ctx,
        {"node_id": node_id, "depth": depth, "include_archived": include_archived},
    )
    return http_response_from_payload(payload)


@router.get("/{workspace_id}/graph/path")
async def graph_path_route(
    workspace_id: str,
    request: Request,
    source: str,
    target: str,
    algorithm: str = "bfs",
    directed: bool = True,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Graph Path Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    if algorithm not in {"bfs", "dijkstra"}:
        raise AdminError(422, "bad_algorithm", "algorithm 须为 bfs 或 dijkstra")
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_paths,
        ctx,
        {
            "source": source,
            "target": target,
            "algorithm": algorithm,
            "directed": directed,
        },
    )
    return http_response_from_payload(payload)


@router.get("/{workspace_id}/graph/edges")
async def graph_edges_route(
    workspace_id: str,
    request: Request,
    type: str | None = None,
    source: str | None = None,
    target: str | None = None,
    limit: int = 100,
    cursor: str | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> dict[str, Any]:
    """
Graph Edges Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    return await asyncio.to_thread(
        paginate_edges,
        runtime,
        edge_type=type,
        source=source,
        target=target,
        limit=limit,
        cursor=cursor,
        max_limit=limits.graph_page_max_edges,
    )


@router.post("/{workspace_id}/graph/search")
async def graph_search_route(
    workspace_id: str,
    body: GraphSearchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> dict[str, Any]:
    """
Graph Search Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_graph_search,
        ctx,
        {
            "query": body.query,
            "limit": body.limit,
            "max_limit": limits.graph_node_search_max_limit,
            "at": body.at,
            "include_archived": body.include_archived,
        },
    )
    return http_response_from_payload(payload)


@router.get("/{workspace_id}/graph/snapshot")
async def graph_snapshot_route(
    workspace_id: str,
    request: Request,
    limit_nodes: int = 200,
    limit_edges: int = 400,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> dict[str, Any]:
    """
Graph Snapshot Route. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    session = graph_for(request, workspace_id)
    capped_nodes = min(max(1, limit_nodes), limits.graph_page_max_nodes)
    capped_edges = min(max(1, limit_edges), limits.graph_page_max_edges)
    return graph_snapshot(session, limit_nodes=capped_nodes, limit_edges=capped_edges)
