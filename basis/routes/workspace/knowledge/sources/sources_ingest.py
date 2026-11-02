"""Workspace ingest source sync and webhook ingestion."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Request

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_workspace_for_editor, get_knowledge_store, get_store
from basis.services.knowledge.services.graph_audit import audit_graph
from basis.services.knowledge.services.ingest_source_service import (
    enqueue_text_from_source,
    execute_ingest_source_sync,
    record_ingest_source_event,
)
from basis.services.knowledge.store import KnowledgeStore
from basis.routes.workspace.knowledge.sources.sources_models import (
    SyncIngestSourceRequest,
    WebhookIngestRequest,
)
from basis.routes.workspace.knowledge.sources.sources_support import (
    bearer_token,
    doc_id_from_external_key,
    now_iso,
)

router = APIRouter(tags=["workspaces"])

@router.post("/{workspace_id}/sources/{source_id}/sync")
async def sync_ingest_source(
    workspace_id: str,
    source_id: str,
    request: Request,
    body: SyncIngestSourceRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Sync Ingest Source. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    result = execute_ingest_source_sync(
        request.app,
        knowledge,
        workspace_id,
        source_id,
        auto_process=body.auto_process,
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.ingest_source.sync",
        extra={"source_id": source_id, "doc_id": result.get("doc_id")},
    )
    return {"source_id": source_id, "result": result}


@router.post("/{workspace_id}/sources/{source_id}/webhook")
async def ingest_via_webhook(
    workspace_id: str,
    source_id: str,
    body: WebhookIngestRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Ingest Via Webhook. Ingest sources (HTTP poll, webhook, manual sync). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    token = bearer_token(authorization)
    expected = knowledge.get_ingest_source_secret(workspace_id, source_id)
    if not expected or not token or token != expected:
        raise AdminError(401, "unauthorized", "Webhook 令牌无效")

    source = knowledge.get_ingest_source(workspace_id, source_id)
    if source["kind"] != "webhook" or not source["enabled"]:
        raise AdminError(403, "forbidden", "来源未启用")

    title = (body.title or "Webhook ingest").strip() or "Webhook ingest"
    doc_id = doc_id_from_external_key(body.external_key, title)
    at = now_iso()
    try:
        result = enqueue_text_from_source(
            request.app,
            knowledge,
            workspace_id,
            source_id,
            title=title,
            text=body.text,
            doc_id=doc_id,
            auto_process=body.auto_process,
        )
    except Exception as exc:
        record_ingest_source_event(
            knowledge,
            workspace_id,
            source_id,
            {"at": at, "status": "failed", "mode": "webhook", "error": str(exc)[:500]},
        )
        raise

    record_ingest_source_event(
        knowledge,
        workspace_id,
        source_id,
        {
            "at": at,
            "status": "succeeded",
            "mode": "webhook",
            "doc_id": result.get("doc_id"),
            "job_id": result.get("job_id"),
        },
    )
    return result
