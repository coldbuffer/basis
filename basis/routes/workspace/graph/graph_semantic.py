"""Workspace graph semantic graph analytics."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    graph_runtime_for,
    get_current_user,
    get_workspace_for_viewer,
    get_store,
)
from basis.services.graph.session.guard import require_graph_session

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/graph/semantic-neighborhood")
async def graph_semantic_neighborhood(
    workspace_id: str,
    request: Request,
    node_id: str = Query(...),
    top_k: int = Query(20, ge=1, le=200),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Graph Semantic Neighborhood. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.reads.semantic_read import semantic_neighborhood

    return await asyncio.to_thread(
        semantic_neighborhood,
        session,
        node_id,
        top_k=top_k,
        min_similarity=min_similarity,
    )


@router.post("/{workspace_id}/graph/distance-matrix")
async def graph_distance_matrix(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Graph Distance Matrix. Projected graph read API (graph runtime). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.reads.semantic_read import distance_matrix

    raw = await request.json()
    node_ids = raw.get("node_ids") if isinstance(raw, dict) else None
    metric = raw.get("metric", "hops") if isinstance(raw, dict) else "hops"
    if not isinstance(node_ids, list) or not node_ids:
        raise AdminError(422, "validation_error", "node_ids 必填且为非空数组")
    return await asyncio.to_thread(
        distance_matrix,
        session,
        node_ids=[str(n) for n in node_ids],
        metric=str(metric),
    )
