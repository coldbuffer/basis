"""Workspace ingest source connectors — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.interface.http.workspace.sources.sources_crud import router as crud_router
from basis.interface.http.workspace.sources.sources_ingest import router as ingest_router
from basis.interface.http.workspace.sources.sources_models import (
    CreateIngestSourceRequest,
    SyncIngestSourceRequest,
    UpdateIngestSourceRequest,
    WebhookIngestRequest,
)

router = APIRouter(tags=["workspaces"])
router.include_router(crud_router)
router.include_router(ingest_router)

__all__ = [
    "CreateIngestSourceRequest",
    "SyncIngestSourceRequest",
    "UpdateIngestSourceRequest",
    "WebhookIngestRequest",
    "router",
]
