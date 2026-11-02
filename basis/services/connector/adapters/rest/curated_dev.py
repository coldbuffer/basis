"""REST flagship manifests for unit tests only (not shipped under providers/)."""
from __future__ import annotations

from typing import Any

from basis.services.connector.adapters.rest.providers.hubspot import hubspot_manifest
from basis.services.connector.adapters.rest.providers.jira import jira_manifest
from basis.services.connector.manifest.manifest_actions import (
    entity_action_from_stream,
    procedure_action_from_tool,
)
from basis.services.connector.manifest.manifest_schema import (
    AuthModeLiteral,
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    DynamicSchemaLoaderSpec,
    OAuth2DialectSpec,
    PaginatorSpec,
    RetrieverSpec,
    StreamFieldSpec,
    StreamMutationSpec,
    StreamSpec,
    SubstreamPartitionSpec,
    ToolAnnotationsSpec,
    ToolSpec,
)


def _curated_manifest(
    *,
    streams: list[StreamSpec] | None = None,
    tools: list[ToolSpec] | None = None,
    **kwargs: Any,
) -> ConnectorManifest:
    """Assemble an internal StreamSpec/ToolSpec collection as a v2 wire manifest."""
    actions: list[Any] = [entity_action_from_stream(s) for s in (streams or [])]
    actions.extend(procedure_action_from_tool(t) for t in (tools or []))
    return ConnectorManifest(version="2.0", actions=actions, **kwargs)


