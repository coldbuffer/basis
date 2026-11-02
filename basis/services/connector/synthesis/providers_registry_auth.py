"""Import upstream ``providers.yaml`` auth blocks into BOCP ``AuthSpec`` (P1)."""

from __future__ import annotations

from typing import Any

import yaml

from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    OAuth2DialectSpec,
    TwoStepAuthSpec,
)
from basis.services.connector.synthesis.paths import providers_registry_yaml

_BOCP_AUTH_DISPLAY_NAMES: dict[str, str] = {
    "oauth2": "OAuth 2.0",
    "oauth2_cc": "OAuth 2.0 (client credentials)",
    "api_key": "API key / token",
    "basic": "HTTP Basic",
    "two_step": "Two-step token",
    "oauth1": "OAuth 1.0",
    "jwt": "JWT bearer",
    "aws_sigv4": "AWS Signature V4",
    "app": "App installation",
    "none": "No authentication",
    "custom": "Custom",
    "database_dsn": "Database (DSN)",
}


def registry_auth_mode_to_bocp(registry_mode: str) -> str:
    """Map upstream registry ``auth_mode`` (uppercase) to BOCP ``AuthModeLiteral``."""
    mode = (registry_mode or "").strip().upper()
    return {
        "OAUTH2": "oauth2",
        "MCP_OAUTH2": "oauth2",
        "MCP_OAUTH2_GENERIC": "oauth2",
        "API_KEY": "api_key",
        "OAUTH2_CC": "oauth2_cc",
        "BASIC": "basic",
        "TWO_STEP": "two_step",
        "OAUTH1": "oauth1",
        "JWT": "jwt",
        "AWS_SIGV4": "aws_sigv4",
        "APP": "app",
        "NONE": "none",
        "CUSTOM": "custom",
        "BILL": "custom",
        "TBA": "custom",
        "SIGNATURE": "custom",
        "INSTALL_PLUGIN": "custom",
    }.get(mode, "custom")


def load_provider_registry_block(service: str) -> dict[str, Any] | None:
    path = providers_registry_yaml()
    if path is None:
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    candidates = [service, service.replace("_", "-"), service.replace("-", "_")]
    for key in candidates:
        block = data.get(key)
        if isinstance(block, dict):
            return block
    return None


def _registry_connection_config_fields(raw: dict[str, Any]) -> list[ConfigFieldSpec]:
    block = raw.get("connection_config")
    if not isinstance(block, dict):
        return []
    fields: list[ConfigFieldSpec] = []
    for key, spec in block.items():
        if not isinstance(spec, dict):
            continue
        title = spec.get("title") or key
        fields.append(
            ConfigFieldSpec(
                key=str(key),
                label=str(title),
                input_type="text",
                required=not bool(spec.get("optional")),
                secret=False,
                description=(
                    str(spec["description"])
                    if isinstance(spec.get("description"), str)
                    else None
                ),
                pattern=(
                    str(spec["pattern"])
                    if isinstance(spec.get("pattern"), str)
                    else None
                ),
            )
        )
    return fields


def _registry_credential_fields(raw: dict[str, Any]) -> list[ConfigFieldSpec]:
    block = raw.get("credentials")
    if not isinstance(block, dict):
        return []
    fields: list[ConfigFieldSpec] = []
    for key, spec in block.items():
        if not isinstance(spec, dict):
            continue
        title = spec.get("title") or key
        secret = bool(spec.get("secret"))
        fields.append(
            ConfigFieldSpec(
                key=str(key),
                label=str(title),
                input_type="password" if secret else "text",
                required=not bool(spec.get("optional")),
                secret=secret,
                description=(
                    str(spec["description"])
                    if isinstance(spec.get("description"), str)
                    else None
                ),
                pattern=(
                    str(spec["pattern"])
                    if isinstance(spec.get("pattern"), str)
                    else None
                ),
            )
        )
    return fields


def _registry_base_url(raw: dict[str, Any]) -> str | None:
    base = raw.get("base_url")
    if isinstance(base, str) and base.strip():
        return base.rstrip("/")
    proxy = raw.get("proxy")
    if isinstance(proxy, dict):
        proxy_base = proxy.get("base_url")
        if isinstance(proxy_base, str) and proxy_base.strip():
            return proxy_base.rstrip("/")
    return None


