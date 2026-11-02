"""Hand-authored BOCP manifests (source of truth until upstream merge replaces them)."""

from __future__ import annotations

from collections.abc import Callable

from basis.services.connector.adapters.rest.providers.github import github_manifest
from basis.services.connector.adapters.rest.providers.hubspot import hubspot_manifest
from basis.services.connector.adapters.rest.providers.gitlab import gitlab_manifest
from basis.services.connector.adapters.rest.providers.jira import jira_manifest
from basis.services.connector.adapters.rest.providers.notion import notion_manifest
from basis.services.connector.adapters.rest.providers.slack import slack_manifest
from basis.services.connector.adapters.sql.providers import sql_provider_manifests
from basis.services.connector.manifest.manifest_schema import ConnectorManifest

GeneratorFn = Callable[[], ConnectorManifest]

_SQL_BY_SERVICE: dict[str, ConnectorManifest] = {
    m.service: m for m in sql_provider_manifests()
}


def generator_for_service(service: str) -> GeneratorFn | None:
    if service in _SQL_BY_SERVICE:
        return lambda s=service: _SQL_BY_SERVICE[s]
    if service == "github":
        return github_manifest
    if service == "slack":
        return slack_manifest
    if service == "notion":
        return notion_manifest
    if service == "hubspot":
        return hubspot_manifest
    if service == "gitlab":
        return gitlab_manifest
    if service == "jira":
        return jira_manifest
    return None


def manifest_from_generator(service: str) -> ConnectorManifest | None:
    fn = generator_for_service(service)
    if fn is None:
        return None
    manifest = fn()
    if manifest.service != service:
        raise ValueError(
            f"Generator for '{service}' produced service '{manifest.service}'"
        )
    return manifest


def all_generator_services() -> list[str]:
    return sorted(
        {*_SQL_BY_SERVICE.keys(), "github", "gitlab", "hubspot", "jira", "slack", "notion"}
    )
