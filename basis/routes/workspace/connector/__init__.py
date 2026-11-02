"""Workspace Basis Open Connector Protocol (BOCP) routes — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.connector.catalog import router as catalog_router
from basis.routes.workspace.connector.connections import router as connections_router
from basis.routes.workspace.connector.embed import router as connectors_embed_router
from basis.routes.workspace.connector.mappings import router as mappings_router
from basis.routes.workspace.connector.oauth import router as oauth_router
from basis.routes.workspace.connector.outbox import router as outbox_router
from basis.routes.workspace.connector.tools import router as tools_router

router = APIRouter(tags=["workspaces"])
router.include_router(catalog_router)
router.include_router(connectors_embed_router)
router.include_router(connections_router)
router.include_router(mappings_router)
router.include_router(outbox_router)
router.include_router(oauth_router)
router.include_router(tools_router)

__all__ = ["router"]
