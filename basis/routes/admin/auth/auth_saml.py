"""Organization SAML SSO (SP-initiated login, ACS, SLO)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response

from basis.services.tenancy.admin.store import AdminStore
from basis.services.tenancy.identity.settings import AuthSettings
from basis.http.deps import get_store
from basis.services.tenancy.identity.http_paths import auth_v1_path
from basis.services.tenancy.identity.saml_capabilities import saml_sp_available
from basis.services.tenancy.identity.saml_client import (
    build_saml_settings,
    saml_login_redirect_url,
    saml_logout_redirect_url,
    saml_metadata_xml,
    saml_process_acs,
    saml_process_slo,
)
from basis.services.tenancy.identity.state import new_nonce, sign_oauth_state, verify_oauth_state

from basis.routes.admin.auth.auth_support import auth_settings, redirect_with_token

router = APIRouter()


def _saml_sp_entity_id(settings: AuthSettings, org_slug: str, cfg: dict[str, Any]) -> str:
    override = (cfg.get("sp_entity_id") or "").strip()
    if override:
        return override
    return f"{settings.public_url.rstrip('/')}{auth_v1_path(f'saml/{org_slug}/metadata')}"


def _saml_settings_for_org(
    settings: AuthSettings,
    org_slug: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    acs_url = settings.oauth_callback_url(auth_v1_path("saml/acs"))
    sp_slo_url = settings.oauth_callback_url(auth_v1_path("saml/slo"))
    sp_entity_id = _saml_sp_entity_id(settings, org_slug, cfg)
    return build_saml_settings(
        sp_entity_id=sp_entity_id,
        acs_url=acs_url,
        idp_entity_id=cfg["idp_entity_id"],
        idp_sso_url=cfg["idp_sso_url"],
        idp_x509_cert=cfg["idp_x509_cert"],
        authn_requests_signed=bool(cfg.get("authn_requests_signed")),
        sp_x509_cert=cfg.get("sp_x509_cert"),
        sp_private_key=cfg.get("sp_private_key"),
        slo_enabled=bool(cfg.get("slo_enabled")),
        idp_slo_url=cfg.get("idp_slo_url"),
        sp_slo_url=sp_slo_url,
    )


@router.get("/saml/{org_slug}/metadata")
async def org_saml_metadata(
    org_slug: str,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> Response:
    """
Org Saml Metadata. SP metadata XML for IdP configuration (F-ACC-07 SAML).
    """
    if not saml_sp_available():
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": "SAML 未安装（uv sync --extra saml）"},
        )
    settings = auth_settings(request)
    org = store.get_org_by_slug(org_slug)
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_saml_config(org.id)
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SAML 未配置"})
    saml_settings = _saml_settings_for_org(settings, org.slug, cfg)
    xml = saml_metadata_xml(saml_settings)
    return Response(content=xml, media_type="application/samlmetadata+xml")


@router.get("/saml/{org_slug}/start")
async def org_saml_start(
    org_slug: str,
    request: Request,
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Saml Start. SP-initiated SAML login (F-ACC-07).
    """
    if not saml_sp_available():
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": "SAML 未安装（uv sync --extra saml）"},
        )
    settings = auth_settings(request)
    org = store.get_org_by_slug(org_slug)
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_saml_config(org.id)
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SAML 未配置"})
    relay_state = sign_oauth_state(
        settings.state_secret,
        {"provider": "saml", "org_id": org.id, "nonce": new_nonce()},
    )
    saml_settings = _saml_settings_for_org(settings, org.slug, cfg)
    try:
        redirect_url = saml_login_redirect_url(request, saml_settings, relay_state=relay_state)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": str(exc)},
        ) from exc
    return RedirectResponse(redirect_url)


@router.post("/saml/acs")
async def org_saml_acs(
    request: Request,
    SAMLResponse: str = Form(...),  # noqa: N803
    RelayState: str = Form(""),  # noqa: N803
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Saml Acs. SAML assertion consumer (POST binding, F-ACC-07).
    """
    if not saml_sp_available():
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": "SAML 未安装（uv sync --extra saml）"},
        )
    settings = auth_settings(request)
    try:
        payload = verify_oauth_state(settings.state_secret, RelayState)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "无效 RelayState"}) from exc
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "缺少 org_id"})
    org = store.get_org_by_id(str(org_id))
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_saml_config(str(org_id))
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SAML 未配置"})
    saml_settings = _saml_settings_for_org(settings, org.slug, cfg)
    try:
        profile = saml_process_acs(
            request,
            saml_settings,
            saml_response=SAMLResponse,
            relay_state=RelayState,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "saml_failed", "message": str(exc)}) from exc
    subject = str(profile.get("subject") or "")
    if not subject:
        raise HTTPException(status_code=502, detail={"code": "upstream", "message": "IdP 未返回 NameID"})
    user, session = store.login_or_register_federated(
        provider="saml",
        subject=subject,
        email=profile.get("email"),
        display_name=profile.get("display_name"),
        organization_id=str(org_id),
        issuer=cfg["idp_entity_id"],
    )
    _ = user
    return redirect_with_token(settings, session)


def _saml_slo_finish(
    request: Request,
    settings: AuthSettings,
    store: AdminStore,
    relay_state: str,
    *,
    post_data: dict[str, str] | None = None,
) -> RedirectResponse:
    if not relay_state:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "缺少 RelayState"})
    try:
        payload = verify_oauth_state(settings.state_secret, relay_state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "无效 RelayState"}) from exc
    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail={"code": "bad_state", "message": "缺少 org_id"})
    org = store.get_org_by_id(str(org_id))
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_saml_config(str(org_id))
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SAML 未配置"})
    if not cfg.get("slo_enabled"):
        raise HTTPException(status_code=400, detail={"code": "slo_disabled", "message": "组织未启用 SAML SLO"})
    saml_settings = _saml_settings_for_org(settings, org.slug, cfg)
    try:
        redirect = saml_process_slo(request, saml_settings, post_data=post_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "saml_slo_failed", "message": str(exc)}) from exc
    target = redirect or f"{settings.web_origin}/login"
    return RedirectResponse(target, status_code=302)


@router.get("/saml/{org_slug}/logout")
async def org_saml_logout_start(
    org_slug: str,
    request: Request,
    name_id: str = Query(..., min_length=1),
    session_index: str = Query(""),
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Saml Logout Start. SP-initiated SAML single logout (F-ACC-07).
    """
    if not saml_sp_available():
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": "SAML 未安装（uv sync --extra saml）"},
        )
    settings = auth_settings(request)
    org = store.get_org_by_slug(org_slug)
    if org is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "组织不存在"})
    cfg = store.get_org_saml_config(org.id)
    if cfg is None:
        raise HTTPException(status_code=404, detail={"code": "not_configured", "message": "组织 SAML 未配置"})
    if not cfg.get("slo_enabled"):
        raise HTTPException(status_code=400, detail={"code": "slo_disabled", "message": "组织未启用 SAML SLO"})
    relay_state = sign_oauth_state(
        settings.state_secret,
        {"provider": "saml", "org_id": org.id, "flow": "slo", "nonce": new_nonce()},
    )
    saml_settings = _saml_settings_for_org(settings, org.slug, cfg)
    try:
        redirect_url = saml_logout_redirect_url(
            request,
            saml_settings,
            name_id=name_id,
            session_index=session_index or None,
            relay_state=relay_state,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": str(exc)},
        ) from exc
    if not redirect_url:
        raise HTTPException(status_code=502, detail={"code": "upstream", "message": "IdP 未返回 SLO URL"})
    return RedirectResponse(redirect_url, status_code=302)


@router.get("/saml/slo")
async def org_saml_slo_get(
    request: Request,
    RelayState: str = Query(""),  # noqa: N803
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Saml Slo. SAML single logout response (HTTP-Redirect, F-ACC-07).
    """
    if not saml_sp_available():
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": "SAML 未安装（uv sync --extra saml）"},
        )
    settings = auth_settings(request)
    return _saml_slo_finish(request, settings, store, RelayState)


@router.post("/saml/slo")
async def org_saml_slo_post(
    request: Request,
    RelayState: str = Form(""),  # noqa: N803
    SAMLResponse: str = Form(""),  # noqa: N803
    SAMLRequest: str = Form(""),  # noqa: N803
    store: AdminStore = Depends(get_store),
) -> RedirectResponse:
    """
Org Saml Slo. SAML single logout response (HTTP-POST, F-ACC-07).
    """
    if not saml_sp_available():
        raise HTTPException(
            status_code=503,
            detail={"code": "saml_unavailable", "message": "SAML 未安装（uv sync --extra saml）"},
        )
    settings = auth_settings(request)
    post_data: dict[str, str] = {"RelayState": RelayState}
    if SAMLResponse:
        post_data["SAMLResponse"] = SAMLResponse
    if SAMLRequest:
        post_data["SAMLRequest"] = SAMLRequest
    return _saml_slo_finish(request, settings, store, RelayState, post_data=post_data)
