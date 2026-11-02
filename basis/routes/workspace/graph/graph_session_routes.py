"""Workspace graph session query surface — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.graph.graph_decisions import router as decisions_router
from basis.routes.workspace.graph.graph_io import router as graph_io_router
from basis.routes.workspace.graph.graph_reasoning import router as reasoning_router
from basis.routes.workspace.graph.graph_semantic import router as semantic_router
from basis.routes.workspace.graph.graph_sparql import router as sparql_router

router = APIRouter(tags=["workspaces"])
router.include_router(sparql_router)
router.include_router(semantic_router)
router.include_router(decisions_router)
router.include_router(reasoning_router)
router.include_router(graph_io_router)

__all__ = ["router"]
