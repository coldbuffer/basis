"""Email magic-link authentication."""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore
from basis.http.deps import get_store
from basis.services.tenancy.identity.magic_link import deliver_magic_link
from basis.services.tenancy.identity.http_paths import auth_v1_path

from basis.routes.admin.auth.auth_support import auth_settings, redirect_with_token

router = APIRouter()


class MagicLinkRequest(BaseModel):
    email: EmailStr


@router.post("/magic-link/request")
async def magic_link_request(
    body: MagicLinkRequest,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> dict[str, bool]:
    """
Magic Link Request. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    if not settings.magic_link_enabled:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "邮箱登录未启用"})
    if not settings.magic_link_available:
        raise HTTPException(status_code=503, detail={"code": "not_configured", "message": "Magic Link 邮件未配置"})
    org = store.resolve_org_by_email_domain(body.email)
    org_id = org.id if org else None
    token = store.create_magic_link(body.email, organization_id=org_id)
    q = urllib.parse.urlencode({"token": token})
    link = f"{settings.oauth_callback_url(auth_v1_path('magic-link/verify'))}?{q}"
    deliver_magic_link(settings, email=body.email, link=link)
    return {"ok": True}


def _normalize_magic_link_token(raw: str) -> str:
    return raw.strip().strip(".").strip()


@router.get("/magic-link/verify")
async def magic_link_verify(
    request: Request,
    token: str = Query(...),
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Magic Link Verify. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    cleaned = _normalize_magic_link_token(token)
    try:
        _user, session = store.consume_magic_link(cleaned)
    except AdminError as exc:
        if exc.code in ("invalid_token", "registration_closed"):
            query = urllib.parse.urlencode({"magic_link_error": exc.code})
            return RedirectResponse(
                url=f"{settings.web_origin}/login?{query}",
                status_code=302,
            )
        raise
    return redirect_with_token(settings, session)
