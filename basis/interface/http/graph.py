"""Workspace projected graph read API and chunk search — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.interface.http.workspace.graph.graph_models import (
    GraphSearchRequest,
    ResolveNodeLabelsRequest,
    SearchConfigRequest,
    SearchReindexRequest,
)
from basis.interface.http.workspace.graph.graph_mutations import router as mutations_router
from basis.interface.http.workspace.graph.graph_read import router as read_router
from basis.interface.http.workspace.graph.graph_search import router as search_router

router = APIRouter(tags=["workspaces"])
router.include_router(read_router)
router.include_router(search_router)
router.include_router(mutations_router)

__all__ = [
    "GraphSearchRequest",
    "ResolveNodeLabelsRequest",
    "SearchConfigRequest",
    "SearchReindexRequest",
    "router",
]
