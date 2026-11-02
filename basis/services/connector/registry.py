"""In-memory registry and loader for Basis Open Connector Protocol (BOCP) providers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from basis.services.connector.manifest.manifest_schema import ConnectorManifest
from basis.services.connector.manifest.provider_bundle import (
    ProviderBundlePaths,
    is_provider_manifest_file,
    load_provider_bundle,
    provider_manifest_path,
)


def default_providers_dir() -> Path:
    return Path(__file__).resolve().parent / "providers"


class ConnectorCatalog:
    """Loaded registry of BOCP ConnectorManifest objects."""

    def __init__(
        self,
        manifests: list[ConnectorManifest],
        *,
        bundle_paths: dict[str, ProviderBundlePaths] | None = None,
    ) -> None:
        by_service: dict[str, ConnectorManifest] = {}
        for item in manifests:
            by_service[item.service] = item
        self._by_service = dict(sorted(by_service.items()))
        self._bundle_paths = bundle_paths or {}

    @classmethod
    def load_from_directory(cls, directory: Path | None = None) -> ConnectorCatalog:
        providers_root = directory or default_providers_dir()
        manifests: dict[str, ConnectorManifest] = {}
        bundle_paths: dict[str, ProviderBundlePaths] = {}

        if providers_root.is_dir():
            for child in sorted(providers_root.iterdir()):
                if is_provider_manifest_file(child):
                    try:
                        loaded = load_provider_bundle(child)
                    except (FileNotFoundError, ValueError):
                        continue
                    manifests[loaded.manifest.service] = loaded.manifest
                    bundle_paths[loaded.manifest.service] = loaded.paths
                    continue
                if not child.is_dir():
                    continue
                if provider_manifest_path(providers_root, child.name).is_file():
                    continue
                try:
                    loaded = load_provider_bundle(child)
                except (FileNotFoundError, ValueError):
                    continue
                manifests[loaded.manifest.service] = loaded.manifest
                bundle_paths[loaded.manifest.service] = loaded.paths

        return cls(list(manifests.values()), bundle_paths=bundle_paths)

    def provider_bundle_paths(self, service: str) -> ProviderBundlePaths | None:
        return self._bundle_paths.get(service)

    def openapi_path(self, service: str) -> Path | None:
        paths = self._bundle_paths.get(service)
        return paths.openapi if paths else None

    def list_manifests(
        self,
        *,
        category: str | None = None,
        auth_mode: str | None = None,
        has_streams_only: bool = False,
        query: str | None = None,
    ) -> list[ConnectorManifest]:
        results = list(self._by_service.values())
        if category:
            cat_lower = category.lower()
            results = [
                m
                for m in results
                if any(c.lower() == cat_lower for c in m.categories)
            ]
        if auth_mode:
            results = [
                m
                for m in results
                if any(a.auth_mode == auth_mode for a in m.auth)
            ]
        if has_streams_only:
            results = [m for m in results if len(m.streams) > 0]
        if query and query.strip():
            q = query.strip().lower()
            results = [
                m
                for m in results
                if q in m.service.lower()
                or q in m.display_name.lower()
                or (m.description and q in m.description.lower())
            ]
        return results

    def get(self, service: str) -> ConnectorManifest | None:
        return self._by_service.get(service)

    def service_ids(self) -> list[str]:
        return list(self._by_service.keys())

    def category_labels(self) -> list[str]:
        labels: set[str] = set()
        for manifest in self._by_service.values():
            labels.update(manifest.categories)
        return sorted(labels, key=str.lower)

    def category_breakdown(
        self,
        *,
        platform_allowed: list[str] | str = "*",
    ) -> list[dict[str, int | str]]:
        """Count providers per primary category (first tag), with platform-enabled totals."""
        from basis.services.connector.vault.allowlist import is_platform_provider_allowed

        totals: dict[str, int] = {}
        enabled: dict[str, int] = {}
        for manifest in self._by_service.values():
            label = (manifest.categories[0] if manifest.categories else "other").lower()
            totals[label] = totals.get(label, 0) + 1
            if is_platform_provider_allowed(manifest.service, platform_allowed):
                enabled[label] = enabled.get(label, 0) + 1
        return [
            {
                "category": key,
                "total": totals[key],
                "enabled": enabled.get(key, 0),
            }
            for key in sorted(totals.keys())
        ]

    def __len__(self) -> int:
        return len(self._by_service)

    def summary_stats(self) -> dict[str, int]:
        total_streams = sum(len(m.streams) for m in self._by_service.values())
        total_tools = sum(len(m.tools) for m in self._by_service.values())
        with_streams = sum(1 for m in self._by_service.values() if m.streams)
        return {
            "providers": len(self._by_service),
            "providers_with_streams": with_streams,
            "total_streams": total_streams,
            "total_tools": total_tools,
        }


@lru_cache(maxsize=1)
def get_connector_catalog() -> ConnectorCatalog:
    return ConnectorCatalog.load_from_directory()


