"""Run ontology application operations from HTTP handlers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from fastapi import Request

from basis.application.kernel import WorkspaceCoreContext
from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.core_context import build_workspace_core_context
from basis.interface.http.shared.deps import get_workspace_for_role
from basis.interface.http.shared.operation_http import http_response_from_payload
from basis.interface.http.workspace.ontology.ontology_hub_support import min_role

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
