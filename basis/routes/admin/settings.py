from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store, require_system_admin
from basis.services.tenancy.identity.settings import invalidate_app_auth_settings

router = APIRouter(tags=["settings"])


class AccessCredentialsPatch(BaseModel):
    class EmailCreds(BaseModel):
        transport: str | None = None
        api_key: str | None = None
        from_: str | None = Field(None, alias="from")
        host: str | None = None
        port: int | None = None
        username: str | None = None
        password: str | None = None

    class OAuthCreds(BaseModel):
        client_id: str | None = None
        client_secret: str | None = None

    email: EmailCreds | None = None
    oauth: dict[str, OAuthCreds] | None = None

    model_config = {"populate_by_name": True}


class AccessSettingsRequest(BaseModel):
    auth_providers: list[str] | None = None
    signup_policy: str | None = None
    public_url: str | None = None
    web_origin: str | None = None
    magic_link_dev_log: bool | None = None
    credentials: AccessCredentialsPatch | None = None


class SettingsRequest(BaseModel):
    open_registration: bool | None = None
    chat_provider: str | None = None
    chat_base_url: str | None = None
    chat_model: str | None = None
    chat_api_key: str | None = None
    embed_provider: str | None = None
    embed_base_url: str | None = None
    embed_model: str | None = None
    embed_api_key: str | None = None


@router.get("")
async def get_settings(
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Get Settings. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    return store.get_settings()


@router.put("")
async def put_settings(
    body: SettingsRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """Put Settings. Requires session JWT (`sessionAuth`)."""
    require_system_admin(user)
    return store.update_settings(user, body.model_dump(exclude_unset=True))


def _default_public_url(request: Request) -> str:
    app_settings = request.app.state.settings
    return f"http://{app_settings.host}:{app_settings.port}".rstrip("/")


@router.get("/access")
async def get_access(
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Get Access. Platform system settings (admin). Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    return store.get_access_settings(default_public_url=_default_public_url(request))


@router.put("/access")
async def put_access(
    request: Request,
    body: AccessSettingsRequest,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Put Access. Platform system settings (admin). Requires session JWT (`sessionAuth`).
    """
    require_system_admin(user)
    payload = body.model_dump(exclude_unset=True, by_alias=True)
    if body.credentials is not None:
        creds = body.credentials.model_dump(exclude_unset=True, by_alias=True)
        payload["credentials"] = creds
    result = store.update_access_settings(
        user,
        payload,
        default_public_url=_default_public_url(request),
    )
    invalidate_app_auth_settings(request)
    return result
