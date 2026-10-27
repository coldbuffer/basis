"""Workspace review queue — aggregates sub-routers (Gate D)."""

from __future__ import annotations

from fastapi import APIRouter

from basis.interface.http.workspace.review.review_audit import router as audit_router
from basis.interface.http.workspace.review.review_queue import (
    CreateEntityMergeReviewRequest,
    propose_entity_merge,
    router as queue_router,
)
from basis.interface.http.workspace.review.resolve import router as resolve_router

router = APIRouter(tags=["workspaces"])
router.include_router(queue_router)
router.include_router(resolve_router)
router.include_router(audit_router)

__all__ = ["CreateEntityMergeReviewRequest", "propose_entity_merge", "router"]
