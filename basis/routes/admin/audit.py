from fastapi import APIRouter, Depends, Query

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store, require_system_admin

router = APIRouter(tags=["audit"])


@router.get("")
async def list_audit(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    workspace_id: str | None = Query(None),
    action_prefix: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    """
List Audit. Platform audit log (admin). Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    if workspace_id:
        events = store.list_audit_for_workspace(
            workspace_id,
            action_prefix=action_prefix,
            limit=limit,
        )
    else:
        events = store.list_audit(limit=limit, action_prefix=action_prefix)
    return {"events": events}
