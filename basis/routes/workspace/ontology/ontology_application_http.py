"""Run ontology application operations from HTTP handlers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import Request

from basis.services.kernel import WorkspaceCoreContext
from basis.services.tenancy.admin.store import AdminStore, User
from basis.http.core_context import build_workspace_core_context
from basis.http.deps import get_workspace_for_role
from basis.http.operation_http import http_response_from_payload
from basis.routes.workspace.ontology.ontology_hub_support import min_role

OperationFn = Callable[[WorkspaceCoreContext, dict[str, Any]], dict[str, Any]]


async def run_ontology_operation(
    request: Request,
    workspace_id: str,
    user: User,
    store: AdminStore,
    op: OperationFn,
    args: dict[str, Any],
    *,
    http_method: str,
    require_editor: bool = False,
) -> dict[str, Any]:
    get_workspace_for_role(request, user, workspace_id, store, min_role(http_method))
    ctx = build_workspace_core_context(
        request,
        workspace_id=workspace_id,
        user=user,
        store=store,
        require_editor=require_editor,
    )
    payload = await asyncio.to_thread(op, ctx, args)
    return http_response_from_payload(payload)
