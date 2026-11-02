"""BOCP connector routes — writeback outbox and run history."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from basis.services.connector import outbox
from basis.services.connector.operations import op_propose_entity_writeback
from basis.services.kernel import CoreError
from basis.http.operation_http import (
    http_exception_from_core,
    http_response_from_connector_payload,
)
from basis.services.tenancy.admin.store import AdminStore, User
from basis.routes.workspace.connector.models import ProposeEntityWritebackRequest
from basis.http.core_context import build_workspace_core_context
from basis.http.deps import get_current_user, get_store

router = APIRouter(tags=["workspaces"])


@router.get("/{workspace_id}/connectors/outbox")
async def list_sync_outbox(
    workspace_id: str,
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """List outbound entity writeback items in `entity_sync_outbox`."""
    try:
        ctx = build_workspace_core_context(
            request, workspace_id=workspace_id, user=user, store=store
        )
        return outbox.list_outbox(ctx, status=status, limit=limit)
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.post(
    "/{workspace_id}/connectors/outbox/propose",
)
async def propose_entity_writeback(
    workspace_id: str,
    body: ProposeEntityWritebackRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Propose an outbound writeback of ledger entity attributes to its external connector stream."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        payload = op_propose_entity_writeback(
            ctx,
            {"entity_id": body.entity_id, "field_updates": body.field_updates},
        )
        return http_response_from_connector_payload(payload, kind="writeback")
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc


@router.get("/{workspace_id}/connectors/runs")
async def list_connector_runs(
    workspace_id: str,
    request: Request,
    service: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """List recent BOCP connector execution audit logs (`connector_runs`)."""
    try:
        ctx = build_workspace_core_context(
            request, workspace_id=workspace_id, user=user, store=store
        )
        return outbox.list_runs(ctx, service=service, limit=limit)
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc
