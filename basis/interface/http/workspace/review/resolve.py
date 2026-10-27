"""Workspace review approve / reject — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.interface.http.workspace.review.review_resolve_approve import router as approve_router
from basis.interface.http.workspace.review.review_resolve_reject import router as reject_router

router = APIRouter(tags=["workspaces"])
router.include_router(approve_router)
router.include_router(reject_router)

__all__ = ["router"]
