"""Workspace graph mutation routes (archive node, …)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.application.semantica_compat.operations import op_delete_node
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.http.shared.deps import get_current_user, get_store, get_workspace_for_editor
from basis.interface.http.shared.operation_http import http_response_from_payload

router = APIRouter(tags=["workspaces"])


@router.delete("/{workspace_id}/graph/nodes/{node_id}")
async def archive_graph_node(
    workspace_id: str,
    node_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Archive Graph Node. Soft-delete (status=archived) on the projected graph session. Editor only.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    ctx = build_workspace_core_context(
        request,
        workspace_id=workspace_id,
        user=user,
        store=store,
        require_editor=True,
    )
    payload = await asyncio.to_thread(op_delete_node, ctx, {"node_id": node_id})
    return http_response_from_payload(payload)
