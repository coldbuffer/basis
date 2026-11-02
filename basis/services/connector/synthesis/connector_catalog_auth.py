"""OpenConnector / connector ``catalog/apps/*.json`` → BOCP ``auth[]``."""

from __future__ import annotations

from typing import Any

from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    ConfigFieldSpec,
    OAuth2DialectSpec,
)


def _credential_field(spec: dict[str, Any]) -> ConfigFieldSpec:
    key = str(spec.get("key") or "value")
    raw_input = spec.get("inputType") or spec.get("input_type")
    if isinstance(raw_input, str) and raw_input in ("text", "password"):
        input_type = raw_input
    else:
        input_type = "password" if spec.get("secret") else "text"
    return ConfigFieldSpec(
        key=key,
        label=str(spec.get("label") or key),
        input_type=input_type,
        required=bool(spec.get("required", True)),
        secret=bool(spec.get("secret")),
        description=(
            str(spec["description"]) if isinstance(spec.get("description"), str) else None
        ),
        placeholder=(
            str(spec["placeholder"]) if isinstance(spec.get("placeholder"), str) else None
        ),
    )


def auth_specs_from_connector_app(app: dict[str, Any], *, service: str) -> list[AuthSpec]:
    """Map connector catalog app JSON (OpenConnector export) to BOCP auth specs."""
    blocks = app.get("auth")
    if not isinstance(blocks, list) or not blocks:
        return []

    app_label = str(
        app.get("displayName") or app.get("display_name") or service.replace("_", " ")
    ).strip()

    specs: list[AuthSpec] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "").strip().lower()
        if kind == "oauth2":
            auth_url = block.get("authorizationUrl") or block.get("authorization_url")
            token_url = block.get("tokenUrl") or block.get("token_url")
            if not isinstance(auth_url, str) or not isinstance(token_url, str):
                continue
            scopes = block.get("scopes") or []
            if not isinstance(scopes, list):
                scopes = []
            method = str(
                block.get("tokenEndpointAuthMethod")
                or block.get("token_endpoint_auth_method")
                or "client_secret_post"
            )
            if method not in ("client_secret_basic", "client_secret_post", "none"):
                method = "client_secret_post"
            extra_fields = block.get("extraFields") or block.get("extra_fields") or []
            credentials = [
                _credential_field(f) for f in extra_fields if isinstance(f, dict)
            ]
            specs.append(
                AuthSpec(
                    auth_mode="oauth2",
                    display_name=str(block.get("label") or "OAuth 2.0"),
                    headers={"Authorization": "Bearer ${credentials.access_token}"},
                    oauth2=OAuth2DialectSpec(
                        authorization_url=auth_url,
                        token_url=token_url,
                        scopes=[str(s) for s in scopes],
                        token_endpoint_auth_method=method,
                    ),
                    credentials=credentials,
                )
            )
        elif kind == "api_key":
            label = str(block.get("label") or "API key / token")
            cred_key = "api_key"
            headers = {"Authorization": "Bearer ${credentials.api_key}"}
            if service == "github":
                cred_key = "personal_access_token"
                headers = {"Authorization": "Bearer ${credentials.personal_access_token}"}
            extra = block.get("extraFields") or block.get("extra_fields") or []
            credentials = [
                ConfigFieldSpec(
                    key=cred_key,
                    label=label,
                    input_type="password",
                    required=True,
                    secret=True,
                    description=(
                        str(block["description"])
                        if isinstance(block.get("description"), str)
                        else None
                    ),
                    placeholder=(
                        str(block["placeholder"])
                        if isinstance(block.get("placeholder"), str)
                        else None
                    ),
                )
            ]
            credentials.extend(
                _credential_field(f) for f in extra if isinstance(f, dict)
            )
            specs.append(
                AuthSpec(
                    auth_mode="api_key",
                    display_name=label,
                    headers=headers,
                    credentials=credentials,
                )
            )
        elif kind in ("no_auth", "none"):
            specs.append(
                AuthSpec(
                    auth_mode="none",
                    display_name=str(block.get("label") or "No authentication"),
                )
            )
        elif kind == "custom_credential":
            fields = block.get("fields") or []
            if not isinstance(fields, list):
                fields = []
            specs.append(
                AuthSpec(
                    auth_mode="custom",
                    display_name=str(block.get("label") or f"{app_label} credentials"),
                    credentials=[
                        _credential_field(f) for f in fields if isinstance(f, dict)
                    ],
                )
            )
    return specs
