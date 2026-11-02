"""BOCP connector routes — table mappings and inbound sync."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.services.connector import mappings as mapping_uc
from basis.services.connector import mappings_admin as mapping_admin_uc
from basis.services.connector.operations import op_sync_connector_table_mapping
from basis.services.kernel import CoreError
from basis.http.operation_http import (
    http_exception_from_core,
    http_response_from_connector_payload,
)
from basis.services.tenancy.admin.store import AdminStore, User
from basis.routes.workspace.connector.models import (
    BatchCreateTableMappingsRequest,
    CreateTableMappingRequest,
    SuggestTableMappingsRequest,
    UpdateTableMappingRequest,
)
from basis.http.core_context import build_workspace_core_context
from basis.http.deps import get_current_user, get_store

router = APIRouter(tags=["workspaces"])


def _ctx(
    request: Request,
    workspace_id: str,
    user: User,
    store: AdminStore,
    *,
    require_editor: bool = False,
):
    return build_workspace_core_context(
        request,
        workspace_id=workspace_id,
        user=user,
        store=store,
        require_editor=require_editor,
    )


@router.get(
    "/{workspace_id}/connectors/table-mappings",
)
async def list_table_mappings(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """List structured stream-to-ontology table mappings configured in this workspace."""
    try:
        return mapping_uc.list_all_table_mappings(
            _ctx(request, workspace_id, user, store)
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.get("/{workspace_id}/connectors/table-mappings/{mapping_id}")
async def get_table_mapping(
    workspace_id: str,
    mapping_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Fetch one stream-to-ontology table mapping with connector connection binding."""
    try:
        return mapping_admin_uc.get_table_mapping(
            _ctx(request, workspace_id, user, store), mapping_id=mapping_id
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.put("/{workspace_id}/connectors/table-mappings/{mapping_id}")
async def update_table_mapping(
    workspace_id: str,
    mapping_id: str,
    body: UpdateTableMappingRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Update a stream-to-ontology table mapping and optional connector connection binding."""
    try:
        return mapping_admin_uc.update_table_mapping(
            _ctx(request, workspace_id, user, store, require_editor=True),
            mapping_id=mapping_id,
            provider=body.provider,
            stream_name=body.stream_name,
            external_table=body.external_table,
            primary_key_column=body.primary_key_column,
            cursor_column=body.cursor_column,
            label_column=body.label_column,
            target_class_uri=body.target_class_uri,
            column_mappings=body.column_mappings,
            stream_params=body.stream_params,
            sync_mode=body.sync_mode,
            track_deletes=body.track_deletes,
            sync_direction=body.sync_direction,
            writeback_mode=body.writeback_mode,
            max_rows=body.max_rows,
            poll_interval_minutes=body.poll_interval_minutes,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.delete("/{workspace_id}/connectors/table-mappings/{mapping_id}")
async def delete_table_mapping(
    workspace_id: str,
    mapping_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Delete a stream-to-ontology table mapping (cascades `entity_external_refs`)."""
    try:
        return mapping_admin_uc.delete_table_mapping(
            _ctx(request, workspace_id, user, store, require_editor=True),
            mapping_id=mapping_id,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post("/{workspace_id}/connectors/table-mappings/suggest")
async def suggest_table_mappings(
    workspace_id: str,
    body: SuggestTableMappingsRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Propose cross-stream connector mapping drafts grouped by inferred entity type (discover-backed)."""
    try:
        return mapping_admin_uc.suggest_table_mappings(
            _ctx(request, workspace_id, user, store),
            body.model_dump(mode="json"),
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post("/{workspace_id}/connectors/table-mappings/batch-create")
async def batch_create_table_mappings(
    workspace_id: str,
    body: BatchCreateTableMappingsRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Create multiple stream-to-ontology table mappings and optionally run first inbound sync."""
    try:
        return mapping_admin_uc.batch_create_table_mappings(
            _ctx(request, workspace_id, user, store, require_editor=True),
            mappings=[m.model_dump(mode="json") for m in body.mappings],
            run_sync=body.run_sync,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post("/{workspace_id}/connectors/table-mappings")
async def create_table_mapping(
    workspace_id: str,
    body: CreateTableMappingRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Create a stream-to-ontology table mapping (auto-creating a `connector` ingest_source if omitted)."""
    try:
        return mapping_admin_uc.create_table_mapping(
            _ctx(request, workspace_id, user, store, require_editor=True),
            body.model_dump(mode="json"),
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post(
    "/{workspace_id}/connectors/table-mappings/{mapping_id}/sync",
)
async def sync_table_mapping(
    workspace_id: str,
    mapping_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Execute inbound 4-way sync from the BOCP stream into the Evidence Ledger."""
    try:
        payload = op_sync_connector_table_mapping(
            _ctx(request, workspace_id, user, store, require_editor=True),
            {"mapping_id": mapping_id},
        )
        return http_response_from_connector_payload(payload, kind="mapping_sync")
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc
