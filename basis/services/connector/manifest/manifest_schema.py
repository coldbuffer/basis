"""Pydantic v2 contracts for BOCP — normative spec: docs/architecture/connectors/bocp.md (v2.0 manifest)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AuthModeLiteral = Literal[
    "none",
    "api_key",
    "basic",
    "two_step",
    "oauth2",
    "oauth2_cc",
    "oauth1",
    "jwt",
    "aws_sigv4",
    "app",
    "database_dsn",
    "custom",
]

FieldInputTypeLiteral = Literal[
    "text",
    "password",
    "number",
    "boolean",
    "select",
    "textarea",
    "json",
]


class BocpModel(BaseModel):
    """Base model: declared fields are strict, custom extensions use the ``x-`` prefix."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _reject_unknown_fields(self) -> "BocpModel":
        for key in self.model_extra or {}:
            if not key.startswith("x-"):
                raise ValueError(
                    f"Unknown field '{key}' on {type(self).__name__}; "
                    "custom extensions must use the 'x-' prefix"
                )
        return self


class ConfigFieldSpec(BocpModel):
    """Declarative field definition for connection_config or credentials."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    input_type: FieldInputTypeLiteral = "text"
    required: bool = True
    secret: bool = False
    default: str | int | bool | None = None
    placeholder: str | None = None
    description: str | None = None
    enum: list[str] | None = None
    pattern: str | None = None


class OAuthTokenResponseEnvelope(BocpModel):
    """Non-standard OAuth token response envelope extractor (e.g. Feishu/Notion dialects)."""

    data_field: str = Field(min_length=1)
    code_field: str | None = None
    success_code: int | str | None = None
    message_field: str | None = None


class OAuth2DialectSpec(BocpModel):
    """Declarative OAuth2 & OAuth2 Client Credentials parameters."""

    authorization_url: str | None = None
    token_url: str = Field(min_length=1)
    refresh_token_url: str | None = None
    scopes: list[str] = Field(default_factory=list)
    scope_separator: Literal[" ", ","] = " "
    token_endpoint_auth_method: Literal[
        "client_secret_basic", "client_secret_post", "none"
    ] = "client_secret_post"
    token_request_format: Literal["form", "json"] = "form"
    pkce_s256: bool = False
    authorization_params: dict[str, str] = Field(default_factory=dict)
    token_params: dict[str, str] = Field(default_factory=dict)
    token_response_envelope: OAuthTokenResponseEnvelope | None = None


class TwoStepAuthSpec(BocpModel):
    """Two-step username/password or key exchange for a session token."""

    token_url: str = Field(min_length=1)
    method: Literal["POST", "GET"] = "POST"
    body_format: Literal["form", "json"] = "json"
    token_params: dict[str, str] = Field(default_factory=dict)
    token_headers: dict[str, str] = Field(default_factory=dict)
    token_response_path: str = "access_token"
    token_expires_in_ms: int | None = None


class CheckEndpointSpec(BocpModel):
    """Declarative connection health check and account profile extractor (`CHECK` primitive)."""

    method: Literal["GET", "POST"] = "GET"
    path: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    account_id_path: str | None = "id"
    display_name_path: str | None = "name"
    scopes_path: str | None = None


class RateLimitQuotaSpec(BocpModel):
    """Adaptive rate-limit header tracking (Airbyte TokenQuota style)."""

    name: str = "default"
    remaining_header: str | None = "X-RateLimit-Remaining"
    reset_header: str | None = "X-RateLimit-Reset"
    limit_header: str | None = "X-RateLimit-Limit"
    retry_after_header: str | None = "Retry-After"


class AuthSpec(BocpModel):
    """Primitive 1: Authentication mode, connection config fields, and proxy headers."""

    auth_mode: AuthModeLiteral
    display_name: str | None = Field(
        default=None,
        min_length=1,
        description="Human label for this auth option in catalog and connection UI.",
    )
    base_url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    connection_config: list[ConfigFieldSpec] = Field(default_factory=list)
    credentials: list[ConfigFieldSpec] = Field(default_factory=list)
    oauth2: OAuth2DialectSpec | None = None
    two_step: TwoStepAuthSpec | None = None
    check: CheckEndpointSpec | None = None
    quotas: list[RateLimitQuotaSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_mode_requirements(self) -> AuthSpec:
        if self.auth_mode in ("oauth2", "oauth2_cc") and self.oauth2 is None:
            raise ValueError(
                f"auth_mode '{self.auth_mode}' requires an 'oauth2' block"
            )
        if self.auth_mode == "two_step" and self.two_step is None:
            raise ValueError("auth_mode 'two_step' requires a 'two_step' block")
        if self.auth_mode == "api_key" and not self.headers and not self.query_params:
            raise ValueError(
                "auth_mode 'api_key' requires an explicit auth.headers or "
                "auth.query_params placement"
            )
        return self


class PaginatorSpec(BocpModel):
    """Declarative pagination strategy (synthesizing Airbyte DefaultPaginator)."""

    type: Literal["none", "cursor", "offset", "page", "link"] = "none"
    page_size: int | None = 100
    limit_param: str | None = None
    inject_into: Literal["query", "body", "header"] = "query"
    # cursor pagination
    cursor_request_param: str | None = None
    cursor_response_path: str | None = None
    stop_condition_jinja: str | None = None
    # offset / page pagination
    offset_request_param: str | None = None
    page_request_param: str | None = None
    # link pagination
    link_header_rel: str | None = "next"
    link_response_path: str | None = None


class SubstreamPartitionSpec(BocpModel):
    """Parent-child stream routing (Airbyte SubstreamPartitionRouter)."""

    parent_stream: str = Field(min_length=1)
    parent_key: str = Field(min_length=1)
    partition_field: str = Field(min_length=1)


class RetrieverSpec(BocpModel):
    """Primitive 3: Declarative record extraction, pagination, and incremental sync (`READ`)."""

    adapter: Literal["rest_declarative", "sql_alchemy"] = "rest_declarative"
    path: str = ""
    http_method: Literal["GET", "POST"] = "GET"
    request_params: dict[str, str] = Field(default_factory=dict)
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body_json: dict[str, Any] | None = None
    records_field_path: list[str] = Field(default_factory=list)
    record_fields_unwrap_path: str | None = None
    record_filter_jinja: str | None = None
    paginator: PaginatorSpec = Field(default_factory=PaginatorSpec)
    partition_router: SubstreamPartitionSpec | None = None
    incremental_cursor_param: str | None = None
    incremental_cursor_inject: Literal["query", "body", "header"] = "query"


class DynamicSchemaLoaderSpec(BocpModel):
    """Runtime schema discovery for custom tables/objects (`DISCOVER` primitive)."""

    type: Literal["sql_inspector", "rest_metadata"] = "rest_metadata"
    container_stream: str | None = None
    metadata_path: str | None = None
    fields_field_path: list[str] = Field(default_factory=lambda: ["fields"])
    field_name_key: str = "name"
    field_type_key: str = "type"
    types_map: dict[str, str] = Field(default_factory=dict)


class StreamFieldSpec(BocpModel):
    """Normalized column/field descriptor returned by static or dynamic discovery."""

    name: str = Field(min_length=1)
    data_type: Literal[
        "string", "integer", "number", "boolean", "date", "datetime", "json", "array"
    ] = "string"
    nullable: bool = True
    primary_key: bool = False
    fk_target_stream: str | None = None
    description: str | None = None


class StreamMutationSpec(BocpModel):
    """Primitive 4a: Declarative write-back template bound to a stream (`MUTATE`)."""

    operation: Literal["create", "update", "upsert", "delete"] = "update"
    adapter: Literal["rest_declarative", "sql_alchemy"] = "rest_declarative"
    http_method: Literal["POST", "PUT", "PATCH", "DELETE"] = "PATCH"
    path_template: str = ""
    request_params: dict[str, str] = Field(default_factory=dict)
    request_headers: dict[str, str] = Field(default_factory=dict)
    body_template: dict[str, Any] = Field(default_factory=dict)


class StreamSpec(BocpModel):
    """Primitive 2: Business object / entity stream definition (`STREAM` & `DISCOVER`)."""

    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str | None = None
    primary_key: list[str] = Field(default_factory=lambda: ["id"])
    cursor_field: str | None = None
    default_label_field: str | None = None
    fields: list[StreamFieldSpec] = Field(default_factory=list)
    dynamic_schema_loader: DynamicSchemaLoaderSpec | None = None
    retriever: RetrieverSpec = Field(default_factory=RetrieverSpec)
    mutations: dict[Literal["create", "update", "upsert", "delete"], StreamMutationSpec] = (
        Field(default_factory=dict)
    )


class ToolAnnotationsSpec(BocpModel):
    """MCP-aligned tool safety and governance annotations."""

    read_only_hint: bool = True
    destructive_hint: bool = False
    idempotent_hint: bool = False


class ToolSpec(BocpModel):
    """Primitive 4b: Standalone RPC tool exposed via OpenAPI & Basis Python MCP."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    required_scopes: list[str] = Field(default_factory=list)
    annotations: ToolAnnotationsSpec = Field(default_factory=ToolAnnotationsSpec)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    http_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] | None = None
    path_template: str | None = None
    body_encoding: BodyEncodingLiteral = "json"
    mail_action: str | None = Field(
        default=None,
        description="When set, invoke runs via the mail (IMAP/SMTP) adapter.",
    )