def curated_rest_manifests() -> dict[str, ConnectorManifest]:
    """Curated REST manifests (dev/tests only — not loaded from ``providers/``)."""
    airtable = _curated_manifest(
        service="airtable",
        display_name="Airtable",
        description="Airtable cloud relational bases, tables, and records with dynamic base/table schema discovery and bidirectional record sync.",
        categories=["Database", "Productivity"],
        homepage_url="https://airtable.com",
        docs_url="https://airtable.com/developers/web/api/introduction",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://api.airtable.com",
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://airtable.com/oauth2/v1/authorize",
                    token_url="https://airtable.com/oauth2/v1/token",
                    scopes=[
                        "data.records:read",
                        "data.records:write",
                        "schema.bases:read",
                    ],
                    pkce_s256=True,
                    token_endpoint_auth_method="client_secret_basic",
                ),
                check=CheckEndpointSpec(
                    method="GET",
                    path="/v0/meta/whoami",
                    account_id_path="id",
                    display_name_path="email",
                ),
            ),
            AuthSpec(
                auth_mode="api_key",
                base_url="https://api.airtable.com",
                headers={"Authorization": "Bearer ${credentials.api_key}"},
                credentials=[
                    ConfigFieldSpec(
                        key="api_key",
                        label="Personal Access Token",
                        input_type="password",
                        required=True,
                        secret=True,
                    )
                ],
                check=CheckEndpointSpec(
                    method="GET",
                    path="/v0/meta/whoami",
                    account_id_path="id",
                    display_name_path="email",
                ),
            ),
        ],
        streams=[
            StreamSpec(
                name="bases",
                display_name="Bases",
                description="Accessible Airtable bases.",
                primary_key=["id"],
                fields=[
                    StreamFieldSpec(name="id", data_type="string", nullable=False, primary_key=True),
                    StreamFieldSpec(name="name", data_type="string", nullable=False),
                    StreamFieldSpec(name="permissionLevel", data_type="string"),
                ],
                retriever=RetrieverSpec(
                    adapter="rest_declarative",
                    http_method="GET",
                    path="/v0/meta/bases",
                    records_field_path=["bases"],
                    paginator=PaginatorSpec(
                        type="cursor",
                        cursor_response_path="offset",
                        cursor_request_param="offset",
                    ),
                ),
            ),
            StreamSpec(
                name="records",
                display_name="Table Records",
                description="Records inside an Airtable base and table with dynamic schema introspection.",
                primary_key=["id"],
                cursor_field="createdTime",
                dynamic_schema_loader=DynamicSchemaLoaderSpec(
                    type="rest_metadata",
                    container_stream="bases",
                    metadata_path="/v0/meta/bases/{{config.base_id}}/tables",
                    fields_field_path=["tables", "fields"],
                ),
                retriever=RetrieverSpec(
                    adapter="rest_declarative",
                    http_method="GET",
                    path="/v0/{{config.base_id}}/{{config.table_id}}",
                    records_field_path=["records"],
                    record_fields_unwrap_path="fields",
                    paginator=PaginatorSpec(
                        type="cursor",
                        cursor_response_path="offset",
                        cursor_request_param="offset",
                        page_size=100,
                        limit_param="pageSize",
                    ),
                    partition_router=SubstreamPartitionSpec(
                        parent_stream="bases",
                        parent_key="id",
                        partition_field="base_id",
                    ),
                ),
                mutations={
                    "update": StreamMutationSpec(
                        operation="update",
                        adapter="rest_declarative",
                        http_method="PATCH",
                        path_template="/v0/{{config.base_id}}/{{config.table_id}}/{{external_id}}",
                        body_template={"fields": "{{patch}}"},
                    ),
                    "create": StreamMutationSpec(
                        operation="create",
                        adapter="rest_declarative",
                        http_method="POST",
                        path_template="/v0/{{config.base_id}}/{{config.table_id}}",
                        body_template={"fields": "{{patch}}"},
                    ),
                },
            ),
        ],
        tools=[
            ToolSpec(
                id="airtable.list_bases",
                name="list_bases",
                description="List all Airtable bases accessible by the connected account.",
                http_method="GET",
                path_template="/v0/meta/bases",
                annotations=ToolAnnotationsSpec(
                    read_only_hint=True,
                    destructive_hint=False,
                    idempotent_hint=True,
                ),
            ),
            ToolSpec(
                id="airtable.update_record",
                name="update_record",
                description="Patch fields on a single Airtable record.",
                http_method="PATCH",
                path_template="/v0/{{base_id}}/{{table_id}}/{{record_id}}",
                annotations=ToolAnnotationsSpec(
                    read_only_hint=False,
                    destructive_hint=False,
                    idempotent_hint=True,
                ),
            ),
        ],
    )

    hubspot = hubspot_manifest()

    notion = _curated_manifest(
        service="notion",
        display_name="Notion",
        description="Notion databases, pages, and structured database entries.",
        categories=["Productivity", "Knowledge Management"],
        homepage_url="https://www.notion.so",
        docs_url="https://developers.notion.com",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://api.notion.com",
                headers={"Notion-Version": "2022-06-28"},
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://api.notion.com/v1/oauth/authorize",
                    token_url="https://api.notion.com/v1/oauth/token",
                    token_endpoint_auth_method="client_secret_basic",
                    token_request_format="json",
                ),
                check=CheckEndpointSpec(
                    method="GET",
                    path="/v1/users/me",
                    account_id_path="id",
                    display_name_path="name",
                ),
            ),
            AuthSpec(
                auth_mode="api_key",
                base_url="https://api.notion.com",
                headers={
                    "Authorization": "Bearer ${credentials.integration_token}",
                    "Notion-Version": "2022-06-28",
                },
                credentials=[
                    ConfigFieldSpec(
                        key="integration_token",
                        label="Internal Integration Secret",
                        input_type="password",
                        required=True,
                        secret=True,
                    )
                ],
                check=CheckEndpointSpec(
                    method="GET",
                    path="/v1/users/me",
                    account_id_path="id",
                    display_name_path="name",
                ),
            ),
        ],
        streams=[
            StreamSpec(
                name="database_pages",
                display_name="Database Pages",
                primary_key=["id"],
                cursor_field="last_edited_time",
                dynamic_schema_loader=DynamicSchemaLoaderSpec(
                    type="rest_metadata",
                    metadata_path="/v1/databases/{{config.database_id}}",
                    fields_field_path=["properties"],
                ),
                retriever=RetrieverSpec(
                    adapter="rest_declarative",
                    http_method="POST",
                    path="/v1/databases/{{config.database_id}}/query",
                    records_field_path=["results"],
                    paginator=PaginatorSpec(
                        type="cursor",
                        inject_into="body",
                        cursor_response_path="next_cursor",
                        cursor_request_param="start_cursor",
                        page_size=100,
                        limit_param="page_size",
                    ),
                ),
                mutations={
                    "update": StreamMutationSpec(
                        operation="update",
                        adapter="rest_declarative",
                        http_method="PATCH",
                        path_template="/v1/pages/{{external_id}}",
                        body_template={"properties": "{{patch}}"},
                    ),
                },
            ),
        ],
    )

    jira = jira_manifest()

    return {m.service: m for m in [airtable, hubspot, notion, jira]}
