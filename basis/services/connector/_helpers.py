"""Shared helpers for connector application use cases."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, TYPE_CHECKING

from basis.services.kernel import WorkspaceCoreContext
from basis.services.connector.vault.connection_scope import SCOPE_WORKSPACE
from basis.services.knowledge.services.connector_sync import ConnectorLedgerSyncService

if TYPE_CHECKING:
    from basis.services.connector.vault.auth_vault import StoredConnection


def json_safe_cursor_watermark(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def connector_sync_service(ctx: WorkspaceCoreContext) -> ConnectorLedgerSyncService:
    return ctx.knowledge.connector_sync_service()


def filter_manifests_for_workspace(ctx: WorkspaceCoreContext, manifests: list[Any]) -> list[Any]:
    runtime = ctx.knowledge.connector_runtime()
    effective = runtime.vault.effective_allowed_providers(ctx.workspace.id)
    if effective == "*":
        return manifests
    allowed = set(effective) if isinstance(effective, list) else set()
    return [m for m in manifests if m.service in allowed]


def connector_summary(manifest: Any) -> dict[str, Any]:
    auth_modes = [a.auth_mode for a in (manifest.auth or [])]
    return {
        "service": manifest.service,
        "display_name": manifest.display_name,
        "description": manifest.description,
        "categories": list(manifest.categories or []),
        "auth_modes": auth_modes,
        "stream_count": len(manifest.streams or []),
        "tool_count": len(manifest.tools or []),
    }


def mcp_connection_item(conn: StoredConnection) -> dict[str, Any]:
    return {
        "service": conn.service,
        "connection_scope": conn.connection_scope,
        "subject_id": conn.subject_id if conn.connection_scope != SCOPE_WORKSPACE else None,
        "auth_type": conn.auth_type,
        "account_profile": conn.account_profile,
        "updated_at": conn.updated_at,
    }
