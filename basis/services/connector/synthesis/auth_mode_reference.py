"""Canonical upstream registry service ids per BOCP ``auth_mode`` (tests / migration)."""

from __future__ import annotations

from typing import get_args

from basis.services.connector.manifest.manifest_schema import AuthModeLiteral

# Shipped Basis providers (providers/*.yaml) — not all modes.
SHIPPED_MODE_EXAMPLES: dict[str, str] = {
    "oauth2": "github",
    "api_key": "github",
    "database_dsn": "postgres",
}

# One upstream registry provider per BOCP auth_mode for synthesis / migration reference.
REGISTRY_CANONICAL_BY_AUTH_MODE: dict[str, str] = {
    "oauth2": "github",
    "api_key": "active-campaign",
    "oauth2_cc": "1password-users",
    "basic": "amplitude",
    "two_step": "3cx",
    "oauth1": "trello",
    "jwt": "ghost-admin",
    "aws_sigv4": "aws-sigv4",
    "app": "github-app",
    "none": "unauthenticated",
    "custom": "github-app-oauth",
}

ALL_AUTH_MODES: frozenset[str] = frozenset(get_args(AuthModeLiteral))

# Upstream registry auth_mode values with no dedicated BOCP enum (map in providers_registry_auth).
REGISTRY_MODES_WITHOUT_BOCP_ENUM: frozenset[str] = frozenset(
    {
        "MCP_OAUTH2",
        "MCP_OAUTH2_GENERIC",
        "BILL",
        "TBA",
        "SIGNATURE",
        "INSTALL_PLUGIN",
    }
)
