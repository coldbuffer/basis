import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.deps import get_current_user, get_store
from basis.services.tenancy.identity.http_paths import auth_v1_path
from basis.services.tenancy.identity.desktop_principal import issue_desktop_session_token
from basis.services.tenancy.identity.org_login_policy import assert_local_login_allowed
from basis.services.tenancy.identity.settings import load_auth_settings_from_store

router = APIRouter()


def _reject_if_desktop(request: Request) -> None:
    if request.app.state.settings.is_desktop:
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Desktop 模式不支持该认证方式"},
        )


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _auth_settings(request: Request):
    app_settings = request.app.state.settings
    public = f"http://{app_settings.host}:{app_settings.port}".rstrip("/")
    return load_auth_settings_from_store(
        request.app.state.store,
        default_public_url=public,
    )


@router.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Create a local account when password registration is enabled in platform settings.
    """
    _reject_if_desktop(request)
    auth = _auth_settings(request)
    if not auth.password_login_enabled:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "密码注册未启用"})
    try:
        assert_local_login_allowed(store, body.email)
        user, token = store.register(body.email, body.password, body.display_name)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message}) from exc
    return {"user": user.public(), "token": token}


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Authenticate with email and password. Returns a session Bearer token for platform and workspace routes.
    """
    _reject_if_desktop(request)
    auth = _auth_settings(request)
    if not auth.password_login_enabled:
        raise HTTPException(status_code=403, detail={"code": "forbidden", "message": "密码登录未启用"})
    try:
        assert_local_login_allowed(store, body.email)
        user, token = store.login(body.email, body.password)
    except AdminError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message}) from exc
    return {"user": user.public(), "token": token}


@router.post("/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Logout. Revokes the session token. When the user signed in via SAML with SLO enabled, returns `saml_logout_url` to start IdP logout.
    """
    hint = store.saml_logout_hint_for_user(user.id)
    store.logout(request.state.token, user.id)
    payload: dict = {"ok": True}
    if hint is not None:
        auth = _auth_settings(request)
        query = urllib.parse.urlencode(
            {
                "name_id": hint["name_id"],
                "session_index": hint.get("session_index") or "",
            }
        )
        path = auth_v1_path(f"saml/{hint['org_slug']}/logout")
        payload["saml_logout_url"] = f"{auth.public_url.rstrip('/')}{path}?{query}"
    return payload


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    """Return the current session user profile (requires session token)."""
    return {"user": user.public()}


@router.post("/desktop-session")
async def desktop_session(
    request: Request,
    store: AdminStore = Depends(get_store),
) -> dict:
    """
Desktop Session. Issue a long-lived Bearer token for the local principal (desktop profile only).
    """
    if not request.app.state.settings.is_desktop:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "仅 Desktop 模式可用"})
    user = getattr(request.app.state, "desktop_user", None)
    if user is None:
        raise HTTPException(status_code=500, detail={"code": "desktop_uninitialized", "message": "Desktop principal 未初始化"})
    token = issue_desktop_session_token(store, user)
    return {"user": user.public(), "token": token}
