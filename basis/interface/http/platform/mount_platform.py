"""Platform routers for ``register_v1_api_routers`` (paths relative to ``/api/v1`` root)."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

from basis.interface.http.platform.audit import router as audit_router
from basis.interface.http.platform.e2e_helpers import router as e2e_helpers_router
from basis.interface.http.platform.model_providers import router as model_providers_router
from basis.interface.http.platform.models import router as models_router
from basis.interface.http.platform.organizations import router as organizations_router
from basis.interface.http.platform.platform_info import router as platform_info_router
from basis.interface.http.platform.reasoning import router as reasoning_router
from basis.interface.http.platform.settings import router as settings_router
from basis.interface.http.platform.users import router as users_router
from basis.interface.http.platform.auth_mount import router as auth_router

# (router, suffix under api root — empty string mounts at root, e.g. users)
_PLATFORM_ROUTERS: tuple[tuple[APIRouter, str], ...] = (
    (auth_router, "/auth"),
    (platform_info_router, "/platform"),
    (organizations_router, "/orgs"),
    (settings_router, "/settings"),
    (model_providers_router, "/model-providers"),
    (models_router, "/models"),
    (audit_router, "/audit"),
    (reasoning_router, "/reason"),
)


def mount_platform_routers(app: FastAPI, root: str) -> None:
    """Register platform-scoped routers under ``root`` (typically ``/api/v1``)."""
    for router, suffix in _PLATFORM_ROUTERS:
        app.include_router(router, prefix=f"{root}{suffix}")
    app.include_router(users_router, prefix=root)


def mount_platform_e2e_helpers(app: FastAPI, root: str) -> None:
    app.include_router(e2e_helpers_router, prefix=root)
