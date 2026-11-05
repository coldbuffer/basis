"""Organization CAS 2.0 SSO (service ticket)."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from basis.http.deps import get_store
from basis.routes.admin.auth.auth_support import auth_settings, redirect_with_token
from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import AdminStore
from basis.services.tenancy.identity.cas_client import (
    cas_login_url,
    cas_service_url,
    parse_cas_success,
    validate_cas_ticket,
)
from basis.services.tenancy.identity.http_paths import auth_v1_path

router = APIRouter()


def _service_for(request: Request, org_slug: str) -> str:
    settings = auth_settings(request)
    return cas_service_url(settings.public_url, auth_v1_path("cas/callback"), org_slug)


@router.get("/cas/{org_slug}/start")
async def org_cas_start(
    org_slug: str,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Cas Start. Redirect the browser to the organization's CAS login.
    """
    org = store.get_org_by_slug(org_slug)
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_cas_config(org.id)
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 CAS 未配置"})
    service = _service_for(request, org.slug)
    return RedirectResponse(
        cas_login_url(cfg["server_url"], service, cfg["login_path"]),
    )


@router.get("/cas/callback")
async def org_cas_callback(
    request: Request,
    org: str = Query(...),
    ticket: str = Query(...),
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Cas Callback. Validate the CAS service ticket and open a Basis session.
    """
    organization = store.get_org_by_slug(org)
    if organization is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_cas_config(organization.id)
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 CAS 未配置"})
    service = _service_for(request, organization.slug)
    try:
        body = await validate_cas_ticket(
            cfg["server_url"],
            service,
            ticket,
            cfg["validate_path"],
        )
        subject, email, display_name = parse_cas_success(body, cfg["email_attribute"])
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"code": "upstream", "message": "CAS 校验失败"}) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_ticket", "message": "CAS 票据无效"},
        ) from exc
    settings = auth_settings(request)
    try:
        _user, session = store.login_or_register_federated(
            provider="cas",
            subject=subject,
            email=email,
            display_name=display_name or subject,
            organization_id=organization.id,
            issuer=cfg["server_url"],
        )
    except AdminError as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return redirect_with_token(settings, session)