ProviderProtocolLiteral = Literal["rest", "sql", "graphql", "grpc", "mail"]


class ProviderSpecReference(BocpModel):
    """Upstream protocol attachment(s) beside ``connector.yaml`` (paths relative to provider dir)."""

    protocol: ProviderProtocolLiteral = "rest"
    openapi: str | None = None
    graphql: str | None = None
    grpc: str | None = None


WriteOpLiteral = Literal["create", "update", "upsert", "delete"]

ENTITY_OPERATION_NAMES = frozenset({"list", "create", "update", "upsert", "delete"})
SQL_ENTITY_OPERATION_NAMES = ENTITY_OPERATION_NAMES | {"discover"}
INVOKE_OPERATION_NAME = "invoke"

HttpMethodLiteral = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class RestIncrementalSpec(BocpModel):
    """REST LIST incremental watermark: parameter name and injection target."""

    param: str = Field(min_length=1)
    inject_into: Literal["query", "body", "header"] = "query"


BodyEncodingLiteral = Literal["json", "form"]


class RestOperationSpec(BocpModel):
    """Single REST operation for the HTTP executor layer."""

    method: HttpMethodLiteral
    path: str = Field(min_length=1)
    query: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict[str, Any] | None = None
    body_encoding: BodyEncodingLiteral = "json"
    pagination: PaginatorSpec | None = None
    incremental: RestIncrementalSpec | None = None
    records: list[str] = Field(default_factory=list)


