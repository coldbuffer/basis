"""Workspace ontology registry and alignment routes."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from basis.application.ontology import operations as ontology_ops
from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_store,
)
from basis.domain.ontology.hub.scoped_state import OntologyHubState
from basis.interface.http.workspace.ontology.ontology_application_http import run_ontology_operation
from basis.interface.http.workspace.ontology.ontology_session import graph_session

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
    get_workspace_for_viewer(request, user, workspace_id, store)

    with OntologyHubState(request, workspace_id):
        align_store = request.app.state.ontology_alignments[workspace_id]
        alignments = list(align_store.values())
        if uri:
            alignments = [
                item
                for item in alignments
                if str(item.get("source_uri", "")).startswith(uri)
                or str(item.get("target_uri", "")).startswith(uri)
            ]
        return sorted(
            alignments,
            key=lambda item: (
                item.get("source_label", ""),
                item.get("target_label", ""),
                item.get("relation", ""),
            ),
        )


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
    get_workspace_for_editor(request, user, workspace_id, store)
    from basis.domain.ontology.hub.catalog import upsert_alignment

    raw = await request.json()
    if not isinstance(raw, dict):
        raise AdminError(422, "validation_error", "请求体须为 JSON 对象")
    session = graph_session(request, workspace_id)
    with OntologyHubState(request, workspace_id):
        align_store = request.app.state.ontology_alignments[workspace_id]
        return await asyncio.to_thread(
            upsert_alignment,
            align_store,
            session,
            source_uri=str(raw.get("source_uri", "")),
            target_uri=str(raw.get("target_uri", "")),
            relation=str(raw.get("relation", "")),
            source_label=raw.get("source_label"),
            target_label=raw.get("target_label"),
            confidence=float(raw.get("confidence", 1.0)),
            provenance=raw.get("provenance"),
            source=raw.get("source"),
            reviewer=raw.get("reviewer"),
        )


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
    get_workspace_for_editor(request, user, workspace_id, store)
    from basis.domain.ontology.hub.catalog import delete_alignment

    with OntologyHubState(request, workspace_id):
        align_store = request.app.state.ontology_alignments[workspace_id]
        return await asyncio.to_thread(delete_alignment, align_store, id)


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
    get_workspace_for_viewer(request, user, workspace_id, store)
    from basis.domain.ontology.hub.catalog import suggest_alignments

    raw = await request.json()
    if not isinstance(raw, dict):
        raise AdminError(422, "validation_error", "请求体须为 JSON 对象")
    session = graph_session(request, workspace_id)
    return await asyncio.to_thread(
        suggest_alignments,
        session,
        source_ontology_uri=raw.get("source_ontology_uri"),
        target_ontology_uri=raw.get("target_ontology_uri"),
        threshold=float(raw.get("threshold", 0.65)),
        limit=int(raw.get("limit", 25)),
    )
