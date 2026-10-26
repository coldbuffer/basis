"""Workspace role gates for mutating application operations."""

from __future__ import annotations

from fastapi import HTTPException

from basis.application.kernel.context import WorkspaceCoreContext
from basis.application.kernel.errors import CoreError
from basis.domain.errors import AdminError


def require_workspace_owner(ctx: WorkspaceCoreContext) -> None:
    try:
        _, role = ctx.store.get_workspace_for(ctx.user, ctx.workspace.id, "admin")
        if role != "owner" and not ctx.user.is_admin:
            raise AdminError(403, "forbidden", "只有所有者或系统管理员可以重置工作区")
    except AdminError as exc:
        raise CoreError(
            {"code": exc.code, "message": exc.message},
            status_code=exc.status,
        ) from exc
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise CoreError(detail, status_code=exc.status_code) from exc


def require_workspace_editor(ctx: WorkspaceCoreContext) -> None:
    try:
        if ctx.assert_workspace_editor is not None:
            ctx.assert_workspace_editor()
        else:
            ctx.store.get_workspace_for(ctx.user, ctx.workspace.id, "editor")
    except AdminError as exc:
        raise CoreError(
            {"code": exc.code, "message": exc.message},
            status_code=exc.status,
        ) from exc
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise CoreError(detail, status_code=exc.status_code) from exc
