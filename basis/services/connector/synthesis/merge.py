"""Merge upstream assets + generators into one ``ConnectorManifest`` per service."""

from __future__ import annotations

from typing import Any

from basis.services.connector.manifest.manifest_schema import ConnectorManifest, ProcedureActionSpec
from basis.services.connector.manifest.manifest_executor import INVOKE_OPERATION
from basis.services.connector.synthesis.airbyte_entity import merge_airbyte_entities
from basis.services.connector.synthesis.anyconnect_catalog import (
    anyconnect_app_metadata,
    load_connector_app,
    load_connector_catalog_procedures,
)
from basis.services.connector.synthesis.connector_catalog_auth import auth_specs_from_connector_app
from basis.services.connector.synthesis.generators import manifest_from_generator
from basis.services.connector.synthesis.providers_registry_auth import (
    auth_specs_from_providers_registry,
    load_provider_registry_block,
)


def _registry_catalog_display_name(service: str, raw: dict[str, Any]) -> str:
    for key in ("display_name", "name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return service.replace("-", " ").replace("_", " ").title()


def _overlay_auth(manifest: ConnectorManifest, auth_specs: list) -> ConnectorManifest:
    if not auth_specs:
        return manifest
    payload = manifest.model_dump(mode="python")
    payload["auth"] = [a.model_dump(mode="python") for a in auth_specs]
    return ConnectorManifest.model_validate(payload)


def _catalog_auth_specs(service: str, catalog_app: dict[str, Any] | None) -> list:
    if not catalog_app:
        return []
    return auth_specs_from_connector_app(catalog_app, service=service)


def _synthesis_auth_specs(
    service: str,
    *,
    catalog_app: dict[str, Any] | None,
    registry_auth: list,
    overlay_registry_auth: bool,
    prefer_catalog_auth: bool,
) -> list:
    """OpenConnector catalog ``auth[]`` first when enabled; else registry overlay."""
    if not overlay_registry_auth:
        return []
    catalog_auth = _catalog_auth_specs(service, catalog_app) if prefer_catalog_auth else []
    if catalog_auth:
        return catalog_auth
    return registry_auth if registry_auth else []


def _auth_for_catalog_only_manifest(
    service: str,
    *,
    catalog_app: dict[str, Any] | None,
    registry_auth: list,
    prefer_catalog_auth: bool,
) -> list:
    if prefer_catalog_auth:
        catalog_auth = _catalog_auth_specs(service, catalog_app)
        if catalog_auth:
            return catalog_auth
    return registry_auth


def _procedure_invoke_path(procedure: ProcedureActionSpec) -> str:
    if procedure.mail is not None:
        return procedure.mail.action
    if procedure.rest is None:
        return ""
    op = procedure.rest.operations.get(INVOKE_OPERATION)
    if op is None:
        return ""
    return op.path or ""


def _invoke_ready_procedures(procedures: list[ProcedureActionSpec]) -> list[ProcedureActionSpec]:
    return [p for p in procedures if _procedure_invoke_path(p)]


def _overlay_anyconnect_procedures(
    manifest: ConnectorManifest,
    procedures: list[ProcedureActionSpec],
    meta: dict[str, Any],
) -> ConnectorManifest:
    payload = manifest.model_dump(mode="python")
    if meta.get("display_name"):
        payload["display_name"] = meta["display_name"]
    if meta.get("description"):
        payload["description"] = meta["description"]
    if meta.get("categories"):
        payload["categories"] = meta["categories"]
    if meta.get("homepage_url"):
        payload["homepage_url"] = meta["homepage_url"]
    if meta.get("docs_url"):
        payload["docs_url"] = meta["docs_url"]
    existing = list(payload.get("actions") or [])
    entity_actions = [a for a in existing if a.get("kind") == "entity"]
    proc_payload = [p.model_dump(mode="python") for p in procedures]
    payload["actions"] = entity_actions + proc_payload
    return ConnectorManifest.model_validate(payload)


def merge_service(
    service: str,
    *,
    ship_tier: str | None = None,
    prefer_anyconnect_procedures: bool = True,
    prefer_connector_catalog: bool | None = None,
    catalog_procedures_only: bool = False,
    overlay_registry_auth: bool = True,
) -> ConnectorManifest:
    """
    Build a provider manifest for ``service``.

    Order: generator baseline → OpenConnector catalog auth → registry auth fallback
    → connector catalog procedures → Airbyte entities.
    """
    service = service.strip().lower()
    prefer_catalog_procedures = (
        prefer_connector_catalog
        if prefer_connector_catalog is not None
        else prefer_anyconnect_procedures
    )
    registry_auth = auth_specs_from_providers_registry(service)
    catalog_app = load_connector_app(service)
    prefer_catalog_auth = prefer_catalog_procedures
    synthesis_auth = _synthesis_auth_specs(
        service,
        catalog_app=catalog_app,
        registry_auth=registry_auth,
        overlay_registry_auth=overlay_registry_auth,
        prefer_catalog_auth=prefer_catalog_auth,
    )
    catalog_only_auth = _auth_for_catalog_only_manifest(
        service,
        catalog_app=catalog_app,
        registry_auth=registry_auth,
        prefer_catalog_auth=prefer_catalog_auth,
    )
    manifest = (
        None if catalog_procedures_only else manifest_from_generator(service)
    )

    ac_loaded = (
        load_connector_catalog_procedures(service)
        if prefer_catalog_procedures
        else None
    )
    ac_meta: dict[str, Any] | None = None
    ac_all: list[ProcedureActionSpec] = []
    ac_ready: list[ProcedureActionSpec] = []
    if ac_loaded is not None:
        ac_meta, ac_all = ac_loaded
        ac_ready = _invoke_ready_procedures(ac_all)

    if manifest is None:
        if ac_ready:
            if not catalog_only_auth:
                raise ValueError(
                    f"Service '{service}' has no auth; add OpenConnector catalog auth, "
                    "providers registry, or a generator auth block"
                )
            assert ac_meta is not None
            manifest = ConnectorManifest(
                service=service,
                display_name=ac_meta.get("display_name") or service,
                description=ac_meta.get("description"),
                categories=ac_meta.get("categories") or [],
                homepage_url=ac_meta.get("homepage_url"),
                docs_url=ac_meta.get("docs_url"),
                auth=catalog_only_auth,
                actions=ac_ready,
            )
        elif catalog_only_auth:
            raw = load_provider_registry_block(service) or {}
            meta = anyconnect_app_metadata(catalog_app) if catalog_app else {}
            manifest = ConnectorManifest(
                service=service,
                display_name=meta.get("display_name")
                or _registry_catalog_display_name(service, raw),
                description=meta.get("description"),
                categories=meta.get("categories") or [],
                homepage_url=meta.get("homepage_url"),
                docs_url=meta.get("docs_url"),
                auth=catalog_only_auth,
                actions=[],
            )
        else:
            raise ValueError(
                f"Unknown service '{service}' (no generator, connector catalog, "
                "or upstream auth)"
            )
    else:
        if synthesis_auth:
            manifest = _overlay_auth(manifest, synthesis_auth)
        if (
            ac_ready
            and ac_meta is not None
            and prefer_catalog_procedures
            and len(ac_ready) == len(ac_all)
        ):
            manifest = _overlay_anyconnect_procedures(manifest, ac_ready, ac_meta)

    airbyte_entities = merge_airbyte_entities(service)
    if airbyte_entities:
        payload = manifest.model_dump(mode="python")
        existing_entities = [
            a for a in payload.get("actions") or [] if a.get("kind") == "entity"
        ]
        proc = [a for a in payload.get("actions") or [] if a.get("kind") == "procedure"]
        payload["actions"] = existing_entities + [
            e.model_dump(mode="python") for e in airbyte_entities
        ] + proc
        manifest = ConnectorManifest.model_validate(payload)

    if ship_tier:
        payload = manifest.model_dump(mode="python")
        payload["x-basis-ship-tier"] = ship_tier
        manifest = ConnectorManifest.model_validate(payload)

    return manifest
