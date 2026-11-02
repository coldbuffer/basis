"""Platform + workspace dual-layer BOCP provider allowlists."""

from __future__ import annotations

from typing import Any

AllowedProviders = list[str] | str

PLATFORM_CONNECTOR_ALLOWLIST_KEY = "connector_allowed_providers"


def normalize_allowed_providers(raw: Any) -> AllowedProviders:
    """Coerce stored JSON into `*` or a sorted unique provider id list."""
    if raw is None or raw == "":
        return "*"
    if raw == "*":
        return "*"
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped == "*":
            return "*"
        parts = [p.strip() for p in stripped.split(",") if p.strip()]
        if not parts or parts == ["*"]:
            return "*"
        return sorted(set(parts))
    if isinstance(raw, list):
        if not raw or raw == ["*"] or "*" in raw:
            return "*"
        return sorted({str(p).strip() for p in raw if str(p).strip()})
    return "*"


def effective_allowed_providers(
    platform: AllowedProviders,
    workspace: AllowedProviders,
) -> AllowedProviders:
    """
    Intersect platform ceiling with workspace selection.

    Workspace `*` means «all providers allowed by the platform» (not the full catalog).
    """
    platform_norm = normalize_allowed_providers(platform)
    workspace_norm = normalize_allowed_providers(workspace)
    if platform_norm == "*":
        return workspace_norm
    if not isinstance(platform_norm, list):
        return []
    platform_set = set(platform_norm)
    if workspace_norm == "*":
        return sorted(platform_set)
    if isinstance(workspace_norm, list):
        return sorted(set(workspace_norm) & platform_set)
    return []


def is_platform_provider_allowed(service: str, platform: AllowedProviders) -> bool:
    """Whether a service is allowed by the platform ceiling alone."""
    platform_norm = normalize_allowed_providers(platform)
    if platform_norm == "*":
        return True
    if isinstance(platform_norm, list):
        return "*" in platform_norm or service in platform_norm
    return False


def count_platform_enabled(platform: AllowedProviders, services: list[str]) -> int:
    if normalize_allowed_providers(platform) == "*":
        return len(services)
    return sum(1 for s in services if is_platform_provider_allowed(s, platform))


def is_workspace_provider_enabled(service: str, workspace: AllowedProviders) -> bool:
    """Whether a provider is enabled on the workspace allowlist (before platform intersection)."""
    workspace_norm = normalize_allowed_providers(workspace)
    if workspace_norm == "*":
        return True
    if isinstance(workspace_norm, list):
        return service in workspace_norm
    return False


def is_provider_allowed(
    service: str,
    platform: AllowedProviders,
    workspace: AllowedProviders,
) -> bool:
    effective = effective_allowed_providers(platform, workspace)
    if effective == "*":
        return True
    if isinstance(effective, list):
        return "*" in effective or service in effective
    return False


def unknown_catalog_providers(
    allowed: AllowedProviders,
    catalog_services: list[str],
) -> list[str]:
    """Provider keys in ``allowed`` that are not in the shipped BOCP catalog."""
    normalized = normalize_allowed_providers(allowed)
    if normalized == "*":
        return []
    if not isinstance(normalized, list):
        return []
    known = set(catalog_services)
    return sorted(set(normalized) - known)


def assert_allowed_providers_in_catalog(
    allowed: AllowedProviders,
    catalog_services: list[str],
) -> None:
    unknown = unknown_catalog_providers(allowed, catalog_services)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"Unknown connector service keys: {joined}")


def assert_workspace_allowlist_within_platform(
    workspace: AllowedProviders,
    platform: AllowedProviders,
) -> None:
    """Raise ValueError when workspace allowlist exceeds the platform ceiling."""
    platform_norm = normalize_allowed_providers(platform)
    workspace_norm = normalize_allowed_providers(workspace)
    if platform_norm == "*" or workspace_norm == "*":
        return
    if not isinstance(platform_norm, list) or not isinstance(workspace_norm, list):
        return
    extra = set(workspace_norm) - set(platform_norm)
    if extra:
        joined = ", ".join(sorted(extra))
        raise ValueError(
            f"Workspace allowlist includes providers not enabled at platform level: {joined}"
        )


def provider_blocked_layer(
    service: str,
    platform: AllowedProviders,
    workspace: AllowedProviders,
) -> str | None:
    """Return ``platform``, ``workspace``, or ``None`` when the service is allowed."""
    platform_norm = normalize_allowed_providers(platform)
    if platform_norm != "*":
        platform_set = set(platform_norm) if isinstance(platform_norm, list) else set()
        if "*" not in platform_set and service not in platform_set:
            return "platform"
    workspace_norm = normalize_allowed_providers(workspace)
    if workspace_norm != "*":
        workspace_set = set(workspace_norm) if isinstance(workspace_norm, list) else set()
        if "*" not in workspace_set and service not in workspace_set:
            return "workspace"
    return None
