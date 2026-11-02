"""Shipped Notion REST provider (entity + dynamic schema; Batch 1)."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_actions import entity_action_from_stream
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    DynamicSchemaLoaderSpec,
    OAuth2DialectSpec,
    PaginatorSpec,
    RetrieverSpec,
    StreamMutationSpec,
    StreamSpec,
)


def _database_pages_entity() -> EntityActionSpec:
    stream = StreamSpec(
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
    )
    return entity_action_from_stream(stream)


def notion_manifest() -> ConnectorManifest:
    return ConnectorManifest(
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
        actions=[_database_pages_entity()],
    )
