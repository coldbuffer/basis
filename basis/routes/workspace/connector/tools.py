"""BOCP connector routes — standalone tool execution."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from basis.services.connector.operations import op_execute_connector_tool
from basis.services.kernel import CoreError
from basis.http.operation_http import (
    http_exception_from_core,
    http_response_from_connector_payload,
)
from basis.services.tenancy.admin.store import AdminStore, User
from basis.routes.workspace.connector.models import ExecuteConnectorToolRequest
from basis.http.core_context import build_workspace_core_context
from basis.http.deps import get_current_user, get_store

router = APIRouter(tags=["workspaces"])


@router.post(
    "/{workspace_id}/connectors/tools/execute",
)
async def execute_connector_tool(
    workspace_id: str,
    body: ExecuteConnectorToolRequest,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
) -> dict[str, Any]:
    """Execute a standalone BOCP connector tool (`ToolSpec`) with workspace policy enforcement."""
    try:
        ctx = build_workspace_core_context(
            request,
            workspace_id=workspace_id,
            user=user,
            store=store,
            require_editor=True,
        )
        payload = op_execute_connector_tool(
            ctx,
            {
                "service": body.service,
                "tool_id": body.tool_id,
                "connection_scope": body.connection_scope,
                "subject_id": body.subject_id,
                "arguments": body.arguments,
            },
        )
        return http_response_from_connector_payload(payload, kind="tool")
    except CoreError as exc:
        raise http_exception_from_core(exc) from exc
