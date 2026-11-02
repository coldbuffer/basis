"""Dynamic MCP tools derived from BOCP manifest ``actions[]`` (per-workspace tools/list)."""

from __future__ import annotations

from typing import Any

from basis.services.connector import get_connector_catalog
from basis.services.connector.vault.auth_vault import ConnectorPolicy
from basis.services.connector.manifest.manifest_schema import (
    ConnectorManifest,
    EntityActionSpec,
    ProcedureActionSpec,
)
from basis.services.kernel import WorkspaceCoreContext
from basis.mcp.connector_mcp_tool_name import (
    CONNECTOR_TOOL_PREFIX,
    MutateOpLiteral,
    _MUTATE_OPS,
    connector_mcp_tool_name,
    parse_connector_mcp_tool_name,
)


def _connection_scope_properties() -> dict[str, Any]:
    return {
        "connection_scope": {
            "type": "string",
            "enum": ["workspace", "end_user"],
            "description": "Use end_user with subject_id for per-user (embed) vault rows",
        },
        "subject_id": {
            "type": "string",
            "description": "End-user id when connection_scope is end_user",
        },
    }


def _action_params_property() -> dict[str, Any]:
    return {
        "type": "object",
        "description": "Scope params (e.g. owner, repo) merged into {{config.*}} templates",
    }


def _list_input_schema(*, sql: bool) -> dict[str, Any]:
    props: dict[str, Any] = {
        **_connection_scope_properties(),
        "action_params": _action_params_property(),
        "limit": {
            "type": "integer",
            "description": "Max records for this call (default 500, max 5000)",
        },
        "cursor_watermark": {"description": "Incremental cursor for list"},
    }
    if sql:
        props["external_table"] = {
            "type": "string",
            "description": "Table name when required by the SQL action",
        }
        props["primary_key_column"] = {"type": "string"}
        props["cursor_column"] = {"type": "string"}
    return {"type": "object", "properties": props}


def _discover_input_schema(*, sql: bool) -> dict[str, Any]:
    props: dict[str, Any] = {
        **_connection_scope_properties(),
        "action_params": _action_params_property(),
    }
    if sql:
        props["external_table"] = {
            "type": "string",
            "description": "Table name when required by the SQL action",
        }
    return {"type": "object", "properties": props}


def _mutate_input_schema(
    operation: str,
    *,
    sql: bool,
) -> dict[str, Any]:
    props: dict[str, Any] = {
        **_connection_scope_properties(),
        "action_params": _action_params_property(),
        "changes": {
            "type": "object",
            "description": "Field patch for mutate",
        },
    }
    if sql:
        props["external_table"] = {
            "type": "string",
            "description": "Table name when required by the SQL action",
        }
    if operation != "create":
        props["external_id"] = {
            "description": "External primary key for mutate (omit for create)",
        }
    return {"type": "object", "properties": props}


def _invoke_input_schema(procedure: ProcedureActionSpec) -> dict[str, Any]:
    arg_schema = procedure.input_schema if procedure.input_schema else {"type": "object"}
    return {
        "type": "object",
        "properties": {
            **_connection_scope_properties(),
            "arguments": {
                **arg_schema,
                "description": "Procedure payload per manifest input_schema",
            },
            "changes": {
                "type": "object",
                "description": "Alias for arguments",
            },
        },
    }


def _entity_operation_keys(entity: EntityActionSpec) -> set[str]:
    if entity.rest is not None:
        return {k for k in entity.rest.operations if not k.startswith("x-")}
    if entity.sql is not None:
        return {k for k in entity.sql.operations if not k.startswith("x-")}
    return set()


def _is_sql_entity(entity: EntityActionSpec) -> bool:
    return entity.sql is not None


def _primitive_disabled(
    policy: ConnectorPolicy,
    service: str,
    action_id: str,
    primitive: str,
    *,
    operation: str | None = None,
) -> bool:
    return (
        policy.resolve_primitive_execution_mode(
            service,
            action_id,
            primitive,
            operation=operation,
        )
        == "disabled"
    )