class RestEntityExecutorSpec(BocpModel):
    """REST executor configuration: all wire operations in one map."""

    operations: dict[str, RestOperationSpec]


class MailProcedureExecutorSpec(BocpModel):
    """IMAP/SMTP mail action name (OpenConnector mail/imap-smtp)."""

    action: str = Field(min_length=1)


class SqlEntityExecutorSpec(BocpModel):
    """SQL executor configuration (ORM / reflection); operation values are profile-specific."""

    operations: dict[str, Any]


class EntityActionSpec(BocpModel):
    """Entity action: schema metadata + protocol executor block (``rest`` or ``sql``)."""

    kind: Literal["entity"] = "entity"
    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str | None = None
    primary_key: list[str] = Field(default_factory=lambda: ["id"])
    cursor_field: str | None = None
    default_label_field: str | None = None
    fields: list[StreamFieldSpec] = Field(default_factory=list)
    rest: RestEntityExecutorSpec | None = None
    sql: SqlEntityExecutorSpec | None = None

    @model_validator(mode="after")
    def _one_executor(self) -> EntityActionSpec:
        if self.rest is not None and self.sql is not None:
            raise ValueError(f"Entity '{self.id}' cannot define both rest and sql")
        if self.rest is None and self.sql is None:
            raise ValueError(f"Entity '{self.id}' requires rest or sql executor block")
        if self.rest is not None:
            unknown = {
                key
                for key in self.rest.operations
                if key not in ENTITY_OPERATION_NAMES and not key.startswith("x-")
            }
            if unknown:
                raise ValueError(
                    f"Entity '{self.id}' has unsupported rest.operations keys "
                    f"{sorted(unknown)}; allowed: {sorted(ENTITY_OPERATION_NAMES)}"
                )
            if "list" not in self.rest.operations:
                raise ValueError(
                    f"Entity '{self.id}' rest.operations must include 'list'"
                )
        if self.sql is not None:
            unknown = {
                key
                for key in self.sql.operations
                if key not in SQL_ENTITY_OPERATION_NAMES and not key.startswith("x-")
            }
            if unknown:
                raise ValueError(
                    f"Entity '{self.id}' has unsupported sql.operations keys "
                    f"{sorted(unknown)}; allowed: {sorted(SQL_ENTITY_OPERATION_NAMES)}"
                )
            if "list" not in self.sql.operations:
                raise ValueError(
                    f"Entity '{self.id}' sql.operations must include 'list'"
                )
        return self


