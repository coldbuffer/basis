"""Platform authentication: password session and federated login (OAuth, OIDC, SAML, magic link)."""

from __future__ import annotations

from fastapi import APIRouter

from basis.routes.admin.auth.auth_bootstrap import router as bootstrap_router
from basis.routes.admin.auth.auth_magic_link import router as magic_link_router
from basis.routes.admin.auth.auth_oidc import router as oidc_router
from basis.routes.admin.auth.auth_saml import router as saml_router
from basis.routes.admin.auth.auth_session import router as session_router
from basis.routes.admin.auth.auth_social import router as social_router

router = APIRouter(tags=["auth"])
router.include_router(session_router)
router.include_router(bootstrap_router)
router.include_router(social_router)
router.include_router(oidc_router)
router.include_router(saml_router)
router.include_router(magic_link_router)

__all__ = ["router"]
