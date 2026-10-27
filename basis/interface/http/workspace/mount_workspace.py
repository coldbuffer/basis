"""Workspace routers mounted under ``{api_root}/workspaces``."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from basis.interface.http.workspace.connectors import router as connectors_router
from basis.interface.http.workspace.documents import router as documents_router
from basis.interface.http.workspace.graph import router as graph_router
from basis.interface.http.workspace.ledger import router as ledger_router
from basis.interface.http.workspace.ontology import router as ontology_router
from basis.interface.http.workspace.resources import router as resources_router
from basis.interface.http.workspace.review import router as review_router
from basis.interface.http.workspace.sources import router as sources_router
from basis.interface.http.workspace.tokens import router as tokens_router
from basis.interface.http.workspace.config.config_alerts import router as alerts_router
from basis.interface.http.workspace.config.config_governance import router as governance_router
from basis.interface.http.workspace.config.config_mappings import router as mappings_router
from basis.interface.http.workspace.config.config_reasoning_rules import (
    router as reasoning_rules_router,
)
from basis.interface.http.workspace.e2e_helpers import router as e2e_helpers_router
from basis.interface.http.workspace.graph.graph_enrich import router as graph_enrich_router
from basis.interface.http.workspace.graph.graph_session_routes import (
    router as graph_session_query_router,
)
from basis.interface.http.workspace.graph.graph_staging import router as graph_staging_router
from basis.interface.http.workspace.graph.graph_temporal import router as graph_temporal_router
from basis.interface.http.workspace.mcp.mcp_http import router as mcp_router
from basis.interface.http.workspace.realtime.realtime import router as realtime_router

_WORKSPACE_ROUTERS: tuple[APIRouter, ...] = (
    resources_router,
    graph_router,
    documents_router,
    mcp_router,
    tokens_router,
    graph_temporal_router,
    graph_staging_router,
    graph_enrich_router,
    graph_session_query_router,
    ontology_router,
    review_router,
    ledger_router,
    mappings_router,
    reasoning_rules_router,
    alerts_router,
    sources_router,
    connectors_router,
    governance_router,
    realtime_router,
)


def mount_workspace_routers(app: FastAPI, workspaces_prefix: str) -> None:
    for router in _WORKSPACE_ROUTERS:
        app.include_router(router, prefix=workspaces_prefix)


def mount_workspace_e2e_helpers(app: FastAPI, workspaces_prefix: str) -> None:
    app.include_router(e2e_helpers_router, prefix=workspaces_prefix)
