"""Workspace-installed connector apps (allowlist + soft disable)."""

from __future__ import annotations

from typing import Any

from basis.services.connector.vault.allowlist import AllowedProviders, normalize_allowed_providers

DISABLED_PROVIDERS_POLICY_KEY = "disabled_providers"


def normalize_disabled_providers(action_policy: dict[str, Any] | None) -> list[str]:
    raw = (action_policy or {}).get(DISABLED_PROVIDERS_POLICY_KEY)
    if not isinstance(raw, list):
        return []
    return sorted({str(s).strip() for s in raw if str(s).strip()})


def with_disabled_providers(
    action_policy: dict[str, Any] | None,
    disabled: list[str],
) -> dict[str, Any]:
    merged = dict(action_policy or {})
    merged[DISABLED_PROVIDERS_POLICY_KEY] = sorted(set(disabled))
    return merged


def installed_workspace_providers(allowed_providers: AllowedProviders) -> list[str]:
    """Explicit workspace app installs. Workspace ``*`` means none in the app list."""
    norm = normalize_allowed_providers(allowed_providers)
    if norm == "*":
        return []
    if isinstance(norm, list):
        return list(norm)
    return []


def is_workspace_app_installed(service: str, allowed_providers: AllowedProviders) -> bool:
    return service in installed_workspace_providers(allowed_providers)


def is_workspace_app_disabled(service: str, action_policy: dict[str, Any] | None) -> bool:
    return service in set(normalize_disabled_providers(action_policy))


def is_workspace_app_active(
    service: str,
    allowed_providers: AllowedProviders,
    action_policy: dict[str, Any] | None,
) -> bool:
    if not is_workspace_app_installed(service, allowed_providers):
        norm = normalize_allowed_providers(allowed_providers)
        if norm == "*":
            return not is_workspace_app_disabled(service, action_policy)
        return False
    return not is_workspace_app_disabled(service, action_policy)


def effective_active_providers(
    platform: AllowedProviders,
    workspace: AllowedProviders,
    action_policy: dict[str, Any] | None,
) -> list[str] | str:
    """Runtime-active providers: platform ∩ workspace install list − disabled."""
    from basis.services.connector.vault.allowlist import effective_allowed_providers
    from basis.services.connector import get_connector_catalog

    disabled = set(normalize_disabled_providers(action_policy))
    workspace_norm = normalize_allowed_providers(workspace)
    if workspace_norm == "*":
        platform_norm = normalize_allowed_providers(platform)
        if platform_norm == "*":
            if not disabled:
                return "*"
            base = set(get_connector_catalog().service_ids())
        elif isinstance(platform_norm, list):
            base = set(platform_norm)
        else:
            base = set()
        return sorted(base - disabled)
    base_list = effective_allowed_providers(platform, workspace)
    if base_list == "*":
        return "*"
    if isinstance(base_list, list):
        return sorted(set(base_list) - disabled)
    return []
