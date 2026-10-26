"""Which ontology schema nodes belong in the workspace graph projection."""

from __future__ import annotations

from typing import Any

from basis.domain.ontology.hub.catalog import _node_belongs_to_ontology, published_entity_uris_for_ontology
from basis.domain.ontology.hub.registry_write import _entry_enabled


def registry_ontology_uris(registry: dict[str, Any]) -> set[str]:
    uris: set[str] = set()
    for key, entry in registry.items():
        if isinstance(entry, dict):
            uri = str(entry.get("uri") or key).strip()
        else:
            uri = str(getattr(entry, "uri", None) or key).strip()
        if uri:
            uris.add(uri)
    return uris


def enabled_registry_ontology_uris(registry: dict[str, Any]) -> set[str]:
    enabled: set[str] = set()
    for key, entry in registry.items():
        if not _entry_enabled(entry):
            continue
        if isinstance(entry, dict):
            uri = str(entry.get("uri") or key).strip()
        else:
            uri = str(getattr(entry, "uri", None) or key).strip()
        if uri:
            enabled.add(uri)
    return enabled


def schema_node_dict(node: Any, node_type: str) -> dict[str, Any]:
    if isinstance(node, dict):
        return node
    props = dict(node.properties) if isinstance(getattr(node, "properties", None), dict) else {}
    node_id = str(getattr(node, "node_id", "") or "")
    return {"id": node_id, "type": node_type, "properties": props}


def should_preserve_schema_node(
    node: Any,
    node_type: str,
    ontology_registry: dict[str, Any] | None,
    *,
    published_entity_uris: set[str] | None = None,
) -> bool:
    """When registry is None (no hub sidecar), preserve all schema nodes (legacy/tests)."""
    if ontology_registry is None:
        return True
    enabled = enabled_registry_ontology_uris(ontology_registry)
    if not enabled:
        return False
    known = registry_ontology_uris(ontology_registry)
    node_dict = schema_node_dict(node, node_type)
    node_id = str(node_dict.get("id", "") or "")
    if published_entity_uris and node_id and node_id in published_entity_uris:
        return True
    return any(
        _node_belongs_to_ontology(node_dict, uri, known_ontology_uris=known)
        for uri in enabled
    )


def published_entity_uris_for_enabled_ontologies(
    ontology_registry: dict[str, Any],
    versions: dict[str, Any] | None,
) -> set[str]:
    if not ontology_registry or not versions:
        return set()
    uris: set[str] = set()
    for uri in enabled_registry_ontology_uris(ontology_registry):
        uris |= published_entity_uris_for_ontology(versions, uri)
    return uris
