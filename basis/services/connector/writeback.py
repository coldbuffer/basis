"""Entity writeback proposal use case."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.connector._helpers import connector_sync_service
from basis.services.kernel import WorkspaceCoreContext


def propose_entity_writeback(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    entity_id = str(args.get("entity_id") or "").strip()
    field_updates = args.get("field_updates")
    if not entity_id or not isinstance(field_updates, dict) or not field_updates:
        return {"error": "entity_id and non-empty field_updates are required"}
    authz.require_workspace_editor(ctx)
    svc = connector_sync_service(ctx)
    try:
        outbox = svc.propose_entity_writeback(
            ctx.workspace.id,
            entity_id=entity_id,
            field_updates=field_updates,
            created_by=ctx.user.id,
        )
        return {"outbox": outbox}
    except (LookupError, PermissionError, ValueError) as exc:
        return {"error": str(exc)}

