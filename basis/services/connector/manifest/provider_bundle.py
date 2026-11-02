"""On-disk provider bundle: ``providers/{service}.yaml`` (+ optional sidecar spec files)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from basis.services.connector.manifest.manifest_schema import (
    ConnectorManifest,
    ProviderSpecReference,
)

LEGACY_CONNECTOR_FILE = "connector.yaml"

_MANIFEST_TOP_LEVEL_ORDER: tuple[str, ...] = (
    "version",
    "service",
    "display_name",
    "description",
    "categories",
    "homepage_url",
    "docs_url",
    "icon_url",
    "spec",
    "auth",
    "actions",
)

_ACTION_FIELD_ORDER: tuple[str, ...] = (
    "kind",
    "id",
    "name",
    "display_name",
    "description",
    "primary_key",
    "cursor_field",
    "default_label_field",
    "fields",
    "rest",
    "sql",
)


def provider_manifest_path(providers_root: Path, service: str) -> Path:
    return providers_root / f"{service}.yaml"


def is_provider_manifest_file(path: Path) -> bool:
    """True for ``{service}.yaml`` entries (not ``*.openapi.yaml`` sidecars)."""
    if not path.is_file():
        return False
    if path.suffix not in (".yaml", ".yml"):
        return False
    return "." not in path.stem


def _order_mapping_keys(data: dict[str, Any], preferred: tuple[str, ...]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in preferred:
        if key in data:
            ordered[key] = data[key]
    for key, value in data.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def manifest_wire_payload(manifest: ConnectorManifest) -> dict[str, Any]:
    """JSON-ready manifest dict with stable top-level and per-action key order."""
    payload = manifest.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    payload["version"] = manifest.version
    wire_actions = payload.get("actions")
    if isinstance(wire_actions, list):
        normalized: list[Any] = []
        for wire_action, action in zip(wire_actions, manifest.actions, strict=True):
            if isinstance(wire_action, dict):
                wire_action = dict(wire_action)
                wire_action["kind"] = action.kind
                normalized.append(_order_mapping_keys(wire_action, _ACTION_FIELD_ORDER))
            else:
                normalized.append(wire_action)
        payload["actions"] = normalized
    return _order_mapping_keys(payload, _MANIFEST_TOP_LEVEL_ORDER)


def rewrite_provider_manifest(providers_root: Path, manifest: ConnectorManifest) -> Path:
    """Rewrite ``providers/{service}.yaml`` only (does not touch optional attachments)."""
    providers_root.mkdir(parents=True, exist_ok=True)
    manifest_path = provider_manifest_path(providers_root, manifest.service)
    manifest_path.write_text(
        yaml.safe_dump(
            manifest_wire_payload(manifest),
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return manifest_path


def rewrite_connector_yaml(providers_root: Path, manifest: ConnectorManifest) -> Path:
    """Alias for :func:`rewrite_provider_manifest` (legacy name)."""
    return rewrite_provider_manifest(providers_root, manifest)


@dataclass(frozen=True)
class ProviderBundlePaths:
    bundle_root: Path
    manifest_path: Path
    protocol: str
    openapi: Path | None = None
    graphql: Path | None = None
    grpc: Path | None = None

    @property
    def provider_dir(self) -> Path:
        """Deprecated alias: bundle root (``providers/``), not a per-service subdirectory."""
        return self.bundle_root


@dataclass(frozen=True)
class LoadedProviderBundle:
    manifest: ConnectorManifest
    paths: ProviderBundlePaths


def effective_spec(manifest: ConnectorManifest) -> ProviderSpecReference:
    if manifest.spec is not None:
        return manifest.spec
    return ProviderSpecReference(protocol="rest", openapi=None)


def _resolve_relative(bundle_root: Path, rel: str) -> Path:
    path = (bundle_root / rel).resolve()
    root = bundle_root.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"Spec path escapes providers directory: {rel}")
    return path


def validate_provider_spec_files(
    bundle_root: Path, manifest: ConnectorManifest, *, manifest_path: Path
) -> ProviderBundlePaths:
    spec = effective_spec(manifest)
    openapi: Path | None = None
    graphql: Path | None = None
    grpc: Path | None = None

    if spec.protocol in ("sql", "mail"):
        return ProviderBundlePaths(
            bundle_root=bundle_root,
            manifest_path=manifest_path,
            protocol=spec.protocol,
        )

    if spec.protocol == "rest":
        if not spec.openapi:
            return ProviderBundlePaths(
                bundle_root=bundle_root,
                manifest_path=manifest_path,
                protocol=spec.protocol,
            )
        openapi = _resolve_relative(bundle_root, spec.openapi)
        if not openapi.is_file():
            raise FileNotFoundError(f"Missing REST/OpenAPI spec at {openapi}")
        return ProviderBundlePaths(
            bundle_root=bundle_root,
            manifest_path=manifest_path,
            protocol=spec.protocol,
            openapi=openapi,
        )

    if spec.protocol == "graphql":
        if not spec.graphql:
            raise ValueError(f"Provider {manifest.service}: spec.graphql path is required")
        graphql = _resolve_relative(bundle_root, spec.graphql)
        if not graphql.is_file():
            raise FileNotFoundError(f"Missing GraphQL schema at {graphql}")
        return ProviderBundlePaths(
            bundle_root=bundle_root,
            manifest_path=manifest_path,
            protocol=spec.protocol,
            graphql=graphql,
        )

    if spec.protocol == "grpc":
        if not spec.grpc:
            raise ValueError(f"Provider {manifest.service}: spec.grpc path is required")
        grpc = _resolve_relative(bundle_root, spec.grpc)
        if not grpc.is_file():
            raise FileNotFoundError(f"Missing gRPC proto at {grpc}")
        return ProviderBundlePaths(
            bundle_root=bundle_root,
            manifest_path=manifest_path,
            protocol=spec.protocol,
            grpc=grpc,
        )

    raise ValueError(f"Unsupported provider protocol: {spec.protocol}")


def stub_openapi_document(manifest: ConnectorManifest) -> dict[str, Any]:
    """Minimal OpenAPI 3 placeholder until a vendor spec is checked in."""
    server_url = "https://api.example.com"
    for auth in manifest.auth:
        base = auth.base_url
        if not base:
            continue
        stub = base.split("${", 1)[0].rstrip("/")
        if stub.startswith("http"):
            server_url = stub
            break
    return {
        "openapi": "3.0.3",
        "info": {
            "title": manifest.display_name,
            "version": str(manifest.version),
            "description": manifest.description or "",
        },
        "servers": [{"url": server_url}],
        "paths": {},
    }


def default_spec_for_manifest(manifest: ConnectorManifest) -> ProviderSpecReference:
    if manifest.spec is not None:
        return manifest.spec
    uses_sql = any(
        s.retriever.adapter == "sql_alchemy"
        or any(m.adapter == "sql_alchemy" for m in s.mutations.values())
        for s in manifest.streams
    )
    if uses_sql and manifest.streams:
        return ProviderSpecReference(protocol="sql", openapi=None)
    return ProviderSpecReference(protocol="rest", openapi=None)


def write_provider_bundle(providers_root: Path, manifest: ConnectorManifest) -> Path:
    """Write ``providers/{service}.yaml``; optional OpenAPI sidecar only when ``spec.openapi`` is set."""
    spec = default_spec_for_manifest(manifest)
    wire_manifest = manifest
    if manifest.spec is None:
        wire_manifest = manifest.model_copy(update={"spec": spec})
    manifest_path = rewrite_provider_manifest(providers_root, wire_manifest)

    if spec.protocol == "rest" and spec.openapi:
        openapi_path = _resolve_relative(providers_root, spec.openapi)
        openapi_path.write_text(
            yaml.safe_dump(
                stub_openapi_document(manifest),
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
    return manifest_path


def _manifest_path_from_location(location: Path) -> tuple[Path, Path]:
    """Return ``(manifest_path, bundle_root)`` from a manifest file or legacy bundle dir."""
    if location.is_file():
        return location, location.parent
    if location.is_dir():
        flat = provider_manifest_path(location.parent, location.name)
        if flat.is_file():
            return flat, location.parent
        legacy = location / LEGACY_CONNECTOR_FILE
        if legacy.is_file():
            return legacy, location
    raise FileNotFoundError(f"No provider manifest at {location}")


def load_provider_bundle(location: Path) -> LoadedProviderBundle:
    """Load ``providers/{service}.yaml`` (or legacy ``providers/{service}/connector.yaml``)."""
    manifest_path, bundle_root = _manifest_path_from_location(location)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing provider manifest at {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path}: manifest root must be an object")
    raw.setdefault("version", "2.0")
    manifest = ConnectorManifest.model_validate(raw)
    expected_stem = manifest.service
    if manifest_path.stem != expected_stem and manifest_path.name != LEGACY_CONNECTOR_FILE:
        raise ValueError(
            f"Manifest file {manifest_path.name!r} does not match service {expected_stem!r}"
        )
    if manifest_path.name == LEGACY_CONNECTOR_FILE and location.is_dir():
        if location.name != manifest.service:
            raise ValueError(
                f"Provider directory {location.name!r} does not match "
                f"connector.service {manifest.service!r}"
            )
    paths = validate_provider_spec_files(
        bundle_root, manifest, manifest_path=manifest_path
    )
    return LoadedProviderBundle(manifest=manifest, paths=paths)


def load_connector_manifest(location: Path) -> ConnectorManifest:
    """Load and validate provider manifest + required spec attachments."""
    return load_provider_bundle(location).manifest
