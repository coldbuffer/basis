"""Workspace connector policy use cases."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.kernel import WorkspaceCoreContext
from basis.services.connector import get_connector_catalog
from basis.services.connector.vault.allowlist import (
    is_platform_provider_allowed,
    normalize_allowed_providers,
)
from basis.services.connector.workspace_apps import (
    effective_active_providers,
    installed_workspace_providers,
    is_workspace_app_installed,
    normalize_disabled_providers,
    with_disabled_providers,
)
from basis.services.errors import AdminError


def policy_response(vault: Any, workspace_id: str, pol: Any) -> dict[str, Any]:
    platform_allowed = vault.get_platform_allowed_providers()
    effective = effective_active_providers(
        platform_allowed,
        pol.allowed_providers,
        pol.action_policy,
    )
    return {
        "workspace_id": workspace_id,
        "platform_allowed_providers": platform_allowed,
        "allowed_providers": pol.allowed_providers,
        "installed_providers": installed_workspace_providers(pol.allowed_providers),
        "disabled_providers": normalize_disabled_providers(pol.action_policy),
        "effective_allowed_providers": effective,
        "action_policy": pol.action_policy,
        "updated_at": pol.updated_at,
    }


def get_policy(ctx: WorkspaceCoreContext) -> dict[str, Any]:
    authz.require_workspace_viewer(ctx)
    runtime = ctx.knowledge.connector_runtime()
    pol = runtime.vault.get_policy(ctx.workspace.id)
    return policy_response(runtime.vault, ctx.workspace.id, pol)


def upsert_policy(
    ctx: WorkspaceCoreContext,
    *,
    allowed_providers: list[str] | str,
    action_policy: dict[str, Any],
) -> dict[str, Any]:
    authz.require_workspace_editor(ctx)
    runtime = ctx.knowledge.connector_runtime()
    try:
        pol = runtime.vault.upsert_policy(
            ctx.workspace.id,
            allowed_providers=normalize_allowed_providers(allowed_providers),
            action_policy=action_policy,
        )
    except PermissionError as exc:
        msg = str(exc)
        if "platform level" in msg:
            raise AdminError(400, "connector_allowlist_exceeds_platform", msg) from exc
        if "Unknown connector" in msg:
            raise AdminError(400, "connector_unknown_providers", msg) from exc
        raise AdminError(403, "connector_policy_blocked", msg) from exc
    return policy_response(runtime.vault, ctx.workspace.id, pol)


def _catalog_service_ids() -> list[str]:
    return get_connector_catalog().service_ids()


def _workspace_allowlist_after_remove(
    *,
    current: list[str] | str,
    platform: list[str] | str,
    service: str,
) -> list[str]:
    current_norm = normalize_allowed_providers(current)
    if current_norm == "*":
        platform_norm = normalize_allowed_providers(platform)
        if platform_norm == "*":
            base = _catalog_service_ids()
        elif isinstance(platform_norm, list):
            base = list(platform_norm)
        else:
            base = []
        return sorted({s for s in base if s != service})
    if isinstance(current_norm, list):
        return sorted({s for s in current_norm if s != service})
    return []


def _validate_service(ctx: WorkspaceCoreContext, service: str) -> None:
    catalog = get_connector_catalog()
    if not catalog.get(service):
        raise AdminError(404, "connector_not_found", f"未知的连接器服务: {service}")
    runtime = ctx.knowledge.connector_runtime()
    platform = runtime.vault.get_platform_allowed_providers()
    if not is_platform_provider_allowed(service, platform):
        raise AdminError(
            403,
            "connector_policy_blocked",
            f"Provider '{service}' is not allowed at platform level",
        )


def add_workspace_app(ctx: WorkspaceCoreContext, *, service: str) -> dict[str, Any]:
    """Install a provider on the workspace (or re-enable if already installed)."""
    authz.require_workspace_editor(ctx)
    service = service.strip()
    if not service:
        raise AdminError(422, "service_required", "service is required")
    _validate_service(ctx, service)
    runtime = ctx.knowledge.connector_runtime()
    pol = runtime.vault.get_policy(ctx.workspace.id)
    current = normalize_allowed_providers(pol.allowed_providers)
    if current == "*":
        current = []
    if not isinstance(current, list):
        current = []
    installed = sorted(set(current) | {service})
    disabled = [d for d in normalize_disabled_providers(pol.action_policy) if d != service]
    return upsert_policy(
        ctx,
        allowed_providers=installed,
        action_policy=with_disabled_providers(pol.action_policy, disabled),
    )


def enable_workspace_provider(ctx: WorkspaceCoreContext, *, service: str) -> dict[str, Any]:
    """Alias: add app or clear disabled flag."""
    return add_workspace_app(ctx, service=service)


def disable_workspace_provider(ctx: WorkspaceCoreContext, *, service: str) -> dict[str, Any]:
    """Soft-disable an installed app (keeps OAuth config and connections)."""
    authz.require_workspace_editor(ctx)
    service = service.strip()
    if not service:
        raise AdminError(422, "service_required", "service is required")
    _validate_service(ctx, service)
    runtime = ctx.knowledge.connector_runtime()
    pol = runtime.vault.get_policy(ctx.workspace.id)
    if not is_workspace_app_installed(service, pol.allowed_providers):
        norm = normalize_allowed_providers(pol.allowed_providers)
        if norm != "*":
            raise AdminError(404, "workspace_app_not_installed", f"App '{service}' is not installed")
    disabled = normalize_disabled_providers(pol.action_policy)
    if service not in disabled:
        disabled = sorted(set(disabled) | {service})
    return upsert_policy(
        ctx,
        allowed_providers=pol.allowed_providers,
        action_policy=with_disabled_providers(pol.action_policy, disabled),
    )


def delete_workspace_provider(ctx: WorkspaceCoreContext, *, service: str) -> dict[str, Any]:
    """Remove app from workspace list (does not delete vault connections or OAuth config)."""
    authz.require_workspace_editor(ctx)
    service = service.strip()
    if not service:
        raise AdminError(422, "service_required", "service is required")
    runtime = ctx.knowledge.connector_runtime()
    pol = runtime.vault.get_policy(ctx.workspace.id)
    new_list = _workspace_allowlist_after_remove(
        current=pol.allowed_providers,
        platform=runtime.vault.get_platform_allowed_providers(),
        service=service,
    )
    disabled = [d for d in normalize_disabled_providers(pol.action_policy) if d != service]
    return upsert_policy(
        ctx,
        allowed_providers=new_list if new_list else [],
        action_policy=with_disabled_providers(pol.action_policy, disabled),
    )
