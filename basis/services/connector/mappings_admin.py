"""Table mapping CRUD, suggestions, and batch create (console HTTP use cases)."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.connector._helpers import connector_sync_service
from basis.services.connector.mappings import (
    sync_table_mapping,
    table_mapping_api_dict,
)
from basis.services.kernel import WorkspaceCoreContext
from basis.services.errors import AdminError
from basis.services.knowledge.models import ColumnMappingSpec, ConnectorSourceConfig


def _column_mappings(raw: list[Any]) -> list[ColumnMappingSpec]:
    out: list[ColumnMappingSpec] = []
    for item in raw:
        if isinstance(item, ColumnMappingSpec):
            out.append(item)
        else:
            out.append(ColumnMappingSpec.model_validate(item))
    return out
from basis.services.knowledge.services.mapping_suggestions import (
    SuggestStreamTarget,
    expand_auto_targets,
    suggest_table_mapping_drafts,
)


def _existing_mapping_fingerprints(ctx: WorkspaceCoreContext) -> set[tuple[str, str, str]]:
    svc = connector_sync_service(ctx)
    existing: set[tuple[str, str, str]] = set()
    for m_id in ctx.knowledge.list_source_table_mapping_ids(ctx.workspace.id):
        rec = svc.get_table_mapping(ctx.workspace.id, m_id)
        if not rec:
            continue
        binding = svc.get_mapping_connection_binding(ctx.workspace.id, rec.source_id)
        existing.add(
            (
                binding.provider,
                rec.stream_name,
                rec.external_table,
            )
        )
    return existing


def get_table_mapping(ctx: WorkspaceCoreContext, *, mapping_id: str) -> dict[str, Any]:
    authz.require_workspace_viewer(ctx)
    svc = connector_sync_service(ctx)
    rec = svc.get_table_mapping(ctx.workspace.id, mapping_id)
    if not rec:
        raise AdminError(404, "mapping_not_found", "表映射不存在")
    return {"mapping": table_mapping_api_dict(svc, ctx.workspace.id, rec)}


def update_table_mapping(
    ctx: WorkspaceCoreContext,
    *,
    mapping_id: str,
    provider: str | None,
    stream_name: str,
    external_table: str,
    primary_key_column: str,
    cursor_column: str | None,
    label_column: str,
    target_class_uri: str,
    column_mappings: list[Any],
    stream_params: dict[str, Any],
    sync_mode: str,
    track_deletes: bool,
    sync_direction: str,
    writeback_mode: str,
    max_rows: int,
    poll_interval_minutes: int,
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    svc = connector_sync_service(ctx)
    try:
        rec = svc.update_table_mapping(
            ctx.workspace.id,
            mapping_id,
            provider=provider,
            stream_name=stream_name,
            external_table=external_table,
            primary_key_column=primary_key_column,
            cursor_column=cursor_column,
            label_column=label_column,
            target_class_uri=target_class_uri,
            column_mappings=_column_mappings(column_mappings),
            stream_params=stream_params,
            sync_mode=sync_mode,
            track_deletes=track_deletes,
            sync_direction=sync_direction,
            writeback_mode=writeback_mode,
            max_rows=max_rows,
            poll_interval_minutes=poll_interval_minutes,
        )
        return {"mapping": table_mapping_api_dict(svc, ctx.workspace.id, rec)}
    except LookupError as exc:
        raise AdminError(404, "mapping_not_found", str(exc)) from exc
    except Exception as exc:
        raise AdminError(422, "mapping_update_failed", str(exc)) from exc


def delete_table_mapping(ctx: WorkspaceCoreContext, *, mapping_id: str) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    svc = connector_sync_service(ctx)
    deleted = svc.delete_table_mapping(ctx.workspace.id, mapping_id)
    if not deleted:
        raise AdminError(404, "mapping_not_found", "表映射不存在")
    return {"deleted": True, "mapping_id": mapping_id}


def suggest_table_mappings(ctx: WorkspaceCoreContext, body: dict[str, Any]) -> dict[str, Any]:
    authz.require_workspace_viewer(ctx)
    rt = ctx.knowledge.connector_runtime()
    existing = _existing_mapping_fingerprints(ctx)

    targets: list[SuggestStreamTarget] = []
    for item in body.get("targets") or []:
        targets.append(
            SuggestStreamTarget(
                provider=item["provider"],
                stream_name=item.get("stream_name"),
                external_table=item.get("external_table"),
            )
        )
    for item in body.get("sql_tables") or []:
        targets.append(
            SuggestStreamTarget(
                provider=item["provider"],
                stream_name=item.get("stream_name") or "table_records",
                external_table=item.get("external_table"),
            )
        )
    if not targets:
        connections = body.get("connections") or []
        scopes = [item["provider"] for item in connections] if connections else None
        targets = expand_auto_targets(
            rt,
            ctx.workspace.id,
            max_streams_per_connection=int(body.get("max_streams_per_connection") or 8),
            connection_scopes=scopes,
        )

    result = suggest_table_mapping_drafts(
        rt, ctx.workspace.id, targets, existing_fingerprints=existing
    )
    return {
        "groups": result.groups,
        "skipped": [
            {
                "provider": s.provider,
                "stream_name": s.stream_name,
                "external_table": s.external_table,
                "reason": s.reason,
            }
            for s in result.skipped
        ],
    }


def _resolve_source_id(ctx: WorkspaceCoreContext, mapping_body: dict[str, Any]) -> str:
    source_id = mapping_body.get("source_id")
    if source_id:
        return str(source_id)
    src_cfg = ConnectorSourceConfig(provider=mapping_body["provider"])
    created_src, _ = ctx.knowledge.create_ingest_source(
        ctx.workspace.id,
        ctx.user.id,
        kind="connector",
        name=f"{mapping_body['provider']}:{mapping_body['external_table']}",
        config=src_cfg.model_dump(mode="json", exclude_none=True),
        enabled=True,
    )
    return str(created_src["id"])


def create_table_mapping(ctx: WorkspaceCoreContext, body: dict[str, Any]) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    source_id = _resolve_source_id(ctx, body)
    svc = connector_sync_service(ctx)
    rec = svc.create_table_mapping(
        ctx.workspace.id,
        source_id=source_id,
        stream_name=body["stream_name"],
        external_table=body["external_table"],
        primary_key_column=body["primary_key_column"],
        cursor_column=body.get("cursor_column"),
        label_column=body["label_column"],
        target_class_uri=body["target_class_uri"],
        column_mappings=_column_mappings(body.get("column_mappings") or []),
        stream_params=body.get("stream_params") or {},
        sync_mode=body.get("sync_mode") or "incremental",
        track_deletes=bool(body.get("track_deletes")),
        sync_direction=body.get("sync_direction") or "inbound",
        writeback_mode=body.get("writeback_mode") or "review",
        max_rows=int(body.get("max_rows") or 10000),
        poll_interval_minutes=int(body.get("poll_interval_minutes") or 0),
    )
    return {
        "mapping": {
            "id": rec.id,
            "workspace_id": rec.workspace_id,
            "source_id": rec.source_id,
            "stream_name": rec.stream_name,
            "external_table": rec.external_table,
            "primary_key_column": rec.primary_key_column,
            "label_column": rec.label_column,
            "target_class_uri": rec.target_class_uri,
            "sync_direction": rec.sync_direction,
            "writeback_mode": rec.writeback_mode,
        }
    }


def batch_create_table_mappings(
    ctx: WorkspaceCoreContext,
    *,
    mappings: list[dict[str, Any]],
    run_sync: bool,
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    svc = connector_sync_service(ctx)
    created: list[dict[str, Any]] = []
    sync_results: list[dict[str, Any]] = []

    for mapping_body in mappings:
        source_id = _resolve_source_id(ctx, mapping_body)
        rec = svc.create_table_mapping(
            ctx.workspace.id,
            source_id=source_id,
            stream_name=mapping_body["stream_name"],
            external_table=mapping_body["external_table"],
            primary_key_column=mapping_body["primary_key_column"],
            cursor_column=mapping_body.get("cursor_column"),
            label_column=mapping_body["label_column"],
            target_class_uri=mapping_body["target_class_uri"],
            column_mappings=_column_mappings(mapping_body.get("column_mappings") or []),
            stream_params=mapping_body.get("stream_params") or {},
            sync_mode=mapping_body.get("sync_mode") or "incremental",
            track_deletes=bool(mapping_body.get("track_deletes")),
            sync_direction=mapping_body.get("sync_direction") or "inbound",
            writeback_mode=mapping_body.get("writeback_mode") or "review",
            max_rows=int(mapping_body.get("max_rows") or 10000),
            poll_interval_minutes=int(mapping_body.get("poll_interval_minutes") or 0),
        )
        row = table_mapping_api_dict(svc, ctx.workspace.id, rec)
        created.append(row)
        if run_sync:
            payload = sync_table_mapping(ctx, {"mapping_id": rec.id})
            if payload.get("error"):
                sync_results.append({"mapping_id": rec.id, "error": payload["error"]})
            else:
                sync_results.append(payload)

    return {"mappings": created, "sync_results": sync_results}
