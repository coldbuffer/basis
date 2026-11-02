"""SAML 2.0 SP helpers (OneLogin python3-saml)."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from basis.services.tenancy.identity.saml_capabilities import saml_sp_available


def _require_saml() -> None:
    if not saml_sp_available():
        raise RuntimeError("python3-saml is not installed (uv sync --extra saml)")


def _normalize_idp_cert(pem: str) -> str:
    body = pem.strip()
    if "BEGIN CERTIFICATE" in body:
        lines = [line.strip() for line in body.splitlines() if line.strip() and "CERTIFICATE" not in line]
        return "".join(lines)
    return body.replace("\n", "").replace("\r", "")


def _normalize_sp_pem(pem: str) -> str:
    """OneLogin accepts PEM with headers for SP cert/key."""
    return pem.strip()


def build_saml_settings(
    *,
    sp_entity_id: str,
    acs_url: str,
    idp_entity_id: str,
    idp_sso_url: str,
    idp_x509_cert: str,
    authn_requests_signed: bool = False,
    sp_x509_cert: str | None = None,
    sp_private_key: str | None = None,
    slo_enabled: bool = False,
    idp_slo_url: str | None = None,
    sp_slo_url: str | None = None,
) -> dict[str, Any]:
    sp_block: dict[str, Any] = {
        "entityId": sp_entity_id,
        "assertionConsumerService": {
            "url": acs_url,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        },
        "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
    }
    security: dict[str, Any] = {
        "wantAssertionsSigned": True,
        "wantMessagesSigned": False,
        "authnRequestsSigned": False,
    }
    sp_cert = (sp_x509_cert or "").strip()
    sp_key = (sp_private_key or "").strip()
    if authn_requests_signed:
        if not sp_cert or not sp_key:
            raise ValueError("authn_requests_signed requires SP certificate and private key")
        sp_block["x509cert"] = _normalize_sp_pem(sp_cert)
        sp_block["privateKey"] = _normalize_sp_pem(sp_key)
        security["authnRequestsSigned"] = True
    idp_block: dict[str, Any] = {
        "entityId": idp_entity_id,
        "singleSignOnService": {
            "url": idp_sso_url,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        },
        "x509cert": _normalize_idp_cert(idp_x509_cert),
    }
    slo_url = (idp_slo_url or "").strip()
    sp_logout = (sp_slo_url or "").strip()
    if slo_enabled and slo_url and sp_logout:
        idp_block["singleLogoutService"] = {
            "url": slo_url,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        }
        sp_block["singleLogoutService"] = {
            "url": sp_logout,
            "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        }
    return {
        "strict": True,
        "debug": False,
        "sp": sp_block,
        "idp": idp_block,
        "security": security,
    }


def fastapi_request_to_saml(request: Request, post_data: dict[str, str] | None = None) -> dict[str, Any]:
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    https = "on" if forwarded_proto == "https" else "off"
    host = request.headers.get("host") or request.url.netloc
    return {
        "https": https,
        "http_host": host,
        "script_name": request.url.path,
        "server_port": str(request.url.port or (443 if https == "on" else 80)),
        "get_data": dict(request.query_params),
        "post_data": post_data or {},
    }


def saml_login_redirect_url(
    request: Request,
    settings: dict[str, Any],
    *,
    relay_state: str,
) -> str:
    _require_saml()
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    req = fastapi_request_to_saml(request)
    auth = OneLogin_Saml2_Auth(req, settings)
    return auth.login(return_to=relay_state)


def saml_process_acs(
    request: Request,
    settings: dict[str, Any],
    *,
    saml_response: str,
    relay_state: str,
) -> dict[str, Any]:
    _require_saml()
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    req = fastapi_request_to_saml(
        request,
        post_data={"SAMLResponse": saml_response, "RelayState": relay_state},
    )
    auth = OneLogin_Saml2_Auth(req, settings)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        reason = auth.get_last_error_reason()
        raise ValueError(f"SAML ACS failed: {errors} ({reason})")
    if not auth.is_authenticated():
        raise ValueError("SAML response did not authenticate")
    attributes = auth.get_attributes() or {}
    name_id = auth.get_nameid() or ""
    email = _attribute_first(attributes, ("email", "mail", "Email", "emailAddress"))
    if not email and "@" in name_id:
        email = name_id
    display_name = _attribute_first(attributes, ("displayName", "name", "cn", "givenName"))
    return {
        "subject": name_id or email,
        "email": email,
        "display_name": display_name,
        "issuer": settings["idp"]["entityId"],
    }


def saml_logout_redirect_url(
    request: Request,
    settings: dict[str, Any],
    *,
    name_id: str,
    session_index: str | None = None,
    relay_state: str | None = None,
) -> str | None:
    _require_saml()
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    req = fastapi_request_to_saml(request)
    auth = OneLogin_Saml2_Auth(req, settings)
    return auth.logout(
        name_id=name_id,
        session_index=session_index or "",
        return_to=relay_state,
    )


def saml_process_slo(
    request: Request,
    settings: dict[str, Any],
    *,
    post_data: dict[str, str] | None = None,
) -> str | None:
    """Process IdP logout response; returns redirect URL if any."""
    _require_saml()
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    req = fastapi_request_to_saml(request, post_data=post_data)
    auth = OneLogin_Saml2_Auth(req, settings)
    redirect = auth.process_slo(delete_session_cb=lambda: None)
    errors = auth.get_errors()
    if errors:
        reason = auth.get_last_error_reason()
        raise ValueError(f"SAML SLO failed: {errors} ({reason})")
    return redirect


def saml_metadata_xml(settings: dict[str, Any]) -> str:
    _require_saml()
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.settings import OneLogin_Saml2_Settings

    meta_settings = OneLogin_Saml2_Settings(settings, sp_validation_only=True)
    return meta_settings.get_sp_metadata()


def _attribute_first(attributes: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        raw = attributes.get(key)
        if raw is None:
            continue
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    return item.strip()
        elif isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None
