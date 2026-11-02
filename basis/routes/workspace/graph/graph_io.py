"""Workspace graph graph import/export routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    graph_runtime_for,
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_store,
)
from basis.services.graph.session.guard import require_graph_session
from basis.services.knowledge.services.graph_audit import audit_graph

router = APIRouter(tags=["workspaces"])

@router.post("/{workspace_id}/import")
async def import_graph(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Import Graph. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    raise AdminError(
        409,
        "import_requires_review",
        "图导入请提交审核队列，并在批准后应用",
    )


@router.post("/{workspace_id}/export")
async def export_graph(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Response:
    """
Export Graph. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.services.graph.reads.export_read import export_graph

    raw = await request.json()
    fmt = raw.get("format", "json") if isinstance(raw, dict) else "json"
    node_ids = raw.get("node_ids") if isinstance(raw, dict) else None
    if node_ids is not None and not isinstance(node_ids, list):
        raise AdminError(422, "validation_error", "node_ids 须为字符串数组或省略")
    content, media_type, extension = await asyncio.to_thread(
        export_graph,
        session,
        format=str(fmt),
        node_ids=[str(n) for n in node_ids] if isinstance(node_ids, list) else None,
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.graph.export",
        extra={"format": str(fmt)},
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="semantica_export.{extension}"'},
    )
