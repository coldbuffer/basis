"""GitHub and Google OAuth login."""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from basis.services.tenancy.admin.store import AdminStore
from basis.http.deps import get_store
from basis.services.tenancy.identity.oauth_client import (
    exchange_github_code,
    exchange_google_code,
    fetch_github_user,
    fetch_google_userinfo,
)
from basis.services.tenancy.identity.http_paths import auth_v1_path
from basis.services.tenancy.identity.state import new_nonce, sign_oauth_state, verify_oauth_state

from basis.routes.admin.auth.auth_support import auth_settings, redirect_with_token

router = APIRouter()


@router.get("/oauth/github/start")
async def github_start(request: Request) -> RedirectResponse:
    """
Github Start. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    if not settings.github_enabled:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "GitHub OAuth 未配置"})
    state = sign_oauth_state(
        settings.state_secret,
        {"provider": "github", "nonce": new_nonce()},
    )
    params = urllib.parse.urlencode(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.oauth_callback_url(auth_v1_path("oauth/github/callback")),
            "scope": "read:user user:email",
            "state": state,
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.get("/oauth/github/callback")
async def github_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Github Callback. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    if not settings.github_enabled:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "GitHub OAuth 未配置"})
    try:
        verify_oauth_state(settings.state_secret, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "无效 state"}) from exc
    redirect_uri = settings.oauth_callback_url(auth_v1_path("oauth/github/callback"))
    token_data = await exchange_github_code(
        client_id=settings.github_client_id or "",
        client_secret=settings.github_client_secret or "",
        code=code,
        redirect_uri=redirect_uri,
    )
    profile = await fetch_github_user(token_data["access_token"])
    subject = str(profile.get("id") or "")
    if not subject:
        raise HTTPException(status_code=502, detail={"code": "upstream", "message": "GitHub 未返回用户 ID"})
    user, session = store.login_or_register_federated(
        provider="github",
        subject=subject,
        email=profile.get("email"),
        display_name=profile.get("name") or profile.get("login"),
        organization_id=None,
        issuer=None,
    )
    _ = user
    return redirect_with_token(settings, session)


@router.get("/oauth/google/start")
async def google_start(request: Request) -> RedirectResponse:
    """
Google Start. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    if not settings.google_enabled:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "Google OAuth 未配置"})
    state = sign_oauth_state(
        settings.state_secret,
        {"provider": "google", "nonce": new_nonce()},
    )
    params = urllib.parse.urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.oauth_callback_url(auth_v1_path("oauth/google/callback")),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/oauth/google/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Google Callback. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    if not settings.google_enabled:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "Google OAuth 未配置"})
    try:
        verify_oauth_state(settings.state_secret, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "无效 state"}) from exc
    redirect_uri = settings.oauth_callback_url(auth_v1_path("oauth/google/callback"))
    token_data = await exchange_google_code(
        client_id=settings.google_client_id or "",
        client_secret=settings.google_client_secret or "",
        code=code,
        redirect_uri=redirect_uri,
    )
    profile = await fetch_google_userinfo(token_data["access_token"])
    subject = str(profile.get("sub") or "")
    if not subject:
        raise HTTPException(status_code=502, detail={"code": "upstream", "message": "Google 未返回 sub"})
    user, session = store.login_or_register_federated(
        provider="google",
        subject=subject,
        email=profile.get("email"),
        display_name=profile.get("name"),
        organization_id=None,
        issuer=None,
    )
    _ = user
    return redirect_with_token(settings, session)
