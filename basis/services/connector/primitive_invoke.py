"""BOCP Section 10 primitive dispatch (shared by HTTP and MCP host bindings)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from basis.services.connector.runtime import ConnectorRuntime

PrimitiveLiteral = Literal["discover", "list", "mutate", "invoke"]
MutateOpLiteral = Literal["create", "update", "upsert", "delete"]


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def execute_connector_primitive(
    runtime: ConnectorRuntime,
    workspace_id: str,
    service: str,
    *,
    action_id: str,
    primitive: str,
    connection_scope: str = "workspace",
    subject_id: str | None = None,
    operation: str | None = None,
    external_table: str | None = None,
    external_id: Any | None = None,
    changes: dict[str, Any] | None = None,
    action_params: dict[str, Any] | None = None,
    limit: int = 500,
    cursor_watermark: Any | None = None,
    arguments: dict[str, Any] | None = None,
    primary_key_column: str = "id",
    cursor_column: str | None = None,
) -> dict[str, Any]:
    """Run one BOCP primitive for an entity or procedure action (no ledger mapping)."""
    action_id = action_id.strip()
    primitive = primitive.strip().lower()
    if not action_id or not primitive:
        raise ValueError("action_id and primitive are required")

    policy = runtime.vault.get_policy(workspace_id)
    mode = policy.resolve_primitive_execution_mode(
        service,
        action_id,
        primitive,
        operation=operation,
    )
    if mode == "disabled":
        raise PermissionError(
            f"Primitive '{primitive}' on action '{action_id}' "
            f"(service '{service}') is disabled by workspace action policy"
        )

    params = dict(action_params or {})

    if primitive == "invoke":
        out = runtime.execute_tool(
            workspace_id,
            service,
            action_id,
            connection_scope=connection_scope,
            subject_id=subject_id,
            arguments=arguments or changes or params,
        )
        return {"mode": mode, **out}

    if primitive == "discover":
        info = runtime.discover_schema(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
            stream_name=action_id,
            external_table=external_table,
            stream_params=params,
        )
        return {
            "mode": mode,
            "action_id": action_id,
            "primitive": primitive,
            "stream_name": info.stream_name,
            "display_name": info.display_name,
            "external_table": info.external_table,
            "primary_key": info.primary_key,
            "cursor_field": info.cursor_field,
            "fields": [f.model_dump(mode="json") for f in info.fields],
        }

    if primitive == "list":
        read_res = runtime.read_stream(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
            stream_name=action_id,
            external_table=external_table,
            primary_key_column=primary_key_column,
            cursor_column=cursor_column,
            cursor_watermark=cursor_watermark,
            stream_params=params,
            limit=min(max(1, limit), 5000),
        )
        return {
            "mode": mode,
            "action_id": action_id,
            "primitive": primitive,
            "records": _json_safe(read_res.records),
            "next_cursor_value": _json_safe(read_res.next_cursor_value),
            "has_more": read_res.has_more,
        }

    if primitive == "mutate":
        if not operation:
            raise ValueError("operation is required for primitive mutate")
        if changes is None:
            changes = {}
        if not isinstance(changes, dict):
            raise ValueError("changes must be an object")
        pk = external_id
        if operation != "create" and pk is None:
            raise ValueError("external_id is required for mutate operations other than create")
        out = runtime.mutate_stream(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
            stream_name=action_id,
            external_table=external_table,
            operation=operation,
            primary_key_column=primary_key_column,
            external_pk=pk if pk is not None else "",
            changes=changes,
            stream_params=params,
        )
        return {
            "mode": mode,
            "action_id": action_id,
            "primitive": primitive,
            "operation": operation,
            "result": _json_safe(out),
        }

    raise ValueError(f"unsupported primitive: {primitive!r}")
