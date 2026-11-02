"""Workspace graph reasoning run route."""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, Query, Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store
from basis.http.core_context import build_workspace_core_context
from basis.routes.workspace.graph.graph_models import (
    ReasoningGroundFactsResponse,
    ReasoningRunRequest,
    ReasoningRunResponse,
)
from basis.http.operation_http import http_response_from_payload
from basis.services.graph.operations import (
    op_list_reasoning_ground_facts,
    op_run_reasoning,
)

router = APIRouter(tags=["workspaces"])


@router.get(
    "/{workspace_id}/reasoning/ground-facts",
)
async def list_reasoning_ground_facts_route(
    workspace_id: str,
    request: Request,
    limit: int = Query(200, ge=1, le=500),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> ReasoningGroundFactsResponse:
    """
List Reasoning Ground Facts. Derive predicate(subject, object) strings from typed_facts for reasoning/run. Requires workspace membership (session) or workspace API token with read scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_list_reasoning_ground_facts, ctx, {"limit": limit}
    )
    data = http_response_from_payload(payload)
    return ReasoningGroundFactsResponse.model_validate(data)


@router.post("/{workspace_id}/reasoning/run")
async def reasoning_run(
    workspace_id: str,
    body: ReasoningRunRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> ReasoningRunResponse:
    """
Reasoning Run. Workspace-local reasoning rules and runs. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    raw = body.model_dump(mode="json")
    apply_to_graph = body.apply_to_graph
    role = "editor" if apply_to_graph else "viewer"
    store.get_workspace_for(user, workspace_id, role)
    ctx = build_workspace_core_context(
        request,
        workspace_id=workspace_id,
        user=user,
        store=store,
        require_editor=apply_to_graph,
    )
    payload = await asyncio.to_thread(op_run_reasoning, ctx, raw)
    data = http_response_from_payload(payload)
    return ReasoningRunResponse.model_validate(data)
