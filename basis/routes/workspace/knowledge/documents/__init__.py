"""Workspace documents, processing jobs, and legacy ontology create — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.knowledge.documents.documents_crud import router as crud_router
from basis.routes.workspace.knowledge.documents.documents_jobs import (
    router as jobs_router,
    start_processing_job,
)
from basis.routes.workspace.knowledge.documents.documents_models import (
    AppendTextVersionRequest,
    CreateOntologyRequest,
    IngestTextRequest,
    RetryProcessingRequest,
    StartProcessingRequest,
)
from basis.routes.workspace.knowledge.documents.documents_ontology import router as ontology_router

router = APIRouter(tags=["workspaces"])
router.include_router(crud_router)
router.include_router(jobs_router)
router.include_router(ontology_router)

__all__ = [
    "AppendTextVersionRequest",
    "CreateOntologyRequest",
    "IngestTextRequest",
    "RetryProcessingRequest",
    "StartProcessingRequest",
    "router",
    "start_processing_job",
]
