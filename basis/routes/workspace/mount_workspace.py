"""Workspace routers mounted under ``{api_root}/workspaces``."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from basis.routes.workspace.core import router as core_router
from basis.routes.workspace.core.resources import router as resources_router
from basis.routes.workspace.e2e_helpers import router as e2e_helpers_router
from basis.routes.workspace.graph import router as graph_router
from basis.routes.workspace.graph.graph_enrich import router as graph_enrich_router
from basis.routes.workspace.graph.graph_session_routes import (
    router as graph_session_query_router,
)
from basis.routes.workspace.graph.graph_staging import router as graph_staging_router
from basis.routes.workspace.graph.graph_temporal import router as graph_temporal_router
from basis.routes.workspace.knowledge import router as knowledge_router
from basis.routes.workspace.ontology import router as ontology_router
from basis.routes.workspace.review import router as review_router

_WORKSPACE_ROUTERS: tuple[APIRouter, ...] = (
    resources_router,
    core_router,
    knowledge_router,
    graph_router,
    graph_temporal_router,
    graph_staging_router,
    graph_enrich_router,
    graph_session_query_router,
    ontology_router,
    review_router,
)


def mount_workspace_routers(app: FastAPI, workspaces_prefix: str) -> None:
    for router in _WORKSPACE_ROUTERS:
        app.include_router(router, prefix=workspaces_prefix)


def mount_workspace_e2e_helpers(app: FastAPI, workspaces_prefix: str) -> None:
    app.include_router(e2e_helpers_router, prefix=workspaces_prefix)
