"""Org SSO discovery and enabled auth providers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.services.tenancy.admin.store import AdminStore
from basis.http.deps import get_store
from basis.services.tenancy.identity.http_paths import auth_v1_path
from basis.services.tenancy.identity.saml_capabilities import saml_sp_available

from basis.routes.admin.auth.auth_support import auth_settings

router = APIRouter()


@router.get("/org-sso-options")
async def org_sso_options(
    request: Request,
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Org Sso Options. List organizations with enabled OIDC for login-page SSO buttons (no email required).
    """
    settings = auth_settings(request)
    public = settings.public_url.rstrip("/")
    options: list[dict[str, Any]] = []
    for org in store.list_enabled_org_sso_public():
        if store.get_org_oidc_config(org.id) is not None:
            login_path = auth_v1_path(f"oidc/{org.slug}/start")
            options.append(
                {
                    "organization_id": org.id,
                    "org_slug": org.slug,
                    "org_name": org.name,
                    "auth_policy": org.auth_policy,
                    "protocol": "oidc",
                    "login_path": login_path,
                    "login_url": f"{public}{login_path}",
                }
            )
        if store.get_org_saml_config(org.id) is not None:
            login_path = auth_v1_path(f"saml/{org.slug}/start")
            options.append(
                {
                    "organization_id": org.id,
                    "org_slug": org.slug,
                    "org_name": org.name,
                    "auth_policy": org.auth_policy,
                    "protocol": "saml",
                    "login_path": login_path,
                    "login_url": f"{public}{login_path}",
                }
            )
        if store.get_org_cas_config(org.id) is not None:
            login_path = auth_v1_path(f"cas/{org.slug}/start")
            options.append(
                {
                    "organization_id": org.id,
                    "org_slug": org.slug,
                    "org_name": org.name,
                    "auth_policy": org.auth_policy,
                    "protocol": "cas",
                    "login_path": login_path,
                    "login_url": f"{public}{login_path}",
                }
            )
    return {"options": options}


@router.get("/org-sso-hint")
async def org_sso_hint(
    request: Request,
    email: str = Query(..., min_length=3),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """
Org Sso Hint. Resolve enabled org OIDC login by email domain (F-ACC-07).
    """
    match = store.resolve_org_sso_for_email(email.strip())
    if match is None:
        return {"available": False}
    org, protocol = match
    settings = auth_settings(request)
    login_path = auth_v1_path(f"{protocol}/{org.slug}/start")
    public = settings.public_url.rstrip("/")
    return {
        "available": True,
        "organization_id": org.id,
        "org_slug": org.slug,
        "org_name": org.name,
        "auth_policy": org.auth_policy,
        "protocol": protocol,
        "password_login_allowed": True,
        "login_path": login_path,
        "login_url": f"{public}{login_path}",
    }


@router.get("/providers")
async def auth_providers(request: Request) -> dict[str, Any]:
    """
Auth Providers. Authentication and session bootstrap. Public bootstrap; optional session for personalized responses.
    """
    settings = auth_settings(request)
    return {
        "password": settings.password_login_enabled,
        "github": settings.github_enabled,
        "google": settings.google_enabled,
        "magic_link": settings.magic_link_available,
        "org_oidc": True,
        "org_saml": saml_sp_available(),
        "org_cas": True,
    }
