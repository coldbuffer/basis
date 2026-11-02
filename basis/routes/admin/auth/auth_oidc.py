"""Organization OIDC SSO."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from basis.services.tenancy.admin.store import AdminStore
from basis.http.deps import get_store
from basis.services.tenancy.identity.oauth_client import (
    build_oidc_authorize_url,
    exchange_oidc_code,
    fetch_oidc_metadata,
    fetch_oidc_userinfo,
)
from basis.services.tenancy.identity.http_paths import auth_v1_path
from basis.services.tenancy.identity.state import new_nonce, sign_oauth_state, verify_oauth_state

from basis.routes.admin.auth.auth_support import auth_settings, redirect_with_token

router = APIRouter()


@router.get("/oidc/{org_slug}/start")
async def org_oidc_start(
    org_slug: str,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Oidc Start. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    org = store.get_org_by_slug(org_slug)
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_oidc_config(org.id)
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SSO 未配置"})
    metadata = await fetch_oidc_metadata(cfg["issuer"])
    state = sign_oauth_state(
        settings.state_secret,
        {"provider": "oidc", "org_id": org.id, "nonce": new_nonce()},
    )
    redirect_uri = settings.oauth_callback_url(auth_v1_path("oidc/callback"))
    url = build_oidc_authorize_url(
        metadata,
        client_id=cfg["client_id"],
        redirect_uri=redirect_uri,
        scope=cfg["scopes"],
        state=state,
    )
    return RedirectResponse(url)


@router.get("/oidc/callback")
async def org_oidc_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Oidc Callback. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    try:
        payload = verify_oauth_state(settings.state_secret, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "无效 state"}) from exc
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "缺少 org_id"})
    cfg = store.get_org_oidc_config(str(org_id))
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SSO 未配置"})
    metadata = await fetch_oidc_metadata(cfg["issuer"])
    redirect_uri = settings.oauth_callback_url(auth_v1_path("oidc/callback"))
    token_data = await exchange_oidc_code(
        metadata,
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        code=code,
        redirect_uri=redirect_uri,
    )
    userinfo = await fetch_oidc_userinfo(metadata, token_data["access_token"])
    subject = str(userinfo.get("sub") or "")
    if not subject:
        raise HTTPException(status_code=502, detail={"code": "upstream", "message": "IdP 未返回 sub"})
    user, session = store.login_or_register_federated(
        provider="oidc",
        subject=subject,
        email=userinfo.get("email"),
        display_name=userinfo.get("name") or userinfo.get("preferred_username"),
        organization_id=str(org_id),
        issuer=cfg["issuer"],
    )
    _ = user
    return redirect_with_token(settings, session)
