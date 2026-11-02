"""Register v1 API routers (optional duplicate legacy prefix)."""

from __future__ import annotations

from fastapi import FastAPI

from basis.routes.admin.mount_platform import (
    mount_platform_e2e_helpers,
    mount_platform_routers,
)
from basis.routes.workspace.mount_workspace import (
    mount_workspace_e2e_helpers,
    mount_workspace_routers,
)


def register_v1_api_routers(
    app: FastAPI,
    *,
    legacy_api_enabled: bool,
    include_e2e_helpers: bool = False,
) -> None:
    roots = ["/api/v1"]
    if legacy_api_enabled:
        roots.append("/api")

    for root in roots:
        mount_platform_routers(app, root)
        mount_workspace_routers(app, f"{root}/workspaces")

    if include_e2e_helpers:
        for root in roots:
            mount_platform_e2e_helpers(app, root)
            mount_workspace_e2e_helpers(app, f"{root}/workspaces")
