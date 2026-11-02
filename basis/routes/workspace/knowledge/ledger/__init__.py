"""Ledger helpers for workspace manage console — aggregates sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.knowledge.ledger.ledger_models import RememberProposalRequest
from basis.routes.workspace.knowledge.ledger.ledger_mutations import router as mutations_router
from basis.routes.workspace.knowledge.ledger.ledger_read import router as read_router
from basis.routes.workspace.knowledge.ledger.ledger_remember import router as remember_router

router = APIRouter(tags=["workspaces"])
router.include_router(remember_router)
router.include_router(read_router)
router.include_router(mutations_router)

__all__ = ["RememberProposalRequest", "router"]
