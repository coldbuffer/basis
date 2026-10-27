"""BOCP connector routes — connections, discover, primitives."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.application.connectors import connections
from basis.application.connectors.operations import (
    op_check_connector_connection,
    op_delete_connector_connection,
    op_discover_connector_schema,
    op_invoke_connector_primitive,
    op_upsert_connector_connection,
)
from basis.application.kernel import CoreError
from basis.interface.http.shared.operation_http import (
    http_exception_from_core,
    http_response_from_connector_payload,
)
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.workspace.connectors.models import (
    InvokeConnectorPrimitiveRequest,
    UpsertConnectorConnectionRequest,
)
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.http.shared.deps import get_current_user, get_store

router = APIRouter(tags=["workspaces"])


@router.get(
    "/{workspace_id}/connectors/connections",
)
async def list_connector_connections(
    workspace_id: str,
    request: Request,
    service: str | None = Query(default=None),
    connection_scope: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """List configured BOCP connections for this workspace (credentials redacted)."""
    try:
        ctx = build_workspace_core_context(
            request, workspace_id=workspace_id, user=user, store=store
        )
        return connections.list_connections_public(
            ctx,
            service=service,
            connection_scope=connection_scope,
            subject_id=subject_id,
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.put("/{workspace_id}/connectors/connections/{service}")
async def upsert_connector_connection(
    workspace_id: str,
    service: str,
    body: UpsertConnectorConnectionRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Create or update an encrypted BOCP connection for this workspace."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        return await asyncio.to_thread(
            op_upsert_connector_connection,
            ctx,
            {
                "service": service,
                "connection_scope": body.connection_scope,
                "subject_id": body.subject_id,
                "auth_type": body.auth_type,
                "connection_config": body.connection_config,
                "credentials": body.credentials,
            },
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.delete("/{workspace_id}/connectors/connections/{service}")
async def delete_connector_connection(
    workspace_id: str,
    service: str,
    request: Request,
    connection_scope: str = Query(default="workspace"),
    subject_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Delete a configured BOCP connection from this workspace."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        return await asyncio.to_thread(
            op_delete_connector_connection,
            ctx,
            {
                "service": service,
                "connection_scope": connection_scope,
                "subject_id": subject_id,
            },
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post("/{workspace_id}/connectors/connections/{service}/check")
async def check_connector_connection(
    workspace_id: str,
    service: str,
    request: Request,
    connection_scope: str = Query(default="workspace"),
    subject_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Run the BOCP `CHECK` health check against an upstream connection."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        return await asyncio.to_thread(
            op_check_connector_connection,
            ctx,
            {
                "service": service,
                "connection_scope": connection_scope,
                "subject_id": subject_id,
            },
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.get("/{workspace_id}/connectors/connections/{service}/discover")
async def discover_connector_schema(
    workspace_id: str,
    service: str,
    request: Request,
    stream_name: str | None = Query(default=None),
    external_table: str | None = Query(default=None),
    connection_scope: str = Query(default="workspace"),
    subject_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Run the BOCP `DISCOVER` schema introspection for a SQL table or REST stream."""
    try:
        ctx = build_workspace_core_context(
            request, workspace_id=workspace_id, user=user, store=store
        )
        return await asyncio.to_thread(
            op_discover_connector_schema,
            ctx,
            {
                "service": service,
                "connection_scope": connection_scope,
                "subject_id": subject_id,
                "stream_name": stream_name,
                "external_table": external_table,
            },
        )
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post(
    "/{workspace_id}/connectors/connections/{service}/invoke-primitive",
)
async def invoke_connector_primitive(
    workspace_id: str,
    service: str,
    body: InvokeConnectorPrimitiveRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Run a BOCP Section 10 primitive (discover, list, mutate, invoke) without a table mapping."""
    require_editor = body.primitive not in ("discover", "list")
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=require_editor,
        )
        payload = op_invoke_connector_primitive(
            ctx,
            {
                "service": service,
                "action_id": body.action_id,
                "primitive": body.primitive,
                "connection_scope": body.connection_scope,
                "subject_id": body.subject_id,
                "operation": body.operation,
                "external_table": body.external_table,
                "external_id": body.external_id,
                "changes": body.changes,
                "action_params": body.action_params,
                "limit": body.limit,
                "cursor_watermark": body.cursor_watermark,
                "arguments": body.arguments,
                "primary_key_column": body.primary_key_column,
                "cursor_column": body.cursor_column,
            },
        )
        return http_response_from_connector_payload(payload, kind="primitive")
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc
