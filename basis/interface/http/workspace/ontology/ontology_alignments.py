"""Workspace ontology registry and alignment routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from basis.application.ontology import operations as ontology_ops
from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_current_user,
    get_workspace_for_viewer,
    get_store,
)
from basis.interface.http.workspace.ontology.ontology_application_http import run_ontology_operation

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/ontology/registry")
async def ontology_registry(
    workspace_id: str,
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Ontology Registry. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    args: dict[str, Any] = {}
    if q:
        args["q"] = q
    if status:
        args["status"] = status
    if format:
        args["format"] = format
    payload = await run_ontology_operation(
        request,
        workspace_id,
        user,
        store,
        ontology_ops.op_list_ontology_registry,
        args,
        http_method="GET",
    )
    return payload.get("registry", [])


@router.get("/{workspace_id}/ontology/alignments/suggest-target-uri")
async def suggest_alignment_target_uri(
    workspace_id: str,
    request: Request,
    label: str,
    entity_type: str = "class",
    limit: int = 8,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Suggest Target Uri. Match a surface label to class/property URIs via vocabulary alignments (L1). Requires workspace viewer+.
    """
    payload = await run_ontology_operation(
        request,
        workspace_id,
        user,
        store,
        ontology_ops.op_suggest_alignment_target_uri,
        {"label": label, "entity_type": entity_type, "limit": limit},
        http_method="GET",
    )
    return {"suggestions": payload.get("suggestions", [])}


@router.get("/{workspace_id}/ontology/alignments")
async def list_alignments(
    workspace_id: str,
    request: Request,
    uri: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
List Alignments. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    args: dict[str, Any] = {}
    if uri:
        args["uri"] = uri
    payload = await run_ontology_operation(
        request,
        workspace_id,
        user,
        store,
        ontology_ops.op_list_vocabulary_alignments,
        args,
        http_method="GET",
    )
    return payload.get("alignments", [])


@router.post("/{workspace_id}/ontology/alignments")
async def upsert_alignment(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Upsert Alignment. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    raw = await request.json()
    if not isinstance(raw, dict):
        raise AdminError(422, "validation_error", "请求体须为 JSON 对象")
    payload = await run_ontology_operation(
        request,
        workspace_id,
        user,
        store,
        ontology_ops.op_upsert_vocabulary_alignment,
        raw,
        http_method="POST",
        require_editor=True,
    )
    alignment = payload.get("alignment")
    return alignment if alignment is not None else payload


@router.delete("/{workspace_id}/ontology/alignments")
async def delete_alignment(
    workspace_id: str,
    request: Request,
    id: str = Query(...),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Delete alignment. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    return await run_ontology_operation(
        request,
        workspace_id,
        user,
        store,
        ontology_ops.op_delete_vocabulary_alignment,
        {"alignment_id": id},
        http_method="DELETE",
        require_editor=True,
    )


@router.post("/{workspace_id}/ontology/suggest-alignments")
async def suggest_alignments(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> Any:
    """
Suggest Alignments. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    raw = await request.json()
    if not isinstance(raw, dict):
        raise AdminError(422, "validation_error", "请求体须为 JSON 对象")
    payload = await run_ontology_operation(
        request,
        workspace_id,
        user,
        store,
        ontology_ops.op_suggest_vocabulary_alignments,
        raw,
        http_method="POST",
    )
    return payload.get("suggestions", [])
