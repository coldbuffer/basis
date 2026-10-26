"""Workspace evidence ledger read routes."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.domain.errors import AdminError
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_store,
)
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.application.knowledge.operations import (
    op_entity_facts,
    op_get_chunk,
    op_get_statement,
    op_list_derived_facts,
    op_list_entity_type_object_labels,
    op_list_surface_phrases,
    op_list_typed_facts,
)
from basis.interface.http.shared.operation_http import http_response_from_payload
from basis.domain.knowledge.store import KnowledgeStore

router = APIRouter(tags=["workspaces"])

@router.get("/{workspace_id}/ledger/surface-phrases")
async def list_surface_phrases(
    workspace_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List Surface Phrases. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_list_surface_phrases, ctx, {"limit": limit})


@router.get("/{workspace_id}/ledger/entity-type-object-labels")
async def list_entity_type_object_labels(
    workspace_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List object labels from type assertions (e.g. 是 / instance_of) for entity-class mappings.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    return await asyncio.to_thread(op_list_entity_type_object_labels, ctx, {"limit": limit})


@router.get(
    "/{workspace_id}/ledger/derived-facts",
)
async def list_derived_facts_route(
    workspace_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    entity_id: str | None = Query(None, max_length=128),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List Derived Facts Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    args: dict[str, Any] = {"limit": limit}
    if entity_id and entity_id.strip():
        args["entity_id"] = entity_id.strip()
    payload = await asyncio.to_thread(op_list_derived_facts, ctx, args)
    data = http_response_from_payload(payload)
    return {"derived_facts": data.get("derived_facts") or []}


@router.get("/{workspace_id}/ledger/entities")
async def search_ledger_entities(
    workspace_id: str,
    request: Request,
    query: str = Query("", max_length=200),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Search Ledger Entities. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    q = query.strip()
    total = knowledge.count_browse_entities(workspace_id, query=q)
    if q:
        entities = knowledge.find_entities(workspace_id, query=q, limit=limit, offset=offset)
    else:
        entities = knowledge.list_recent_entities(workspace_id, limit=limit, offset=offset)
    return {"entities": entities, "total": total, "limit": limit, "offset": offset}


@router.get("/{workspace_id}/ledger/documents/{doc_ref}")
async def get_ledger_document_route(
    workspace_id: str,
    request: Request,
    doc_ref: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Get Ledger Document Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    summary = knowledge.get_document_summary(workspace_id, doc_ref)
    if summary is None:
        raise AdminError(404, "document_not_found", "文档不存在")
    return {"document": summary}


@router.get("/{workspace_id}/ledger/documents/{doc_ref}/chunks")
async def list_document_chunks_route(
    workspace_id: str,
    request: Request,
    doc_ref: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
List Document Chunks Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    doc = knowledge.resolve_document_ref(workspace_id, doc_ref)
    if doc is None:
        raise AdminError(404, "document_not_found", "文档不存在")
    version_id = doc.get("version_id")
    if not version_id:
        return {
            "doc_ref": doc_ref,
            "document_id": doc["document_id"],
            "external_key": doc.get("external_key"),
            "chunks": [],
        }
    chunks = knowledge.list_chunks_for_version(workspace_id, version_id)
    return {
        "doc_ref": doc_ref,
        "document_id": doc["document_id"],
        "external_key": doc.get("external_key"),
        "version_id": version_id,
        "chunks": chunks,
    }


@router.get(
    "/{workspace_id}/ledger/chunks/{chunk_id}",
)
async def get_ledger_chunk_route(
    workspace_id: str,
    request: Request,
    chunk_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Get Ledger Chunk Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(op_get_chunk, ctx, {"chunk_id": chunk_id})
    data = http_response_from_payload(payload)
    statements = knowledge.list_statements_for_chunk(workspace_id, chunk_id)
    return {"chunk": data["chunk"], "statements": statements}


@router.get(
    "/{workspace_id}/ledger/statements/{statement_id}",
)
async def get_ledger_statement_route(
    workspace_id: str,
    request: Request,
    statement_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Get Ledger Statement. Resolve a statement id to its subject entity for console deep links (F-RUL-03). Requires workspace membership (session) or workspace API token with read scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_get_statement, ctx, {"statement_id": statement_id}
    )
    return http_response_from_payload(payload)


@router.get(
    "/{workspace_id}/ledger/entities/{entity_id}/facts",
)
async def list_entity_facts_route(
    workspace_id: str,
    request: Request,
    entity_id: str,
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
List Entity Facts Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_entity_facts,
        ctx,
        {"entity_id": entity_id, "limit": limit},
    )
    data = http_response_from_payload(payload)
    sync_svc = knowledge.connector_sync_service()
    external_sync = sync_svc.get_entity_external_sync_context(workspace_id, entity_id)
    return {**data, "external_sync": external_sync}


@router.get("/{workspace_id}/ledger/entities/{entity_id}/delete-preview")
async def preview_delete_ledger_entity(
    workspace_id: str,
    entity_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
Preview Delete Ledger Entity. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    return knowledge.preview_entity_deletion(workspace_id, entity_id)


@router.get(
    "/{workspace_id}/ledger/typed-facts",
)
async def list_typed_facts_route(
    workspace_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
List Typed Facts Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(op_list_typed_facts, ctx, {"limit": limit})
    return http_response_from_payload(payload)


@router.get("/{workspace_id}/ledger/entity-merges")
async def list_entity_merges_route(
    workspace_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=200),
    active_only: bool = Query(True),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """
List Entity Merges Route. Evidence ledger: documents, chunks, statements, entities. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    merges = knowledge.list_entity_merges(workspace_id, limit=limit, active_only=active_only)
    return {"merges": merges}

