"""BOCP v2 conformance guards: schema strictness, interpolation, auth placement."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from basis.services.connector.vault.auth_vault import (
    ConnectorAuthVault,
    StoredConnection,
    interpolate_placeholders,
)
from basis.services.connector.manifest.manifest_executor import (
    rest_operation_to_mutation,
    rest_operation_to_retriever,
)
from basis.services.connector.manifest.manifest_schema import (
    ConnectorManifest,
    RestIncrementalSpec,
    RestOperationSpec,
)
from basis.services.connector.manifest.provider_bundle import (
    load_provider_bundle,
    write_provider_bundle,
)


def _rest_list() -> dict[str, Any]:
    return {"method": "GET", "path": "/items"}


def _manifest_raw(**overrides: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "version": "2.0",
        "service": "demo",
        "display_name": "Demo",
        "auth": [{"auth_mode": "none"}],
        "actions": [
            {
                "kind": "entity",
                "id": "items",
                "display_name": "Items",
                "rest": {"operations": {"list": _rest_list()}},
            }
        ],
    }
    raw.update(overrides)
    return raw


def test_x_prefixed_extensions_are_allowed_unknown_fields_are_not() -> None:
    manifest = ConnectorManifest.model_validate(
        {**_manifest_raw(), "x-vendor": {"region": "eu"}}
    )
    assert manifest.model_extra == {"x-vendor": {"region": "eu"}}

    with pytest.raises(ValidationError, match="x-"):
        ConnectorManifest.model_validate({**_manifest_raw(), "vendor_region": "eu"})


def test_entity_operation_keys_are_closed_and_list_is_required() -> None:
    create_only = _manifest_raw()
    create_only["actions"][0]["rest"]["operations"] = {
        "create": {"method": "POST", "path": "/items"}
    }
    with pytest.raises(ValidationError, match="include 'list'"):
        ConnectorManifest.model_validate(create_only)

    unknown_key = _manifest_raw()
    unknown_key["actions"][0]["rest"]["operations"] = {
        "list": _rest_list(),
        "fetch": {"method": "GET", "path": "/items/fetch"},
    }
    with pytest.raises(ValidationError, match="unsupported rest.operations keys"):
        ConnectorManifest.model_validate(unknown_key)

    sql_unknown = _manifest_raw()
    sql_unknown["actions"][0].pop("rest")
    sql_unknown["actions"][0]["sql"] = {"operations": {"list": {}, "read": {}}}
    with pytest.raises(ValidationError, match="unsupported sql.operations keys"):
        ConnectorManifest.model_validate(sql_unknown)

    extended = _manifest_raw()
    extended["actions"][0]["rest"]["operations"]["x-vendor-hint"] = {
        "method": "GET",
        "path": "/hint",
    }
    ConnectorManifest.model_validate(extended)


def test_procedure_requires_exactly_the_invoke_operation() -> None:
    procedure = _manifest_raw(
        actions=[
            {
                "kind": "procedure",
                "id": "search",
                "name": "search",
                "display_name": "Search",
                "rest": {
                    "operations": {
                        "invoke": {"method": "POST", "path": "/search"},
                    }
                },
            }
        ]
    )
    ConnectorManifest.model_validate(procedure)

    wrong_key = _manifest_raw(
        actions=[
            {
                "kind": "procedure",
                "id": "search",
                "name": "search",
                "display_name": "Search",
                "rest": {
                    "operations": {
                        "call": {"method": "POST", "path": "/search"},
                    }
                },
            }
        ]
    )
    with pytest.raises(ValidationError, match="exactly 'invoke'"):
        ConnectorManifest.model_validate(wrong_key)


def test_interpolation_connection_config_wins_and_path_values_are_encoded() -> None:
    resolved = interpolate_placeholders(
        "/repos/{{config.owner}}/{{config.repo}}/{{external_id}}",
        connection_config={"owner": "acme"},
        stream_params={"owner": "attacker", "repo": "demo"},
        extra={"external_id": "a/b?c"},
        url_encode_values=True,
    )
    assert resolved == "/repos/acme/demo/a%2Fb%3Fc"


def test_interpolation_rejects_dot_segments_in_paths() -> None:
    with pytest.raises(ValueError, match="Unsafe URL path placeholder value"):
        interpolate_placeholders(
            "/repos/{{config.owner}}/issues",
            stream_params={"owner": ".."},
            url_encode_values=True,
        )


def test_interpolation_rejects_unresolved_placeholders() -> None:
    with pytest.raises(ValueError, match="Unresolved connector placeholder"):
        interpolate_placeholders("/repos/{{config.missing}}/issues")

    # Bare {{KEY}} remains the placeholder form for procedure arguments.
    assert (
        interpolate_placeholders(
            "https://{{config.domain}}.example.com/{{base_id}}",
            connection_config={"domain": "acme"},
            stream_params={"base_id": "app1"},
        )
        == "https://acme.example.com/app1"
    )


def _vault_and_manifest(
    auth_raw: dict[str, Any],
) -> tuple[ConnectorAuthVault, ConnectorManifest]:
    vault = ConnectorAuthVault(sqlite3.connect(":memory:"), vault_secret="test")
    manifest = ConnectorManifest.model_validate(_manifest_raw(auth=[auth_raw]))
    return vault, manifest


def test_api_key_auth_requires_explicit_header_or_query_placement() -> None:
    with pytest.raises(ValidationError, match="explicit auth.headers or auth.query_params"):
        _vault_and_manifest(
            {
                "auth_mode": "api_key",
                "base_url": "https://api.example.com",
                "credentials": [
                    {"key": "api_key", "label": "API Key", "secret": True},
                ],
            }
        )

    connection = StoredConnection(
        workspace_id="kb1",
        service="demo",
        auth_type="api_key",
        connection_config={},
        credentials={"api_key": "secret"},
    )
    vault, manifest = _vault_and_manifest(
        {
            "auth_mode": "api_key",
            "base_url": "https://api.example.com",
            "headers": {"X-API-Key": "${credentials.api_key}"},
            "credentials": [
                {"key": "api_key", "label": "API Key", "secret": True},
            ],
        }
    )
    _, headers, _ = vault.build_request_auth(manifest, connection)
    assert headers == {"X-API-Key": "secret"}


def test_rest_openapi_attachment_is_optional(tmp_path: Path) -> None:
    manifest = ConnectorManifest.model_validate(
        _manifest_raw(spec={"protocol": "rest"})
    )
    write_provider_bundle(tmp_path, manifest)

    assert not (tmp_path / "demo.openapi.yaml").exists()
    loaded = load_provider_bundle(tmp_path / "demo.yaml")
    assert loaded.paths.protocol == "rest"
    assert loaded.paths.openapi is None


def test_incremental_cursor_injection_target_is_compiled() -> None:
    retriever = rest_operation_to_retriever(
        RestOperationSpec(
            method="POST",
            path="/items",
            incremental=RestIncrementalSpec(param="since", inject_into="header"),
        )
    )
    assert retriever.incremental_cursor_param == "since"
    assert retriever.incremental_cursor_inject == "header"


def test_mutation_operations_keep_query_and_headers() -> None:
    mutation = rest_operation_to_mutation(
        RestOperationSpec(
            method="PATCH",
            path="/items/{{external_id}}",
            query={"tenant": "{{config.tenant}}"},
            headers={"X-Tenant": "{{config.tenant}}"},
        ),
        "update",
    )
    assert mutation.request_params == {"tenant": "{{config.tenant}}"}
    assert mutation.request_headers == {"X-Tenant": "{{config.tenant}}"}
