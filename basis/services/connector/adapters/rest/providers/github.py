"""Shipped GitHub REST provider manifest (source for ``providers/github/``)."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_actions import (
    entity_action_from_stream,
    procedure_action_from_tool,
)
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    EntityActionSpec,
    OAuth2DialectSpec,
    PaginatorSpec,
    ProcedureActionSpec,
    RetrieverSpec,
    StreamFieldSpec,
    StreamMutationSpec,
    StreamSpec,
    ToolAnnotationsSpec,
    ToolSpec,
)


def _github_issues_entity() -> EntityActionSpec:
    stream = StreamSpec(
        name="issues",
        display_name="Repository Issues",
        primary_key=["id"],
        cursor_field="updated_at",
        default_label_field="title",
        fields=[
            StreamFieldSpec(
                name="id",
                data_type="integer",
                nullable=False,
                primary_key=True,
            ),
            StreamFieldSpec(name="number", data_type="integer", nullable=False),
            StreamFieldSpec(name="title", data_type="string", nullable=False),
            StreamFieldSpec(name="state", data_type="string"),
            StreamFieldSpec(name="body", data_type="string"),
            StreamFieldSpec(name="html_url", data_type="string"),
            StreamFieldSpec(name="updated_at", data_type="datetime"),
        ],
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/repos/{{config.owner}}/{{config.repo}}/issues",
            records_field_path=[],
            request_params={"state": "all"},
            incremental_cursor_param="since",
            paginator=PaginatorSpec(
                type="page",
                page_request_param="page",
                page_size=100,
                limit_param="per_page",
            ),
        ),
        mutations={
            "update": StreamMutationSpec(
                operation="update",
                adapter="rest_declarative",
                http_method="PATCH",
                path_template="/repos/{{config.owner}}/{{config.repo}}/issues/{{external_id}}",
                body_template={"patch": "{{patch}}"},
            ),
            "create": StreamMutationSpec(
                operation="create",
                adapter="rest_declarative",
                http_method="POST",
                path_template="/repos/{{config.owner}}/{{config.repo}}/issues",
                body_template={"patch": "{{patch}}"},
            ),
        },
    )
    return entity_action_from_stream(stream)


def _github_get_authenticated_user_procedure() -> ProcedureActionSpec:
    return procedure_action_from_tool(
        ToolSpec(
            id="get_authenticated_user",
            name="get_authenticated_user",
            description="Return the authenticated GitHub user (REST GET /user).",
            required_scopes=["read:user"],
            http_method="GET",
            path_template="/user",
            annotations=ToolAnnotationsSpec(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "login": {"type": "string"},
                },
            },
        )
    )


def github_manifest() -> ConnectorManifest:
    repositories = entity_action_from_stream(
        StreamSpec(
            name="repositories",
            display_name="Repositories",
            primary_key=["id"],
            cursor_field="updated_at",
            default_label_field="full_name",
            fields=[
                StreamFieldSpec(
                    name="id",
                    data_type="integer",
                    nullable=False,
                    primary_key=True,
                ),
                StreamFieldSpec(name="full_name", data_type="string", nullable=False),
                StreamFieldSpec(name="description", data_type="string"),
                StreamFieldSpec(name="html_url", data_type="string"),
                StreamFieldSpec(name="language", data_type="string"),
                StreamFieldSpec(name="stargazers_count", data_type="integer"),
                StreamFieldSpec(name="updated_at", data_type="datetime"),
            ],
            retriever=RetrieverSpec(
                adapter="rest_declarative",
                http_method="GET",
                path="/user/repos",
                records_field_path=[],
                paginator=PaginatorSpec(
                    type="page",
                    page_request_param="page",
                    page_size=100,
                    limit_param="per_page",
                ),
            ),
        )
    )
    return ConnectorManifest(
        service="github",
        display_name="GitHub",
        description="GitHub repositories, issues, pull requests, and organization members.",
        categories=["Developer Tools", "Engineering"],
        homepage_url="https://github.com",
        docs_url="https://docs.github.com/en/rest",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://api.github.com",
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://github.com/login/oauth/authorize",
                    token_url="https://github.com/login/oauth/access_token",
                    scopes=["repo", "read:org", "read:user"],
                ),
                check=CheckEndpointSpec(
                    method="GET",
                    path="/user",
                    account_id_path="id",
                    display_name_path="login",
                ),
            ),
            AuthSpec(
                auth_mode="api_key",
                base_url="https://api.github.com",
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
            ),
        ],
        actions=[
            repositories,
            _github_issues_entity(),
            _github_get_authenticated_user_procedure(),
        ],
    )
