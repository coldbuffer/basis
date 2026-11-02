from __future__ import annotations

from basis.services.connector.registry import (
    ConnectorCatalog,
    default_providers_dir,
    get_connector_catalog,
)

"""Connector catalog use cases."""


from typing import Any

from basis.services.connector import authz
from basis.services.connector._helpers import connector_summary, filter_manifests_for_workspace
from basis.services.kernel import WorkspaceCoreContext
from basis.services.connector.vault.allowlist import is_platform_provider_allowed
from basis.services.connector.workspace_apps import is_workspace_app_installed
from basis.services.errors import AdminError


def list_catalog(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    """MCP ``list_connector_catalog`` (summary rows; default limit 25, max 100)."""
    authz.require_workspace_viewer(ctx)
    query = str(args.get("query") or "").strip() or None
    limit = min(max(1, int(args.get("limit") or 25)), 100)
    has_streams_only = bool(args.get("has_streams_only"))
    catalog = get_connector_catalog()
    manifests = catalog.list_manifests(
        query=query,
        has_streams_only=has_streams_only,
    )
    manifests = filter_manifests_for_workspace(ctx, manifests)[:limit]
    return {
        "total_matched": len(manifests),
        "connectors": [connector_summary(m) for m in manifests],
    }


def describe_service(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    """MCP ``describe_connector_service`` (summary + stream/tool slices for agents)."""
    authz.require_workspace_viewer(ctx)
    service = str(args.get("service") or "").strip()
    if not service:
        return {"error": "service is required"}
    catalog = get_connector_catalog()
    manifest = catalog.get(service)
    if not manifest:
        return {"error": f"unknown connector service: {service}"}
    filtered = filter_manifests_for_workspace(ctx, [manifest])
    if not filtered:
        return {"error": "connector not allowed by platform or workspace policy"}
    m = filtered[0]
    return {
        "connector": {
            **connector_summary(m),
            "streams": [
                {
                    "name": s.name,
                    "display_name": s.display_name,
                    "cursor_field": s.cursor_field,
                }
                for s in (m.streams or [])[:50]
            ],
            "tools": [
                {"id": t.id, "name": t.name, "description": t.description}
                for t in (m.tools or [])[:30]
            ],
        },
    }


def list_catalog_detailed(
    ctx: WorkspaceCoreContext,
    *,
    category: str | None = None,
    auth_mode: str | None = None,
    has_streams_only: bool = False,
    query: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """HTTP ``GET /connectors/catalog`` (full manifests, stats, category/auth filters)."""
    authz.require_workspace_viewer(ctx)
    catalog = get_connector_catalog()
    manifests = catalog.list_manifests(
        category=category,
        auth_mode=auth_mode,
        has_streams_only=has_streams_only,
        query=query,
    )
    runtime = ctx.knowledge.connector_runtime()
    platform_allowed = runtime.vault.get_platform_allowed_providers()
    workspace_policy = runtime.vault.get_policy(ctx.workspace.id)

    platform_manifests: list[Any] = []
    workspace_apps: list[Any] = []
    for manifest in manifests:
        if not is_platform_provider_allowed(manifest.service, platform_allowed):
            continue
        platform_manifests.append(manifest)
        if is_workspace_app_installed(manifest.service, workspace_policy.allowed_providers):
            workspace_apps.append(manifest)

    catalog_slice = platform_manifests[:limit]
    apps_slice = workspace_apps[:limit]
    return {
        "stats": catalog.summary_stats(),
        "total_matched": len(platform_manifests),
        "total_browse": len(platform_manifests),
        "total_workspace_apps": len(workspace_apps),
        "connectors": [m.model_dump(mode="json", exclude_none=True) for m in catalog_slice],
        "browse_connectors": [m.model_dump(mode="json", exclude_none=True) for m in catalog_slice],
        "workspace_apps": [m.model_dump(mode="json", exclude_none=True) for m in apps_slice],
    }


def get_manifest(ctx: WorkspaceCoreContext, *, service: str) -> dict[str, Any]:
    """HTTP ``GET …/connectors/catalog/{service}`` (full BOCP manifest JSON for the console)."""
    authz.require_workspace_viewer(ctx)
    runtime = ctx.knowledge.connector_runtime()
    try:
        runtime.vault.assert_service_allowed(ctx.workspace.id, service)
    except PermissionError as exc:
        raise AdminError(403, "connector_policy_blocked", str(exc)) from exc
    manifest = get_connector_catalog().get(service)
    if not manifest:
        raise AdminError(404, "connector_not_found", f"未知的连接器服务: {service}")
    return {"connector": manifest.model_dump(mode="json", exclude_none=True)}


def list_embed_providers(
    ctx: WorkspaceCoreContext,
    *,
    has_streams_only: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    authz.require_workspace_viewer(ctx)
    catalog = get_connector_catalog()
    manifests = catalog.list_manifests(has_streams_only=has_streams_only)
    manifests = filter_manifests_for_workspace(ctx, manifests)[:limit]
    return {
        "providers": [m.model_dump(mode="json", exclude_none=True) for m in manifests],
        "total": len(manifests),
    }
