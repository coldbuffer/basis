"""Workspace graph governance decision read routes."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    graph_runtime_for,
    get_current_user,
    get_workspace_for_viewer,
    get_runtime_limits,
    get_store,
)
from basis.services.graph.session.guard import require_graph_session
from basis.infra.runtime.limits import RuntimeLimits

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/decisions")
async def list_decisions(
    workspace_id: str,
    request: Request,
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> Any:
    """
List Decisions. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.governance.decisions_read import list_decisions

    capped = min(max(1, limit), limits.graph_decisions_max_limit)
    return await asyncio.to_thread(
        list_decisions,
        session,
        category=category,
        skip=skip,
        limit=capped,
    )


@router.get("/{workspace_id}/decisions/{decision_id}/chain")
async def decision_chain(
    workspace_id: str,
    decision_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Decision chain. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.governance.decisions_read import get_causal_chain

    return await asyncio.to_thread(get_causal_chain, session, decision_id)