def _tool_description(
    manifest: ConnectorManifest,
    action_label: str,
    action_id: str,
    primitive: str,
    *,
    operation: str | None = None,
    detail: str | None = None,
) -> str:
    verb = primitive
    if primitive == "mutate" and operation:
        verb = f"mutate {operation}"
    parts = [
        f"BOCP {verb} for {manifest.display_name} ({manifest.service}) "
        f"action '{action_id}' ({action_label}).",
    ]
    if detail:
        parts.append(detail.strip())
    parts.append(
        "Same runtime as invoke_connector_primitive; use connection_scope end_user + "
        "subject_id for embed per-user connections; workspace scope uses default vault row."
    )
    return " ".join(parts)


def connector_tool_definitions_for_manifest(
    manifest: ConnectorManifest,
    policy: ConnectorPolicy,
) -> list[dict[str, Any]]:
    """Build MCP tool metadata for one provider manifest (policy-filtered)."""
    if not policy.is_provider_allowed(manifest.service):
        return []
    tools: list[dict[str, Any]] = []
    service = manifest.service

    for action in manifest.actions:
        if isinstance(action, EntityActionSpec):
            op_keys = _entity_operation_keys(action)
            sql = _is_sql_entity(action)
            if "discover" in op_keys and not _primitive_disabled(
                policy, service, action.id, "discover"
            ):
                tools.append(
                    {
                        "name": connector_mcp_tool_name(
                            service, action.id, "discover"
                        ),
                        "description": _tool_description(
                            manifest,
                            action.display_name,
                            action.id,
                            "discover",
                            detail=action.description,
                        ),
                        "inputSchema": _discover_input_schema(sql=sql),
                    }
                )
            if "list" in op_keys and not _primitive_disabled(
                policy, service, action.id, "list"
            ):
                tools.append(
                    {
                        "name": connector_mcp_tool_name(service, action.id, "list"),
                        "description": _tool_description(
                            manifest,
                            action.display_name,
                            action.id,
                            "list",
                            detail=action.description,
                        ),
                        "inputSchema": _list_input_schema(sql=sql),
                    }
                )
            for op in _MUTATE_OPS:
                if op not in op_keys:
                    continue
                if _primitive_disabled(
                    policy, service, action.id, "mutate", operation=op
                ):
                    continue
                tools.append(
                    {
                        "name": connector_mcp_tool_name(
                            service, action.id, "mutate", operation=op
                        ),
                        "description": _tool_description(
                            manifest,
                            action.display_name,
                            action.id,
                            "mutate",
                            operation=op,
                            detail=action.description,
                        ),
                        "inputSchema": _mutate_input_schema(op, sql=sql),
                    }
                )
        elif isinstance(action, ProcedureActionSpec):
            if _primitive_disabled(policy, service, action.id, "invoke"):
                continue
            tools.append(
                {
                    "name": connector_mcp_tool_name(service, action.id, "invoke"),
                    "description": _tool_description(
                        manifest,
                        action.display_name,
                        action.id,
                        "invoke",
                        detail=action.description or None,
                    ),
                    "inputSchema": _invoke_input_schema(action),
                }
            )
    return tools


def _filter_manifests_for_workspace(ctx: WorkspaceCoreContext, manifests: list[ConnectorManifest]) -> list[ConnectorManifest]:
    runtime = ctx.knowledge.connector_runtime()
    effective = runtime.vault.effective_allowed_providers(ctx.workspace.id)
    if effective == "*":
        return manifests
    allowed = set(effective) if isinstance(effective, list) else set()
    return [m for m in manifests if m.service in allowed]


def connector_tool_definitions_for_workspace(ctx: WorkspaceCoreContext) -> list[dict[str, Any]]:
    """Manifest-derived MCP tools for one workspace (allowlist + action_policy.entities)."""
    runtime = ctx.knowledge.connector_runtime()
    policy = runtime.vault.get_policy(ctx.workspace.id)
    catalog = get_connector_catalog()
    manifests = _filter_manifests_for_workspace(ctx, catalog.list_manifests())
    out: list[dict[str, Any]] = []
    for manifest in manifests:
        out.extend(connector_tool_definitions_for_manifest(manifest, policy))
    out.sort(key=lambda t: t["name"])
    return out


def connector_mcp_tool_names_for_workspace(ctx: WorkspaceCoreContext) -> list[str]:
    return [t["name"] for t in connector_tool_definitions_for_workspace(ctx)]
