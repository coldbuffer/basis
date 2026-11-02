"""Shipped Jira Cloud REST provider (entity streams + AnyConnect procedure overlay)."""

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


def _jira_issues_entity():
    stream = StreamSpec(
        name="issues",
        display_name="Jira Issues",
        primary_key=["id"],
        cursor_field="fields.updated",
        default_label_field="fields.summary",
        fields=[
            StreamFieldSpec(name="id", data_type="string", nullable=False, primary_key=True),
            StreamFieldSpec(name="key", data_type="string", nullable=False),
            StreamFieldSpec(name="fields.summary", data_type="string"),
            StreamFieldSpec(name="fields.status.name", data_type="string"),
            StreamFieldSpec(name="fields.priority.name", data_type="string"),
            StreamFieldSpec(name="fields.updated", data_type="datetime"),
        ],
        retriever=RetrieverSpec(
            adapter="rest_declarative",
            http_method="GET",
            path="/ex/jira/{{config.cloudId}}/rest/api/3/search",
            records_field_path=["issues"],
            request_params={
                "jql": "project = {{config.projectKey}} ORDER BY updated DESC",
            },
            paginator=PaginatorSpec(
                type="offset",
                offset_request_param="startAt",
                page_size=50,
                limit_param="maxResults",
            ),
        ),
        mutations={
            "update": StreamMutationSpec(
                operation="update",
                adapter="rest_declarative",
                http_method="PUT",
                path_template="/ex/jira/{{config.cloudId}}/rest/api/3/issue/{{external_id}}",
                body_template={"fields": "{{patch}}"},
            ),
            "create": StreamMutationSpec(
                operation="create",
                adapter="rest_declarative",
                http_method="POST",
                path_template="/ex/jira/{{config.cloudId}}/rest/api/3/issue",
                body_template={"fields": "{{patch}}"},
            ),
        },
    )
    return entity_action_from_stream(stream)


def jira_manifest() -> ConnectorManifest:
    return ConnectorManifest(
        service="jira",
        display_name="Atlassian Jira",
        description="Jira Cloud issues and projects via OAuth (Atlassian API).",
        categories=["Project Management", "Engineering"],
        homepage_url="https://www.atlassian.com/software/jira",
        docs_url="https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://api.atlassian.com",
                headers={"Authorization": "Bearer ${credentials.access_token}"},
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://auth.atlassian.com/authorize",
                    token_url="https://auth.atlassian.com/oauth/token",
                    scopes=["offline_access"],
                    authorization_params={
                        "audience": "api.atlassian.com",
                        "prompt": "consent",
                    },
                ),
                connection_config=[
                    ConfigFieldSpec(
                        key="cloudId",
                        label="Cloud ID",
                        input_type="text",
                        required=True,
                        description="Atlassian cloud ID for API paths (from OAuth post-connection).",
                    ),
                    ConfigFieldSpec(
                        key="projectKey",
                        label="Project key",
                        input_type="text",
                        required=True,
                        description="Jira project key used in the issues stream JQL (e.g. PROJ).",
                    ),
                    ConfigFieldSpec(
                        key="subdomain",
                        label="Subdomain",
                        input_type="text",
                        required=False,
                        description="Optional Atlassian site subdomain.",
                    ),
                ],
                check=CheckEndpointSpec(
                    method="GET",
                    path="/ex/jira/{{config.cloudId}}/rest/api/3/myself",
                    account_id_path="accountId",
                    display_name_path="displayName",
                ),
            ),
        ],
        actions=[_jira_issues_entity()],
    )