def _registry_proxy_headers(raw: dict[str, Any]) -> dict[str, str]:
    proxy = raw.get("proxy")
    if isinstance(proxy, dict):
        headers = proxy.get("headers")
        if isinstance(headers, dict):
            return {str(k): str(v) for k, v in headers.items()}
    headers = raw.get("headers")
    if isinstance(headers, dict):
        return {str(k): str(v) for k, v in headers.items()}
    return {}


def _check_from_registry(raw: dict[str, Any]) -> CheckEndpointSpec | None:
    proxy = raw.get("proxy")
    if not isinstance(proxy, dict):
        return None
    ver = proxy.get("verification")
    if not isinstance(ver, dict):
        return None
    endpoints = ver.get("endpoints")
    path = endpoints[0] if isinstance(endpoints, list) and endpoints else None
    if not isinstance(path, str) or not path.strip():
        return None
    method = str(ver.get("method") or "GET").upper()
    if method not in ("GET", "POST"):
        method = "GET"
    return CheckEndpointSpec(method=method, path=path)


def _display_name(bocp_mode: str, registry_mode: str) -> str:
    if registry_mode.upper().startswith("MCP_OAUTH2"):
        return "OAuth 2.0 (MCP)"
    return _BOCP_AUTH_DISPLAY_NAMES.get(bocp_mode, bocp_mode)


def _github_pat_api_key_spec(base_url: str = "https://api.github.com") -> AuthSpec:
    return AuthSpec(
        auth_mode="api_key",
        display_name=_BOCP_AUTH_DISPLAY_NAMES["api_key"],
        base_url=base_url,
        headers={"Authorization": "Bearer ${credentials.personal_access_token}"},
        credentials=[
            ConfigFieldSpec(
                key="personal_access_token",
                label="Personal Access Token",
                input_type="password",
                required=True,
                secret=True,
            )
        ],
        check=CheckEndpointSpec(
            method="GET",
            path="/user",
            account_id_path="id",
            display_name_path="login",
        ),
    )


def _slack_auth_fallback() -> list[AuthSpec]:
    return [
        AuthSpec(
            auth_mode="oauth2",
            display_name=_BOCP_AUTH_DISPLAY_NAMES["oauth2"],
            base_url="https://slack.com/api",
            headers={"Authorization": "Bearer ${credentials.access_token}"},
            oauth2=OAuth2DialectSpec(
                authorization_url="https://slack.com/oauth/v2/authorize",
                token_url="https://slack.com/api/oauth.v2.access",
                scopes=["channels:read", "chat:write", "reactions:write"],
            ),
            check=CheckEndpointSpec(
                method="POST",
                path="/auth.test",
                display_name_path="team",
            ),
        ),
        AuthSpec(
            auth_mode="api_key",
            display_name="Bot token",
            base_url="https://slack.com/api",
            headers={"Authorization": "Bearer ${credentials.bot_token}"},
            credentials=[
                ConfigFieldSpec(
                    key="bot_token",
                    label="Bot User OAuth Token",
                    input_type="password",
                    required=True,
                    secret=True,
                )
            ],
            check=CheckEndpointSpec(
                method="POST",
                path="/auth.test",
                display_name_path="team",
            ),
        ),
    ]


