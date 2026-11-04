"""Workspace knowledge HTTP aggregator (ledger, documents, sources)."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.knowledge.documents import router as documents_router
from basis.routes.workspace.knowledge.ledger import router as ledger_router
from basis.routes.workspace.knowledge.sources import router as sources_router
from basis.routes.workspace.knowledge.sql_catalog import router as sql_catalog_router

router = APIRouter()
router.include_router(documents_router)
router.include_router(ledger_router)
router.include_router(sources_router)
router.include_router(sql_catalog_router)
