"""Workspace Basis Open Connector Protocol (BOCP) routes — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.interface.http.workspace.connectors.catalog import router as catalog_router
from basis.interface.http.workspace.connectors.connections import router as connections_router
from basis.interface.http.workspace.connectors.embed import router as connectors_embed_router
from basis.interface.http.workspace.connectors.mappings import router as mappings_router
from basis.interface.http.workspace.connectors.oauth import router as oauth_router
from basis.interface.http.workspace.connectors.outbox import router as outbox_router
from basis.interface.http.workspace.connectors.tools import router as tools_router

router = APIRouter(tags=["workspaces"])
router.include_router(catalog_router)
router.include_router(connectors_embed_router)
router.include_router(connections_router)
router.include_router(mappings_router)
router.include_router(outbox_router)
router.include_router(oauth_router)
router.include_router(tools_router)

__all__ = ["router"]
