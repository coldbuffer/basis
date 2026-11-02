"""Shipped Slack REST provider (procedure-first; Batch 1 collaboration)."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_actions import procedure_action_from_tool
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    BodyEncodingLiteral,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    OAuth2DialectSpec,
    ProcedureActionSpec,
    ToolAnnotationsSpec,
    ToolSpec,
)


def _slack_procedure(
    *,
    action_id: str,
    name: str,
    description: str,
    scopes: list[str],
    method: str,
    path: str,
    input_schema: dict,
    output_schema: dict,
    read_only: bool,
    body_encoding: BodyEncodingLiteral = "form",
) -> ProcedureActionSpec:
    return procedure_action_from_tool(
        ToolSpec(
            id=action_id,
            name=name,
            description=description,
            required_scopes=scopes,
            http_method=method,
            path_template=path,
            body_encoding=body_encoding,
            annotations=ToolAnnotationsSpec(
                read_only_hint=read_only,
                destructive_hint=False,
                idempotent_hint=read_only,
            ),
            input_schema=input_schema,
            output_schema=output_schema,
        )
    )


def slack_manifest() -> ConnectorManifest:
    procedures = [
        _slack_procedure(
            action_id="slack.add_reaction",
            name="add_reaction",
            description="Add an emoji reaction to a Slack message.",
            scopes=["reactions:write"],
            method="POST",
            path="/reactions.add",
            read_only=False,
            input_schema={
                "type": "object",
                "properties": {
                    "channelId": {"type": "string", "minLength": 1},
                    "messageTs": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1},
                },
                "required": ["channelId", "messageTs", "name"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
        ),
        _slack_procedure(
            action_id="slack.post_message",
            name="post_message",
            description="Send a message to a Slack channel.",
            scopes=["chat:write"],
            method="POST",
            path="/chat.postMessage",
            read_only=False,
            input_schema={
                "type": "object",
                "properties": {
                    "channelId": {"type": "string", "minLength": 1},
                    "text": {"type": "string", "minLength": 1},
                    "threadTs": {"type": "string"},
                },
                "required": ["channelId", "text"],
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "ts": {"type": "string"},
                    "channel": {"type": "string"},
                },
                "required": ["ok"],
            },
        ),
        _slack_procedure(
            action_id="slack.conversations_list",
            name="conversations_list",
            description="List public channels in the workspace.",
            scopes=["channels:read"],
            method="GET",
            path="/conversations.list",
            read_only=True,
            body_encoding="json",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "cursor": {"type": "string"},
                },
                "additionalProperties": False,
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "channels": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["ok"],
            },
        ),
    ]
    return ConnectorManifest(
        service="slack",
        display_name="Slack",
        description="Slack messaging and channels (procedure actions; POST uses form-urlencoded bodies).",
        categories=["Communication", "Productivity"],
        homepage_url="https://slack.com",
        docs_url="https://api.slack.com",
        auth=[
            AuthSpec(
                auth_mode="oauth2",
                base_url="https://slack.com/api",
                headers={"Authorization": "Bearer ${credentials.access_token}"},
                oauth2=OAuth2DialectSpec(
                    authorization_url="https://slack.com/oauth/v2/authorize",
                    token_url="https://slack.com/api/oauth.v2.access",
                    scopes=[
                        "channels:read",
                        "channels:history",
                        "chat:write",
                        "reactions:write",
                    ],
                ),
                check=CheckEndpointSpec(
                    method="POST",
                    path="/auth.test",
                    display_name_path="team",
                ),
            ),
            AuthSpec(
                auth_mode="api_key",
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
        ],
        actions=procedures,
    )
