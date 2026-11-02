"""Workspace core HTTP aggregator (tokens, realtime, MCP, config)."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.workspace.core.config_alerts import router as alerts_router
from basis.routes.workspace.core.config_governance import router as governance_router
from basis.routes.workspace.core.config_mappings import router as mappings_router
from basis.routes.workspace.core.config_reasoning_rules import (
    router as reasoning_rules_router,
)
from basis.routes.workspace.core.mcp_http import router as mcp_router
from basis.routes.workspace.core.realtime import router as realtime_router
from basis.routes.workspace.core.tokens import router as tokens_router

router = APIRouter()
router.include_router(tokens_router)
router.include_router(mcp_router)
router.include_router(realtime_router)
router.include_router(mappings_router)
router.include_router(reasoning_rules_router)
router.include_router(alerts_router)
router.include_router(governance_router)
