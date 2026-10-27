"""Workspace graph graph diff and staging studio routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_current_user,
    graph_runtime_for,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_store,
)
from basis.domain.graph.session.guard import require_graph_session
from basis.domain.knowledge.store import KnowledgeStore
from basis.interface.http.workspace.review import (
    CreateEntityMergeReviewRequest,
    propose_entity_merge,
)

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/graph/diff")
async def graph_diff(
    workspace_id: str,
    request: Request,
    from_time: str = Query(..., alias="from"),
    to_time: str = Query(..., alias="to"),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """Whole-graph diff between two instants (F-DIFF-01).

    Compares graph projection snapshots at `from` and `to` (ISO instants). Response includes
    `added_nodes`, `removed_nodes`, `modified_nodes`, `added_edges`, `removed_edges`, `summary`,
    and echo `from_time` / `to_time`. Node/edge membership follows ledger `recorded_at` → projected
    `valid_from` and `invalidated_at` → projected `valid_until` (F-TIM-01). Console graph preview dims unchanged elements and highlights
    added/modified nodes and added edges at the end instant.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.domain.graph.reads.diff import diff_session_at
    from basis.domain.graph.projection.projector import build_temporal_graph_from_ledger

    temporal_session = build_temporal_graph_from_ledger(
        get_knowledge_store(request), workspace_id, preserve_from=session
    )
    return diff_session_at(temporal_session, from_time, to_time)


@router.get("/{workspace_id}/graph/staging")
async def graph_staging(
    workspace_id: str,
    request: Request,
    from_time: str = Query(..., alias="from"),
    to_time: str = Query(..., alias="to"),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """Diff + staging manifest for publish/review workflows (F-DIFF-01).

    Returns `{manifest, diff}` where `manifest` includes `session_key` (stable id for the
    from/to range), `focus_node_ids`, governance relpaths (`review`, `graph/staging/entity-merge`,
    graph import), and `change_total`. The nested `diff` matches `GET .../graph/diff` for the
    same instants.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    runtime = graph_runtime_for(request, workspace_id)
    session = require_graph_session(runtime)
    from basis.domain.graph.projection.projector import build_temporal_graph_from_ledger

    knowledge = get_knowledge_store(request)
    temporal_session = build_temporal_graph_from_ledger(
        knowledge, workspace_id, preserve_from=session
    )
    return knowledge.graph_staging_at(
        temporal_session,
        workspace_id,
        from_time,
        to_time,
        updated_by=user.id,
    )


class PutGraphStagingDraftRequest(BaseModel):
    from_time: str = Field(default="")
    to_time: str = Field(default="")
    primary: str = Field(default="")
    duplicate: str = Field(default="")


@router.put("/{workspace_id}/graph/staging/{session_key}/draft")
async def put_graph_staging_draft(
    workspace_id: str,
    session_key: str,
    body: PutGraphStagingDraftRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Persist server-side staging studio merge draft for a compare session (F-DIFF-01)."""
    get_workspace_for_editor(request, user, workspace_id, store)
    return knowledge.upsert_graph_staging_session(
        workspace_id,
        session_key=session_key,
        from_time=body.from_time,
        to_time=body.to_time,
        draft={"primary": body.primary, "duplicate": body.duplicate},
        updated_by=user.id,
    )


@router.post("/{workspace_id}/graph/staging/entity-merge")
async def graph_staging_entity_merge(
    workspace_id: str,
    request: Request,
    body: CreateEntityMergeReviewRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> Any:
    """Propose entity merge from diff/staging studio (Gate D; F-DIFF-01).

    JSON body: `{primary_id, duplicate_ids[]}`. Creates a review-queue item (`entity_merge`);
    identical semantics to `POST .../review/items/entity-merge`.
    """
    return await propose_entity_merge(workspace_id, request, body, user, store, knowledge)