def auth_specs_from_registry_block(
    service: str, raw: dict[str, Any]
) -> list[AuthSpec] | None:
    """Convert one upstream registry provider block to BOCP auth specs."""
    registry_mode = str(raw.get("auth_mode") or "").upper()
    if not registry_mode:
        return None
    bocp_mode = registry_auth_mode_to_bocp(registry_mode)
    base_url = _registry_base_url(raw)
    conn_cfg = _registry_connection_config_fields(raw)
    cred_fields = _registry_credential_fields(raw)
    check = _check_from_registry(raw)
    label = _display_name(bocp_mode, registry_mode)

    if bocp_mode == "none":
        return [
            AuthSpec(
                auth_mode="none",
                display_name=label,
                base_url=base_url,
                check=check,
                connection_config=conn_cfg,
            )
        ]

    if bocp_mode == "oauth2":
        authorization_url = raw.get("authorization_url")
        token_url = raw.get("token_url")
        if not isinstance(authorization_url, str) or not isinstance(token_url, str):
            return None
        scopes = raw.get("scope") or raw.get("scopes") or []
        if isinstance(scopes, str):
            scopes = [s.strip() for s in scopes.split(",") if s.strip()]
        auth_params = raw.get("authorization_params")
        oauth2 = OAuth2DialectSpec(
            authorization_url=authorization_url,
            token_url=token_url,
            scopes=list(scopes) if isinstance(scopes, list) else [],
            pkce_s256=not raw.get("disable_pkce", False),
            authorization_params={
                str(k): str(v) for k, v in (auth_params or {}).items()
            }
            if isinstance(auth_params, dict)
            else {},
        )
        headers = _registry_proxy_headers(raw)
        if not headers and service in ("gitlab", "jira", "github", "slack"):
            headers = {"Authorization": "Bearer ${credentials.access_token}"}
        specs = [
            AuthSpec(
                auth_mode="oauth2",
                display_name=label,
                base_url=base_url,
                headers=headers,
                oauth2=oauth2,
                check=check,
                connection_config=conn_cfg,
                credentials=cred_fields,
            )
        ]
        if service == "slack":
            specs.extend(_slack_auth_fallback()[1:])
        elif service == "github":
            specs.append(_github_pat_api_key_spec(base_url or "https://api.github.com"))
        return specs

    if bocp_mode == "oauth2_cc":
        token_url = raw.get("token_url")
        if not isinstance(token_url, str) or not token_url.strip():
            return None
        scopes = raw.get("scope") or raw.get("scopes") or []
        if isinstance(scopes, str):
            scopes = [s.strip() for s in scopes.split(",") if s.strip()]
        oauth2 = OAuth2DialectSpec(
            token_url=token_url,
            scopes=list(scopes) if isinstance(scopes, list) else [],
            token_endpoint_auth_method="client_secret_post",
        )
        headers = _registry_proxy_headers(raw)
        if not headers:
            headers = {"Authorization": "Bearer ${credentials.access_token}"}
        return [
            AuthSpec(
                auth_mode="oauth2_cc",
                display_name=label,
                base_url=base_url,
                headers=headers,
                oauth2=oauth2,
                check=check,
                connection_config=conn_cfg,
                credentials=cred_fields,
            )
        ]

    if bocp_mode == "two_step":
        token_url = raw.get("token_url")
        if not isinstance(token_url, str) or not token_url.strip():
            return None
        token_response = raw.get("token_response")
        token_path = "access_token"
        if isinstance(token_response, dict) and token_response.get("token"):
            token_path = str(token_response["token"])
        two_step = TwoStepAuthSpec(
            token_url=token_url,
            method="POST",
            body_format="form",
            token_response_path=token_path,
        )
        headers = _registry_proxy_headers(raw)
        if not headers:
            headers = {"Authorization": "Bearer ${credentials.access_token}"}
        return [
            AuthSpec(
                auth_mode="two_step",
                display_name=label,
                base_url=base_url,
                headers=headers,
                two_step=two_step,
                check=check,
                connection_config=conn_cfg,
                credentials=cred_fields,
            )
        ]

    if bocp_mode == "basic":
        return [
            AuthSpec(
                auth_mode="basic",
                display_name=label,
                base_url=base_url,
                check=check,
                connection_config=conn_cfg,
                credentials=cred_fields,
            )
        ]

    if bocp_mode == "api_key":
        headers = _registry_proxy_headers(raw)
        if not headers:
            return None
        return [
            AuthSpec(
                auth_mode="api_key",
                display_name=label,
                base_url=base_url,
                headers=headers,
                check=check,
                connection_config=conn_cfg,
                credentials=cred_fields,
            )
        ]

    headers = _registry_proxy_headers(raw)
    if bocp_mode == "jwt" and not headers:
        headers = {"Authorization": "Bearer ${credentials.access_token}"}
    return [
        AuthSpec(
            auth_mode=bocp_mode,
            display_name=label,
            base_url=base_url,
            headers=headers,
            check=check,
            connection_config=conn_cfg,
            credentials=cred_fields,
        )
    ]


def auth_specs_from_providers_registry(service: str) -> list[AuthSpec] | None:
    """Best-effort upstream providers registry → BOCP auth."""
    raw = load_provider_registry_block(service)
    if raw is None:
        if service == "slack":
            return _slack_auth_fallback()
        return None
    specs = auth_specs_from_registry_block(service, raw)
    if specs is not None:
        return specs
    if service == "slack":
        return _slack_auth_fallback()
    return None
