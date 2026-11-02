"""Workspace graph mutation audit listing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_workspace_for_viewer, get_store

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/audit/graph-mutations")
async def list_graph_audit(
    workspace_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    action_prefix: str = Query("workspace.graph."),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List Graph Audit. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    prefix = action_prefix.strip() or "workspace.graph."
    events = store.list_audit_for_workspace(workspace_id, action_prefix=prefix, limit=limit)
    return {"events": events}
