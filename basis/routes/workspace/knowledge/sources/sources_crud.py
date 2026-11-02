"""Workspace ingest source CRUD and admin routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_store,
)
from basis.services.knowledge.services.graph_audit import audit_graph
from basis.services.knowledge.store import KnowledgeStore
from basis.routes.workspace.knowledge.sources.sources_models import (
    CreateIngestSourceRequest,
    UpdateIngestSourceRequest,
)
from basis.routes.workspace.knowledge.sources.sources_support import webhook_path

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/sources")
async def list_ingest_sources(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
List Ingest Sources. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    sources = knowledge.list_ingest_sources(workspace_id)
    for source in sources:
        if source["kind"] == "webhook":
            source["webhook_path"] = webhook_path(workspace_id, source["id"])
    return {"sources": sources}


@router.post("/{workspace_id}/sources")
async def create_ingest_source(
    workspace_id: str,
    request: Request,
    body: CreateIngestSourceRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Create Ingest Source. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    source, token = knowledge.create_ingest_source(
        workspace_id,
        user.id,
        kind=body.kind,
        name=body.name,
        config=body.config,
        enabled=body.enabled,
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ingest_source.created",
        extra={"source_id": source["id"], "kind": source["kind"]},
    )
    payload: dict[str, Any] = {"source": source}
    if token:
        payload["ingest_token"] = token
        payload["webhook_path"] = webhook_path(workspace_id, source["id"])
    return payload


@router.get("/{workspace_id}/sources/{source_id}")
async def get_ingest_source(
    workspace_id: str,
    request: Request,
    source_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Get Ingest Source. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    source = knowledge.get_ingest_source(workspace_id, source_id)
    if source["kind"] == "webhook":
        source["webhook_path"] = webhook_path(workspace_id, source_id)
    return {"source": source}


@router.patch("/{workspace_id}/sources/{source_id}")
async def update_ingest_source(
    workspace_id: str,
    request: Request,
    source_id: str,
    body: UpdateIngestSourceRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Update Ingest Source. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    if body.config is not None:
        source = knowledge.get_ingest_source(workspace_id, source_id)
        if source["kind"] == "http_poll":
            url = str(body.config.get("url") or source["config"].get("url") or "").strip()
            if url and not url.startswith(("http://", "https://")):
                raise AdminError(422, "bad_url", "http_poll 需要有效的 http(s) URL")
    source = knowledge.update_ingest_source(
        workspace_id,
        source_id,
        name=body.name,
        enabled=body.enabled,
        config=body.config,
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ingest_source.updated",
        extra={"source_id": source_id},
    )
    return {"source": source}


@router.delete("/{workspace_id}/sources/{source_id}")
async def delete_ingest_source(
    workspace_id: str,
    request: Request,
    source_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Delete Ingest Source. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    knowledge.delete_ingest_source(workspace_id, source_id)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ingest_source.deleted",
        extra={"source_id": source_id},
    )
    return {"status": "deleted"}


@router.post("/{workspace_id}/sources/{source_id}/rotate-token")
async def rotate_ingest_source_token(
    workspace_id: str,
    request: Request,
    source_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Rotate Ingest Source Token. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    token = knowledge.rotate_ingest_source_token(workspace_id, source_id)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ingest_source.token_rotated",
        extra={"source_id": source_id},
    )
    return {
        "ingest_token": token,
        "webhook_path": webhook_path(workspace_id, source_id),
    }


@router.get("/{workspace_id}/sources/{source_id}/sync-history")
async def list_ingest_source_sync_history(
    workspace_id: str,
    source_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Recent sync runs stored on the source config (`sync_events`, newest first)."""
    get_workspace_for_viewer(request, user, workspace_id, store)
    source = knowledge.get_ingest_source(workspace_id, source_id)
    events = list(source.get("config", {}).get("sync_events") or [])
    capped = min(max(1, limit), 200)
    return {
        "source_id": source_id,
        "events": events[:capped],
        "last_sync_at": source.get("config", {}).get("last_sync_at"),
        "last_sync_status": source.get("config", {}).get("last_sync_status"),
    }
