"""Ensure hub registry (catalog) reflects published ontologies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from basis.domain.ontology.hub.proposal_store import _get_field, _set_field


def _label_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1] or uri


def _registry_key(registry: dict[str, Any], ontology_uri: str) -> str | None:
    if ontology_uri in registry:
        return ontology_uri
    for key, entry in registry.items():
        entry_uri = _get_field(entry, "uri", key)
        if str(entry_uri).strip() == ontology_uri:
            return str(key)
    return None


def _display_name(proposal: Any, draft: Any, ontology_uri: str) -> str:
    summary = str(_get_field(proposal, "summary") or _get_field(draft, "summary") or "").strip()
    if summary:
        first_line = summary.splitlines()[0].strip()
        if len(first_line) <= 200:
            return first_line
        return first_line[:197] + "..."
    return _label_from_uri(ontology_uri)


def _ensure_ontology_root_node(session: Any, ontology_uri: str, name: str, description: str | None) -> int:
    from basis.domain.ontology.browse.graph_scope import _iter_session_nodes

    for node in _iter_session_nodes(session):
        if node.get("id") == ontology_uri:
            return 0
    root = {
        "id": ontology_uri,
        "type": "owl:Ontology",
        "content": name,
        "properties": {
            "rdfs:label": name,
            "rdfs:comment": description or "",
            "namespace": ontology_uri.rsplit("#", 1)[0] if "#" in ontology_uri else ontology_uri,
        },
    }
    if hasattr(session, "add_nodes"):
        return int(session.add_nodes([root]) or 0)
    props = dict(root.get("properties") or {})
    return 1 if session.add_node(root["id"], root["type"], content=root.get("content"), **props) else 0


def ensure_ontology_registry_on_publish(
    session: Any,
    registry: dict[str, Any],
    ontology_uri: str,
    *,
    proposal: Any,
    draft: Any,
) -> dict[str, Any]:
    """Register ontology_uri in hub catalog if missing; ensure owl:Ontology root exists."""
    ontology_uri = str(ontology_uri or "").strip()
    if not ontology_uri:
        return {"registered": False, "reason": "missing_ontology_uri"}

    name = _display_name(proposal, draft, ontology_uri)
    description = str(_get_field(draft, "summary") or _get_field(proposal, "summary") or "").strip() or None
    now = datetime.now(timezone.utc).isoformat()
    key = _registry_key(registry, ontology_uri)
    registered = False

    if key is None:
        registry[ontology_uri] = {
            "uri": ontology_uri,
            "name": name,
            "description": description,
            "format": "turtle",
            "status": "active",
            "version": _get_field(proposal, "version") or "0.1.0",
            "class_count": 0,
            "loaded_at": now,
            "enabled": True,
            "tags": [],
        }
        key = ontology_uri
        registered = True
    else:
        entry = registry[key]
        if isinstance(entry, dict):
            entry["status"] = "active"
            if not entry.get("name"):
                entry["name"] = name
            if description and not entry.get("description"):
                entry["description"] = description
        else:
            if _get_field(entry, "status") != "active":
                _set_field(entry, "status", "active")

    root_added = _ensure_ontology_root_node(session, ontology_uri, name, description)
    return {"registered": registered, "registry_key": key, "ontology_root_nodes_added": root_added}


def backfill_registry_from_versions(registry: dict[str, Any], versions: dict[str, Any]) -> int:
    """Add catalog rows for ontology URIs that have published versions but no registry entry."""
    added = 0
    now = datetime.now(timezone.utc).isoformat()
    for ontology_uri, entries in versions.items():
        uri = str(ontology_uri or "").strip()
        if not uri or not entries:
            continue
        if _registry_key(registry, uri) is not None:
            continue
        latest = entries[-1]
        author = _get_field(latest, "author")
        name = _label_from_uri(uri)
        registry[uri] = {
            "uri": uri,
            "name": name,
            "description": f"Backfilled from version {_get_field(latest, 'version_id', '')}",
            "format": "turtle",
            "status": "active",
            "version": str(_get_field(latest, "version_id") or "0.1.0"),
            "class_count": 0,
            "loaded_at": now,
            "enabled": True,
            "tags": [],
            "author": author,
        }
        added += 1
    return added
