"""Workspace review queue list and proposal routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_blob_store,
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_runtime_limits,
    get_store,
)
from basis.infra.runtime.limits import RuntimeLimits
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.domain.knowledge.services.conflict_review import run_shacl_conflict_scan
from basis.interface.http.workspace.review.conflict_scan_http import build_conflict_scan_context
from basis.domain.knowledge.services.import_review import stage_import_blob
from basis.domain.knowledge.store import KnowledgeStore
from basis.interface.http.shared.operation_http import http_response_from_payload
from basis.application.review.operations import op_get_review_item, op_list_review_items
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.http.workspace.review.review_models import CreateEntityMergeReviewRequest

router = APIRouter(tags=["workspaces"])

@router.post("/{workspace_id}/review/scan-shacl-violations")
async def scan_shacl_violations_route(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Materialize mappings and enqueue SHACL violation review items (F-RUL-04)."""
    get_workspace_for_editor(request, user, workspace_id, store)
    scan_ctx = build_conflict_scan_context(request, workspace_id, knowledge)
    return run_shacl_conflict_scan(knowledge, workspace_id, scan_ctx=scan_ctx)


@router.get(
    "/{workspace_id}/review/items",
)
async def list_review_items(
    workspace_id: str,
    request: Request,
    status: str | None = Query("open"),
    kind: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
List Review Items. Human review queue for merges, imports, and conflicts. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    args: dict[str, Any] = {"limit": limit, "offset": offset}
    if status is not None:
        args["status"] = status
    if kind is not None:
        args["kind"] = kind
    payload = await asyncio.to_thread(op_list_review_items, ctx, args)
    return http_response_from_payload(payload)


@router.get(
    "/{workspace_id}/review/items/{item_id}",
)
async def get_review_item_route(
    workspace_id: str,
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Get Review Item. Human review queue for merges, imports, and conflicts. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(op_get_review_item, ctx, {"item_id": item_id})
    return http_response_from_payload(payload)


@router.post("/{workspace_id}/review/items/entity-merge")
async def propose_entity_merge(
    workspace_id: str,
    request: Request,
    body: CreateEntityMergeReviewRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Propose Entity Merge. Human review queue for merges, imports, and conflicts. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    subject_id = KnowledgeStore.merge_review_subject_key(body.primary_id, body.duplicate_ids)
    item = knowledge.create_review_item(
        workspace_id,
        kind="entity_merge",
        subject_type="graph_nodes",
        subject_id=subject_id,
        payload={
            "primary_id": body.primary_id,
            "duplicate_ids": body.duplicate_ids,
        },
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.graph.merge_proposed",
        review_item_id=item["id"],
        extra={
            "primary_id": body.primary_id,
            "duplicate_ids": body.duplicate_ids,
        },
    )
    return {"item": item}


@router.post("/{workspace_id}/review/items/graph-import")
async def propose_graph_import(
    workspace_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
    blob_store=Depends(get_blob_store),  # noqa: B008
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> dict[str, Any]:
    """
Propose Graph Import. Human review queue for merges, imports, and conflicts. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    raw = await file.read()
    staged = stage_import_blob(
        blob_store,
        workspace_id,
        raw,
        file.filename or "import.json",
        max_bytes=limits.import_max_bytes,
    )
    subject_id = f"import:{staged['sha256']}"
    item = knowledge.create_review_item(
        workspace_id,
        kind="graph_import",
        subject_type="import_blob",
        subject_id=subject_id,
        payload=staged,
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.graph.import_proposed",
        review_item_id=item["id"],
        extra=staged,
    )
    return {"item": item}

