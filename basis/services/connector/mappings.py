"""Connector table mapping use cases."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.connector._helpers import connector_sync_service, json_safe_cursor_watermark
from basis.services.kernel import WorkspaceCoreContext
from basis.services.errors import AdminError
from basis.services.knowledge.schedulers.connector_mapping_poll_due import poll_interval_minutes_for_mapping
from basis.services.knowledge.services.connector_sync import (
    ConnectorLedgerSyncService,
    SourceTableMappingRecord,
)


def table_mapping_api_dict(
    svc: ConnectorLedgerSyncService, workspace_id: str, rec: SourceTableMappingRecord
) -> dict[str, Any]:
    binding = svc.get_mapping_connection_binding(workspace_id, rec.source_id)
    return {
        "id": rec.id,
        "workspace_id": rec.workspace_id,
        "source_id": rec.source_id,
        "provider": binding.provider,
        "stream_name": rec.stream_name,
        "external_table": rec.external_table,
        "stream_params": rec.stream_params,
        "primary_key_column": rec.primary_key_column,
        "cursor_column": rec.cursor_column,
        "label_column": rec.label_column,
        "target_class_uri": rec.target_class_uri,
        "column_mappings": [c.model_dump(mode="json") for c in rec.column_mappings],
        "sync_mode": rec.sync_mode,
        "track_deletes": rec.track_deletes,
        "checkpoint": rec.checkpoint,
        "sync_direction": rec.sync_direction,
        "writeback_mode": rec.writeback_mode,
        "max_rows": rec.max_rows,
        "poll_interval_minutes": poll_interval_minutes_for_mapping(rec),
        "status": rec.status,
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
    }


def list_all_table_mappings(ctx: WorkspaceCoreContext) -> dict[str, Any]:
    """HTTP ``GET …/connectors/table-mappings`` (full mapping records for the console)."""
    authz.require_workspace_viewer(ctx)
    svc = connector_sync_service(ctx)
    mappings = []
    for m_id in ctx.knowledge.list_source_table_mapping_ids(ctx.workspace.id):
        rec = svc.get_table_mapping(ctx.workspace.id, m_id)
        if rec:
            mappings.append(table_mapping_api_dict(svc, ctx.workspace.id, rec))
    return {"mappings": mappings}


def list_table_mappings(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    """MCP ``list_connector_table_mappings`` (summary rows with optional limit)."""
    authz.require_workspace_viewer(ctx)
    svc = connector_sync_service(ctx)
    mapping_limit = min(max(1, int(args.get("limit") or 50)), 200)
    items: list[dict[str, Any]] = []
    for mapping_id in ctx.knowledge.list_source_table_mapping_ids(
        ctx.workspace.id, limit=mapping_limit
    ):
        rec = svc.get_table_mapping(ctx.workspace.id, mapping_id)
        if not rec:
            continue
        binding = svc.get_mapping_connection_binding(ctx.workspace.id, rec.source_id)
        items.append(
            {
                "id": rec.id,
                "provider": binding.provider,
                "stream_name": rec.stream_name,
                "external_table": rec.external_table,
                "sync_direction": rec.sync_direction,
                "writeback_mode": rec.writeback_mode,
                "poll_interval_minutes": poll_interval_minutes_for_mapping(rec),
                "status": rec.status,
            },
        )
    return {"mappings": items}


def sync_table_mapping(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    mapping_id = str(args.get("mapping_id") or "").strip()
    if not mapping_id:
        return {"error": "mapping_id is required"}
    svc = connector_sync_service(ctx)
    try:
        stats = svc.sync_inbound_mapping(ctx.workspace.id, mapping_id)
    except LookupError:
        return {"error": "mapping not found"}
    except Exception as exc:
        return {"error": str(exc)}
    if (
        ctx.rebuild_projection is not None
        and (stats.added > 0 or stats.updated > 0 or stats.deleted > 0)
    ):
        ctx.rebuild_projection()
    return {
        "mapping_id": stats.mapping_id,
        "external_table": stats.external_table,
        "fetched_rows": stats.fetched_rows,
        "added": stats.added,
        "updated": stats.updated,
        "unchanged": stats.unchanged,
        "deleted": stats.deleted,
        "new_cursor_watermark": json_safe_cursor_watermark(stats.new_cursor_watermark),
    }


