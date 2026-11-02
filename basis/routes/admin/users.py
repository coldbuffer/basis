from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store, require_system_admin
from basis.services.tenancy.realtime.access import revoke_user_realtime

router = APIRouter(tags=["users"])


class CreateUserRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str
    is_admin: bool = False


@router.get("/users")
async def list_active_users(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """List Active Users. Requires session JWT (`sessionAuth`)."""
    del user
    return {"users": [item.public() for item in store.list_users()]}


@router.get("/admin/users")
async def list_users(
    deactivated: bool = Query(default=False),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """List Users. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    return {"users": [item.public() for item in store.list_users(deactivated=deactivated)]}


@router.post("/admin/users")
async def create_user(
    body: CreateUserRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Create User. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    created = store.create_user(
        user,
        body.email,
        body.password,
        body.display_name,
        is_admin=body.is_admin,
    )
    return {"user": created.public()}


@router.post("/admin/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Deactivate User. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    store.deactivate_user(user, user_id)
    revoke_user_realtime(request, user_id)
    return {"ok": True}


@router.post("/admin/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Reactivate User. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    store.reactivate_user(user, user_id)
    return {"ok": True}
