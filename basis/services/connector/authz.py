"""Workspace role checks for connector use cases."""

from __future__ import annotations

from fastapi import HTTPException

from basis.services.kernel import WorkspaceCoreContext
from basis.services.kernel import CoreError


def require_workspace_editor(ctx: WorkspaceCoreContext) -> None:
    try:
        if ctx.assert_workspace_editor is not None:
            ctx.assert_workspace_editor()
        else:
            ctx.store.get_workspace_for(ctx.user, ctx.workspace.id, "editor")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise CoreError(detail, status_code=exc.status_code) from exc


def require_workspace_viewer(ctx: WorkspaceCoreContext) -> None:
    try:
        ctx.store.get_workspace_for(ctx.user, ctx.workspace.id, "viewer")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise CoreError(detail, status_code=exc.status_code) from exc
