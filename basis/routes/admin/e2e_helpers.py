"""Playwright-only platform helpers (data/e2e only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from basis.services.errors import AdminError
from basis.services.tenancy.admin.persistence.workspaces import delete_workspace
from basis.services.tenancy.admin.store import AdminStore
from basis.http.deps import get_store
from basis.infra.runtime.config import Settings
from basis.infra.e2e_sandbox.playwright_e2e import is_playwright_e2e_data_dir

router = APIRouter(tags=["platform"])


def _e2e_helpers_enabled(request: Request) -> bool:
    settings: Settings = request.app.state.settings
    return is_playwright_e2e_data_dir(settings.data_dir)


@router.post("/_e2e/playwright-reset")
async def e2e_playwright_reset(
    request: Request,
    store: AdminStore = Depends(get_store),
) -> dict[str, str]:
    """Wipe tenancy rows so the next register creates the platform admin (Playwright data/e2e only)."""
    if not _e2e_helpers_enabled(request):
        raise AdminError(404, "not_found", "资源不存在")
    conn = store._conn
    with store._lock:
        workspace_ids = [row["id"] for row in conn.execute("SELECT id FROM workspaces").fetchall()]
        for workspace_id in workspace_ids:
            delete_workspace(conn, workspace_id)
        for stmt in (
            "DELETE FROM audit_log",
            "DELETE FROM api_tokens",
            "DELETE FROM tokens",
            "DELETE FROM magic_link_tokens",
            "DELETE FROM oauth_state_nonces",
            "DELETE FROM organizations",
            "DELETE FROM users",
        ):
            conn.execute(stmt)
        conn.commit()
    return {"status": "ok"}
