"""Workspace-scoped vocabulary and ontology-hub — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.interface.http.workspace.ontology.ontology_alignments import router as alignments_router
from basis.interface.http.workspace.ontology.ontology_hub import register_ontology_hub_routes
from basis.interface.http.workspace.ontology.ontology_vocabulary import router as vocabulary_router

router = APIRouter(tags=["workspaces"])
router.include_router(vocabulary_router)
router.include_router(alignments_router)
register_ontology_hub_routes(router)

__all__ = ["router"]
