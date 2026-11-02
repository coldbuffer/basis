"""Pydantic models for named tool arguments and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.services.kernel.schema_base import ExtraAllowedModel


class ListConnectorCatalogInput(ExtraAllowedModel):
    query: str | None = Field(
        default=None,
        description="Filter by service key or display name",
    )
    limit: int | None = Field(
        default=None,
        description="Max rows (default 25, max 100)",
    )
    has_streams_only: bool | None = Field(
        default=None,
        description="Only providers with structured inbound streams",
    )


class DescribeConnectorServiceInput(ExtraAllowedModel):
    service: str = Field(
        min_length=1,
        description="Connector service key (e.g. postgres, github)",
    )


class ListConnectorConnectionsInput(ExtraAllowedModel):
    service: str | None = Field(
        default=None,
        description="Optional filter by connector service key",
    )
    connection_scope: Literal["workspace", "end_user"] | None = None
    subject_id: str | None = None


class UpsertConnectorConnectionInput(ExtraAllowedModel):
    service: str = Field(min_length=1, description="Connector service key")
    auth_type: str = Field(min_length=1)
    connection_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    connection_scope: Literal["workspace", "end_user"] = "workspace"
    subject_id: str | None = None


class DeleteConnectorConnectionInput(ExtraAllowedModel):
    service: str = Field(min_length=1)
    connection_scope: Literal["workspace", "end_user"] = "workspace"
    subject_id: str | None = None


class CheckConnectorConnectionInput(ExtraAllowedModel):
    service: str = Field(min_length=1)
    connection_scope: Literal["workspace", "end_user"] = "workspace"
    subject_id: str | None = None


class DiscoverConnectorSchemaInput(ExtraAllowedModel):
    service: str = Field(min_length=1)
    connection_scope: Literal["workspace", "end_user"] = "workspace"
    subject_id: str | None = None
    stream_name: str | None = None
    external_table: str | None = None


class ListConnectorTableMappingsInput(ExtraAllowedModel):
    limit: int | None = Field(
        default=None,
        description="Max mappings (default 50, max 200)",
    )


class SyncConnectorTableMappingInput(ExtraAllowedModel):
    mapping_id: str = Field(
        min_length=1,
        description="source_table_mappings id",
    )


class InvokeConnectorPrimitiveInput(ExtraAllowedModel):
    service: str = Field(
        min_length=1,
        description="Connector service key (e.g. github, postgres)",
    )
    action_id: str = Field(
        min_length=1,
        description="Entity or procedure action id from manifest actions[]",
    )
    primitive: Literal["discover", "list", "mutate", "invoke"]
    connection_scope: Literal["workspace", "end_user"] | None = None
    subject_id: str | None = Field(
        default=None,
        description="End-user id when connection_scope is end_user",
    )
    operation: str | None = Field(
        default=None,
        description="For mutate: create, update, upsert, or delete",
    )
    external_table: str | None = Field(
        default=None,
        description="SQL table name when required by the action",
    )
    external_id: Any = Field(
        default=None,
        description="External primary key for mutate (omit for create)",
    )
    changes: dict[str, Any] | None = Field(
        default=None,
        description="Field patch for mutate, or procedure payload when primitive is invoke",
    )
    action_params: dict[str, Any] | None = Field(
        default=None,
        description="Scope params (e.g. owner, repo) merged into {{config.*}} templates",
    )
    arguments: dict[str, Any] | None = Field(
        default=None,
        description="Alias for procedure invoke payload",
    )
    limit: int | None = Field(
        default=None,
        description="Max records for list (default 500, max 5000)",
    )
    cursor_watermark: Any = Field(
        default=None,
        description="Incremental cursor for list",
    )
    primary_key_column: str | None = None
    cursor_column: str | None = None


class ExecuteConnectorToolInput(ExtraAllowedModel):
    service: str = Field(min_length=1, description="Connector service key")
    tool_id: str = Field(min_length=1, description="Tool id from manifest tools[]")
    connection_scope: Literal["workspace", "end_user"] | None = None
    subject_id: str | None = None
    arguments: dict[str, Any] | None = Field(
        default=None,
        description="Tool input payload per manifest input_schema",
    )


class ProposeEntityWritebackInput(ExtraAllowedModel):
    entity_id: str = Field(min_length=1)
    field_updates: dict[str, Any] = Field(min_length=1)


TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "check_connector_connection": CheckConnectorConnectionInput,
    "delete_connector_connection": DeleteConnectorConnectionInput,
    "describe_connector_service": DescribeConnectorServiceInput,
    "discover_connector_schema": DiscoverConnectorSchemaInput,
    "execute_connector_tool": ExecuteConnectorToolInput,
    "invoke_connector_primitive": InvokeConnectorPrimitiveInput,
    "list_connector_catalog": ListConnectorCatalogInput,
    "list_connector_connections": ListConnectorConnectionsInput,
    "list_connector_table_mappings": ListConnectorTableMappingsInput,
    "propose_entity_writeback": ProposeEntityWritebackInput,
    "sync_connector_table_mapping": SyncConnectorTableMappingInput,
    "upsert_connector_connection": UpsertConnectorConnectionInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {}
