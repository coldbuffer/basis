"""Workspace chunk search, entity find, and search config routes."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import (
    get_chunk_search,
    get_current_user,
    get_workspace_for_editor,
    get_workspace_for_viewer,
    get_knowledge_store,
    get_runtime_limits,
    get_store,
)
from basis.http.core_context import build_workspace_core_context
from basis.services.graph.operations import op_find_entities
from basis.services.knowledge.operations import op_search_chunks
from basis.http.operation_http import http_response_from_payload
from basis.services.knowledge.search import ChunkSearchService
from basis.infra.runtime.limits import RuntimeLimits
from basis.services.knowledge.store import KnowledgeStore
from basis.routes.workspace.graph.graph_models import (
    SearchConfigRequest,
    SearchReindexRequest,
)

router = APIRouter(tags=["workspaces"])


@router.get(
    "/{workspace_id}/search",
)
async def chunk_search_route(
    workspace_id: str,
    q: str,
    request: Request,
    limit: int = 20,
    document_id: str | None = None,
    entity_id: str | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    as_of: str | None = Query(
        None,
        description="Point-in-time (ISO): alias for created_before when that param is omitted.",
    ),
    mode: Literal["keyword", "semantic", "hybrid"] | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    chunk_search: ChunkSearchService = Depends(get_chunk_search),
    limits: RuntimeLimits = Depends(get_runtime_limits),
) -> dict[str, Any]:
    """
Chunk Search Route. Chunk retrieval (keyword, semantic, or hybrid per workspace config). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    capped_limit = min(max(1, limit), limits.chunk_search_max_limit)
    knowledge = get_knowledge_store(request)
    resolved_document_id = document_id
    if document_id:
        doc = knowledge.resolve_document_ref(workspace_id, document_id)
        if doc is not None:
            resolved_document_id = doc["document_id"]
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_search_chunks,
        ctx,
        {
            "query": q,
            "limit": capped_limit,
            "limit_max": limits.chunk_search_max_limit,
            "document_id": resolved_document_id,
            "entity_id": entity_id,
            "created_after": created_after,
            "created_before": created_before,
            "as_of": as_of,
            "mode": mode,
        },
    )
    return http_response_from_payload(payload)


@router.get("/{workspace_id}/search/config")
async def get_chunk_search_config_route(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
    chunk_search: ChunkSearchService = Depends(get_chunk_search),
) -> dict[str, Any]:
    """
Get Chunk Search Config Route. Chunk retrieval (keyword, semantic, or hybrid per workspace config). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    config = knowledge.get_search_config(workspace_id)
    postgres = knowledge.database.backend == "postgres"
    return {
        "config": config.public_dict(),
        "status": chunk_search.status(workspace_id),
        "available": {
            "chunk_backends": ["postgres_ledger"] if postgres else ["sqlite_ledger"],
            "vector_backends": (
                ["pgvector", "sqlite_vec"] if postgres else ["sqlite_vec"]
            ),
            "search_modes": ["keyword", "semantic", "hybrid"],
            "embedding_models": store.list_configured_models("embed"),
        },
    }


@router.put("/{workspace_id}/search/config")
async def update_chunk_search_config_route(
    workspace_id: str,
    body: SearchConfigRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
    chunk_search: ChunkSearchService = Depends(get_chunk_search),
) -> dict[str, Any]:
    """
Update Chunk Search Config Route. Chunk retrieval (keyword, semantic, or hybrid per workspace config). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    store.get_workspace_for(user, workspace_id, "admin")
    if body.embedding_model_id:
        store.get_embed_settings(body.embedding_model_id)
    previous = knowledge.get_search_config(workspace_id)
    config = knowledge.update_search_config(
        workspace_id,
        chunk_backend=body.chunk_backend,
        vector_backend=body.vector_backend,
        embedding_model_id=body.embedding_model_id,
        keyword_enabled=body.keyword_enabled,
        semantic_enabled=body.semantic_enabled,
        default_mode=body.default_mode,
        auto_index=body.auto_index,
    )
    reindex_required = (
        previous.vector_backend != config.vector_backend
        or previous.embedding_model_id != config.embedding_model_id
    )
    return {
        "config": config.public_dict(),
        "status": chunk_search.status(workspace_id),
        "reindex_required": reindex_required,
    }


@router.post("/{workspace_id}/search/reindex")
async def chunk_search_reindex_route(
    workspace_id: str,
    request: Request,
    body: SearchReindexRequest | None = None,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    chunk_search: ChunkSearchService = Depends(get_chunk_search),
) -> dict[str, Any]:
    """
Chunk Search Reindex Route. Chunk retrieval (keyword, semantic, or hybrid per workspace config). Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    get_workspace_for_editor(request, user, workspace_id, store)
    body = body or SearchReindexRequest()

    def _reindex() -> dict[str, Any]:
        if body.version_id:
            return chunk_search.index_version(workspace_id, body.version_id)
        return chunk_search.reindex_workspace(workspace_id)

    return await asyncio.to_thread(_reindex)


@router.get(
    "/{workspace_id}/entities/find",
)
async def find_entities_route(
    workspace_id: str,
    request: Request,
    q: str,
    limit: int = 20,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Find Entities Route. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
    """
    ctx = build_workspace_core_context(request, workspace_id=workspace_id, user=user, store=store)
    payload = await asyncio.to_thread(
        op_find_entities,
        ctx,
        {"query": q, "limit": limit},
    )
    return http_response_from_payload(payload)