class ProcedureActionSpec(BocpModel):
    """Procedure action: INVOKE via protocol executor (typically ``rest.operations``)."""

    kind: Literal["procedure"] = "procedure"
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = ""
    required_scopes: list[str] = Field(default_factory=list)
    annotations: ToolAnnotationsSpec = Field(default_factory=ToolAnnotationsSpec)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    rest: RestEntityExecutorSpec | None = None
    mail: MailProcedureExecutorSpec | None = None

    @model_validator(mode="after")
    def _require_executor(self) -> ProcedureActionSpec:
        if (self.rest is None) == (self.mail is None):
            raise ValueError(
                f"Procedure '{self.id}' requires exactly one of rest or mail executor"
            )
        if self.rest is not None:
            operation_keys = {
                key for key in self.rest.operations if not key.startswith("x-")
            }
            if operation_keys != {INVOKE_OPERATION_NAME}:
                raise ValueError(
                    f"Procedure '{self.id}' rest.operations must contain exactly "
                    f"'{INVOKE_OPERATION_NAME}'"
                )
        return self


ActionSpec = EntityActionSpec | ProcedureActionSpec


def entity_to_stream_spec(entity: EntityActionSpec) -> StreamSpec:
    from basis.services.connector.manifest.manifest_executor import (
        entity_rest_to_stream_spec,
        entity_sql_to_stream_spec,
    )

    if entity.rest is not None:
        return entity_rest_to_stream_spec(entity, entity.rest)
    if entity.sql is not None:
        return entity_sql_to_stream_spec(entity, entity.sql)
    raise ValueError(f"Entity '{entity.id}' has no executor block")


def procedure_to_tool_spec(procedure: ProcedureActionSpec) -> ToolSpec:
    from basis.services.connector.manifest.manifest_executor import INVOKE_OPERATION

    if procedure.mail is not None:
        return ToolSpec(
            id=procedure.id,
            name=procedure.name,
            description=procedure.description,
            required_scopes=list(procedure.required_scopes),
            annotations=procedure.annotations,
            input_schema=dict(procedure.input_schema),
            output_schema=dict(procedure.output_schema),
            mail_action=procedure.mail.action,
        )
    assert procedure.rest is not None
    ops = procedure.rest.operations
    op = ops.get(INVOKE_OPERATION) or next(iter(ops.values()))
    http_method = op.method
    path_template = op.path
    return ToolSpec(
        id=procedure.id,
        name=procedure.name,
        description=procedure.description,
        required_scopes=list(procedure.required_scopes),
        annotations=procedure.annotations,
        input_schema=dict(procedure.input_schema),
        output_schema=dict(procedure.output_schema),
        http_method=http_method,
        path_template=path_template,
        body_encoding=op.body_encoding,
    )


class ConnectorManifest(BocpModel):
    """BOCP v2 provider manifest (``actions`` only on wire)."""

    @model_validator(mode="before")
    @classmethod
    def _inject_action_kind_on_wire(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        actions = data.get("actions")
        if not isinstance(actions, list):
            return data
        normalized: list[Any] = []
        for item in actions:
            if isinstance(item, dict) and "kind" not in item:
                if "input_schema" in item or "call" in item:
                    normalized.append({**item, "kind": "procedure"})
                else:
                    normalized.append({**item, "kind": "entity"})
            else:
                normalized.append(item)
        return {**data, "actions": normalized}

    version: Literal["2.0"] = "2.0"
    service: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1)
    description: str | None = None
    categories: list[str] = Field(default_factory=list)
    homepage_url: str | None = None
    docs_url: str | None = None
    icon_url: str | None = None
    spec: ProviderSpecReference | None = None
    auth: list[AuthSpec] = Field(min_length=1)
    actions: list[
        Annotated[EntityActionSpec | ProcedureActionSpec, Field(discriminator="kind")]
    ] = Field(default_factory=list)

    def entity_actions(self) -> list[EntityActionSpec]:
        return [a for a in self.actions if isinstance(a, EntityActionSpec)]

    def procedure_actions(self) -> list[ProcedureActionSpec]:
        return [a for a in self.actions if isinstance(a, ProcedureActionSpec)]

    def get_entity(self, action_id: str) -> EntityActionSpec:
        for action in self.entity_actions():
            if action.id == action_id:
                return action
        raise ValueError(
            f"Entity action '{action_id}' not found on service '{self.service}'"
        )

    def get_procedure(self, action_id: str) -> ProcedureActionSpec:
        for action in self.procedure_actions():
            if action.id == action_id or action.name == action_id:
                return action
        raise ValueError(
            f"Procedure action '{action_id}' not found on service '{self.service}'"
        )

    def stream_spec(self, action_id: str) -> StreamSpec:
        return entity_to_stream_spec(self.get_entity(action_id))

    def tool_spec(self, action_id: str) -> ToolSpec:
        return procedure_to_tool_spec(self.get_procedure(action_id))

    @property
    def streams(self) -> list[StreamSpec]:
        return [entity_to_stream_spec(e) for e in self.entity_actions()]

    @property
    def tools(self) -> list[ToolSpec]:
        return [procedure_to_tool_spec(p) for p in self.procedure_actions()]
