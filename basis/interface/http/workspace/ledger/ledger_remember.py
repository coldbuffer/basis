"""Remember proposal route (integration core)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import get_current_user, get_store
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.application.knowledge.operations import op_propose_remember
from basis.interface.http.shared.operation_http import http_response_from_payload
from basis.interface.http.workspace.ledger.ledger_models import RememberProposalRequest

router = APIRouter(tags=["workspaces"])

@router.post(
    "/{workspace_id}/remember/proposals",
)
async def create_remember_proposal(
    workspace_id: str,
    body: RememberProposalRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Propose a canonical fact for human review (integration core `propose_remember`)."""
    ctx = build_workspace_core_context(
        request,
        workspace_id=workspace_id,
        user=user,
        store=store,
        require_editor=True,
    )
    args: dict[str, Any] = {"content": body.content, "source": "api"}
    if body.chunk_id is not None:
        args["chunk_id"] = body.chunk_id
    if body.quote is not None:
        args["quote"] = body.quote
    payload = await asyncio.to_thread(op_propose_remember, ctx, args)
    return http_response_from_payload(payload)
