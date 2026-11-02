"""Connector application services (static MCP tools and shared use cases)."""

from __future__ import annotations

from typing import Any

from basis.services.connector import catalog as catalog_uc
from basis.services.connector import connections as connections_uc
from basis.services.connector import mappings as mappings_uc
from basis.services.connector import primitives as primitives_uc
from basis.services.connector import tools as tools_uc
from basis.services.connector import writeback as writeback_uc
from basis.services.kernel import WorkspaceCoreContext


def op_list_connector_catalog(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return catalog_uc.list_catalog(ctx, args)


def op_describe_connector_service(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return catalog_uc.describe_service(ctx, args)


def op_list_connector_connections(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return connections_uc.list_connections(ctx, args)


def op_upsert_connector_connection(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return connections_uc.upsert_connection(
        ctx,
        service=str(args["service"]).strip(),
        connection_scope=str(args.get("connection_scope") or "workspace"),
        subject_id=(str(args["subject_id"]).strip() if args.get("subject_id") else None),
        auth_type=str(args["auth_type"]).strip(),
        connection_config=dict(args.get("connection_config") or {}),
        credentials=dict(args.get("credentials") or {}),
    )


def op_delete_connector_connection(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return connections_uc.delete_connection(
        ctx,
        service=str(args["service"]).strip(),
        connection_scope=str(args.get("connection_scope") or "workspace"),
        subject_id=(str(args["subject_id"]).strip() if args.get("subject_id") else None),
    )


def op_check_connector_connection(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return connections_uc.check_connection(
        ctx,
        service=str(args["service"]).strip(),
        connection_scope=str(args.get("connection_scope") or "workspace"),
        subject_id=(str(args["subject_id"]).strip() if args.get("subject_id") else None),
    )


def op_discover_connector_schema(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    stream_name = str(args.get("stream_name") or "").strip() or None
    external_table = str(args.get("external_table") or "").strip() or None
    return connections_uc.discover_schema(
        ctx,
        service=str(args["service"]).strip(),
        connection_scope=str(args.get("connection_scope") or "workspace"),
        subject_id=(str(args["subject_id"]).strip() if args.get("subject_id") else None),
        stream_name=stream_name,
        external_table=external_table,
    )


def op_list_connector_table_mappings(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return mappings_uc.list_table_mappings(ctx, args)


def op_sync_connector_table_mapping(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return mappings_uc.sync_table_mapping(ctx, args)


def op_invoke_connector_primitive(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return primitives_uc.invoke(ctx, args)


def op_execute_connector_tool(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return tools_uc.execute_tool(ctx, args)


def op_propose_entity_writeback(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    return writeback_uc.propose_entity_writeback(ctx, args)
