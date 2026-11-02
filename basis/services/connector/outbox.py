"""Connector outbox and run history use cases."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.connector._helpers import connector_sync_service
from basis.services.kernel import WorkspaceCoreContext


def list_outbox(
    ctx: WorkspaceCoreContext,
    *,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    authz.require_workspace_viewer(ctx)
    svc = connector_sync_service(ctx)
    outbox_ids = ctx.knowledge.list_entity_sync_outbox_ids(
        ctx.workspace.id, status=status, limit=limit
    )
    items = [svc.get_outbox_item(ctx.workspace.id, outbox_id) for outbox_id in outbox_ids]
    return {"items": items}


def list_runs(
    ctx: WorkspaceCoreContext,
    *,
    service: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    authz.require_workspace_viewer(ctx)
    runs = ctx.knowledge.list_connector_runs(ctx.workspace.id, service=service, limit=limit)
    return {"runs": runs}
