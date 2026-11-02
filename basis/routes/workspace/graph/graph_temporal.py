"""Workspace graph temporal scrubber routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    get_current_user,
    graph_runtime_for,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_store,
)
from basis.services.graph.session.guard import require_graph_session

router = APIRouter(tags=["workspaces"])


@router.get("/{workspace_id}/temporal/bounds")
async def temporal_bounds(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """Temporal scrubber bounds for the workspace graph (F-TIM-03 / F-TIM-04).

    Returns `{min, max}` ISO instants. When the graph projection lacks node `valid_from`,
    `min` / `max` fall back to ledger timestamps (statements, facts, current document version).
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.temporal.read import get_temporal_bounds

    base_bounds = await asyncio.to_thread(get_temporal_bounds, session)
    if isinstance(base_bounds, dict):
        ledger = get_knowledge_store(request).get_ledger_temporal_bounds(workspace_id)
        merged = dict(base_bounds)
        if not merged.get("min") and ledger.get("min"):
            merged["min"] = ledger["min"]
        if not merged.get("max") and ledger.get("max"):
            merged["max"] = ledger["max"]
        payload = merged
    return payload


@router.get("/{workspace_id}/temporal/snapshot")
async def temporal_snapshot(
    workspace_id: str,
    request: Request,
    at: str | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """Graph projection at an instant (F-TIM-03 / scrubber).

    Primary path: `graph `temporal_snapshot`. When that returns no nodes but the Basis
    projector supports `state_at`, falls back to the same snapshot used by `GET .../graph/diff`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.reads.diff import parse_query_dt
    from basis.services.graph.temporal.read import get_temporal_snapshot
    from basis.services.graph.projection.projector import build_temporal_graph_from_ledger

    payload = await asyncio.to_thread(get_temporal_snapshot, session, at)
    if at:
        try:
            instant = parse_query_dt(at)
            temporal_session = build_temporal_graph_from_ledger(
                get_knowledge_store(request), workspace_id, preserve_from=session
            )
            state = temporal_session.graph.state_at(instant)
        except ValueError:
            state = None
        if isinstance(state, dict) and (state.get("nodes") is not None):
            base = dict(payload) if isinstance(payload, dict) else {}
            state_nodes = state.get("nodes") or []
            state_node_ids = [
                str(n.get("id"))
                for n in state_nodes
                if isinstance(n, dict) and n.get("id")
            ]
            active_ids = state_node_ids if state_nodes or not base.get("active_node_ids") else base.get("active_node_ids")
            payload = {
                **base,
                "active_node_ids": active_ids,
                "active_node_count": len(active_ids),
                "nodes": state_nodes,
                "edges": state.get("edges") or [],
                "at": instant.isoformat(),
                "source": "graph_state_at",
            }
    return payload


@router.get("/{workspace_id}/temporal/diff")
async def temporal_diff(
    workspace_id: str,
    request: Request,
    from_time: str = Query(..., alias="from"),
    to_time: str = Query(..., alias="to"),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Temporal Diff. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.reads.diff import diff_session_at
    from basis.services.graph.projection.projector import build_temporal_graph_from_ledger

    temporal_session = build_temporal_graph_from_ledger(
        get_knowledge_store(request), workspace_id, preserve_from=session
    )
    diff = diff_session_at(temporal_session, from_time, to_time)
    return {
        "from_time": diff["from_time"],
        "to_time": diff["to_time"],
        "added_nodes": diff["added_nodes"],
        "removed_nodes": diff["removed_nodes"],
    }

