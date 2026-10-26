"""Workspace ledger entity delete and merge revert."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from basis.application.knowledge.operations import op_invalidate_entities
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.http.shared.deps import (
    get_current_user,
    get_workspace_for_editor,
    get_knowledge_store,
    get_store,
    rebuild_graph_projection,
)
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.domain.knowledge.store import KnowledgeStore

router = APIRouter(tags=["workspaces"])


class InvalidateEntitiesRequest(BaseModel):
    entity_ids: list[str] = Field(min_length=1, max_length=200)


@router.post("/{workspace_id}/ledger/entities/invalidate")
async def invalidate_ledger_entities(
    workspace_id: str,
    body: InvalidateEntitiesRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Invalidate Ledger Entities. Soft-delete entities and related ledger rows (temporal invalidated_at). Editor only.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_invalidate_entities, ctx, body.model_dump())


@router.delete("/{workspace_id}/ledger/entities/{entity_id}")
async def delete_ledger_entity(
    workspace_id: str,
    entity_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Delete Ledger Entity. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    outcome = knowledge.delete_entity(workspace_id, entity_id)
    projection = await asyncio.to_thread(rebuild_graph_projection, request, workspace_id)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ledger.entity_delete",
        extra={
            "entity_id": outcome["entity_id"],
            "canonical_label": outcome["canonical_label"],
            "statements_removed": outcome["statements_removed"],
            "projection": projection,
        },
    )
    return {"ok": True, **outcome, "projection": projection}

@router.post("/{workspace_id}/ledger/entity-merges/{merge_id}/revert")
async def revert_entity_merge_route(
    workspace_id: str,
    merge_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Revert Entity Merge Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    merged = knowledge.revert_entity_merge(workspace_id, merge_id, reverted_by=user.id)
    projection = rebuild_graph_projection(request, workspace_id)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ledger.entity_merge_revert",
        extra={"merge_id": merge_id, "merge": merged, "projection": projection},
    )
    return {"merge": merged, "projection": projection}
