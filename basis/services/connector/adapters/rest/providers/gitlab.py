"""Shipped GitLab REST provider (entity streams + AnyConnect procedure overlay)."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_actions import entity_action_from_stream
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    OAuth2DialectSpec,
    PaginatorSpec,
    RetrieverSpec,
    StreamFieldSpec,
    StreamMutationSpec,
    StreamSpec,
)


def _gitlab_projects_entity():
    stream = StreamSpec(
        name="projects",
        display_name="Projects",
        primary_key=["id"],
        cursor_field="last_activity_at",
        default_label_field="path_with_namespace",
        fields=[
            StreamFieldSpec(name="id", data_type="integer", nullable=False, primary_key=True),
            StreamFieldSpec(name="name", data_type="string"),
            StreamFieldSpec(name="path_with_namespace", data_type="string"),
            StreamFieldSpec(name="description", data_type="string"),
            StreamFieldSpec(name="web_url", data_type="string"),
            StreamFieldSpec(name="last_activity_at", data_type="datetime"),
        ],
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/api/v4/projects",
            records_field_path=[],
            request_params={"membership": "true"},
            paginator=PaginatorSpec(
                type="page",
                page_request_param="page",
                page_size=100,
                limit_param="per_page",
            ),
        ),
    )
    return entity_action_from_stream(stream)


def _gitlab_project_issues_entity():
    stream = StreamSpec(
        name="project_issues",
        display_name="Project Issues",
        primary_key=["id"],
        cursor_field="updated_at",
        default_label_field="title",
        fields=[
            StreamFieldSpec(name="id", data_type="integer", nullable=False, primary_key=True),
            StreamFieldSpec(name="iid", data_type="integer", nullable=False),
            StreamFieldSpec(name="title", data_type="string", nullable=False),
            StreamFieldSpec(name="state", data_type="string"),
            StreamFieldSpec(name="description", data_type="string"),
            StreamFieldSpec(name="web_url", data_type="string"),
            StreamFieldSpec(name="updated_at", data_type="datetime"),
        ],
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/api/v4/projects/{{config.projectId}}/issues",
            records_field_path=[],
            request_params={"state": "all"},
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
                http_method="PUT",
                path_template="/api/v4/projects/{{config.projectId}}/issues/{{external_id}}",
                body_template={"patch": "{{patch}}"},
            ),
            "create": StreamMutationSpec(
                operation="create",
                adapter="rest_declarative",
                http_method="POST",
                path_template="/api/v4/projects/{{config.projectId}}/issues",
                body_template={"patch": "{{patch}}"},
            ),
        },
    )
    return entity_action_from_stream(stream)


def gitlab_manifest() -> ConnectorManifest:
    return ConnectorManifest(
        service="gitlab",
        display_name="GitLab",
        description="GitLab projects, issues, and merge requests.",
        categories=["Developer Tools", "Engineering"],
        homepage_url="https://gitlab.com",
        docs_url="https://docs.gitlab.com/ee/api/api_resources.html",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://gitlab.com",
                headers={"Authorization": "Bearer ${credentials.access_token}"},
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://gitlab.com/oauth/authorize",
                    token_url="https://gitlab.com/oauth/token",
                    pkce_s256=True,
                    authorization_params={"response_type": "code"},
                ),
                connection_config=[
                    ConfigFieldSpec(
                        key="projectId",
                        label="Project ID or URL-encoded path",
                        input_type="text",
                        required=False,
                        description="Required for the project issues stream (e.g. 123 or group%2Fproject).",
                    ),
                ],
                check=CheckEndpointSpec(
                    method="GET",
                    path="/api/v4/user",
                    display_name_path="username",
                ),
            ),
        ],
        actions=[_gitlab_projects_entity(), _gitlab_project_issues_entity()],
    )
