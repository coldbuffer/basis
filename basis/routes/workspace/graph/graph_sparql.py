"""Workspace graph SPARQL execution."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    graph_runtime_for,
    get_current_user,
    get_workspace_for_viewer,
    get_store,
)
from basis.services.graph.session.guard import require_graph_session
from basis.routes.workspace.graph.graph_shared import sparql_semaphore
from basis.services.graph.sparql.read import (
    SPARQL_TIMEOUT_S,
    build_sparql_graph,
    run_sparql_on_graph,
    sparql_error_response,
    sparql_query_preflight,
    sparql_timeout_response,
)

router = APIRouter(tags=["workspaces"])

@router.post("/{workspace_id}/sparql")
async def sparql_execute(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
SPARQL Execute. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    raw = await request.json()
    query = raw.get("query", "") if isinstance(raw, dict) else ""
    if not isinstance(query, str):
        raise AdminError(422, "validation_error", "query 必填且为字符串")

    preflight = sparql_query_preflight(query)
    if preflight is not None:
        return preflight

    try:
        graph = await asyncio.to_thread(build_sparql_graph, session)
    except ValueError as exc:
        return sparql_error_response(str(exc))

    async with sparql_semaphore:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(run_sparql_on_graph, graph, query),
                timeout=SPARQL_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            return sparql_timeout_response()
