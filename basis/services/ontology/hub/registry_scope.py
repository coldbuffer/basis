"""Ontology registry URI scoping, edge references, restrictions, and auto-ensure."""

from __future__ import annotations


# ── edge_refs.py ──
"""Stable references for removing ontology structure edges (id or source|type|target)."""


from typing import Any

EDGE_REF_SEP = "|"


def edge_removal_ref(source: str, edge_type: str, target: str) -> str:
    return f"{source.strip()}{EDGE_REF_SEP}{edge_type.strip()}{EDGE_REF_SEP}{target.strip()}"


def parse_edge_removal_ref(ref: str) -> tuple[str, str, str] | None:
    text = str(ref or "").strip()
    if EDGE_REF_SEP not in text:
        return None
    parts = text.split(EDGE_REF_SEP, 2)
    if len(parts) != 3:
        return None
    source, edge_type, target = (part.strip() for part in parts)
    if not source or not edge_type or not target:
        return None
    return source, edge_type, target


def find_edge_ids_for_triple(graph: Any, source: str, edge_type: str, target: str) -> list[str]:
    if graph is None or not hasattr(graph, "find_edges"):
        return []
    matches: list[str] = []
    for edge in graph.find_edges():
        if not isinstance(edge, dict):
            continue
        if (
            str(edge.get("source") or "") == source
            and str(edge.get("target") or "") == target
            and str(edge.get("type") or "") == edge_type
        ):
            edge_id = str(edge.get("id") or "").strip()
            if edge_id:
                matches.append(edge_id)
    return matches

# ── restriction_types.py ──
"""OWL 2 class restriction kinds supported by the ontology editor draft apply path."""


from dataclasses import dataclass
from typing import Literal

PropertyScope = Literal["object", "data"]
FillerRole = Literal["class", "individual", "datatype", "literal", "none"]
CardinalityMode = Literal["none", "qualified", "unqualified"]


@dataclass(frozen=True)
class RestrictionKindSpec:
    """How a draft restriction row maps to ``owl:Restriction`` node properties and edges."""

    owl_predicate: str
    filler_role: FillerRole
    cardinality_mode: CardinalityMode
    filler_edge_type: str | None


def restriction_spec(property_scope: str, restriction_type: str) -> RestrictionKindSpec | None:
    scope = (property_scope or "object").strip().lower()
    if scope not in ("object", "data"):
        scope = "object"
    key = (scope, restriction_type.strip())
    return _SPECS.get(key)


_SPECS: dict[tuple[str, str], RestrictionKindSpec] = {}

for _scope, _type, _pred, _filler, _card, _edge in (
    ("object", "someValuesFrom", "owl:someValuesFrom", "class", "none", "owl:someValuesFrom"),
    ("object", "allValuesFrom", "owl:allValuesFrom", "class", "none", "owl:allValuesFrom"),
    ("object", "hasValue", "owl:hasValue", "individual", "none", "owl:hasValue"),
    (
        "object",
        "minQualifiedCardinality",
        "owl:minQualifiedCardinality",
        "class",
        "qualified",
        "owl:onClass",
    ),
    (
        "object",
        "maxQualifiedCardinality",
        "owl:maxQualifiedCardinality",
        "class",
        "qualified",
        "owl:onClass",
    ),
    (
        "object",
        "qualifiedCardinality",
        "owl:qualifiedCardinality",
        "class",
        "qualified",
        "owl:onClass",
    ),
    ("object", "minCardinality", "owl:minCardinality", "none", "unqualified", None),
    ("object", "maxCardinality", "owl:maxCardinality", "none", "unqualified", None),
    ("object", "cardinality", "owl:cardinality", "none", "unqualified", None),
    ("data", "someValuesFrom", "owl:someValuesFrom", "datatype", "none", "owl:someValuesFrom"),
    ("data", "allValuesFrom", "owl:allValuesFrom", "datatype", "none", "owl:allValuesFrom"),
    ("data", "hasValue", "owl:hasValue", "literal", "none", None),
    (
        "data",
        "minQualifiedCardinality",
        "owl:minQualifiedCardinality",
        "datatype",
        "qualified",
        "owl:onDataRange",
    ),
    (
        "data",
        "maxQualifiedCardinality",
        "owl:maxQualifiedCardinality",
        "datatype",
        "qualified",
        "owl:onDataRange",
    ),
    (
        "data",
        "qualifiedCardinality",
        "owl:qualifiedCardinality",
        "datatype",
        "qualified",
        "owl:onDataRange",
    ),
    ("data", "minCardinality", "owl:minCardinality", "none", "unqualified", None),
    ("data", "maxCardinality", "owl:maxCardinality", "none", "unqualified", None),
    ("data", "cardinality", "owl:cardinality", "none", "unqualified", None),
):
    _SPECS[(_scope, _type)] = RestrictionKindSpec(
        owl_predicate=_pred,
        filler_role=_filler,
        cardinality_mode=_card,
        filler_edge_type=_edge,
    )


def supported_restriction_type_keys() -> frozenset[tuple[str, str]]:
    return frozenset(_SPECS.keys())

# ── registry_scope.py ──
"""Which ontology schema nodes belong in the workspace graph projection."""


from typing import Any

from basis.services.ontology.hub.catalog import _node_belongs_to_ontology, published_entity_uris_for_ontology
from basis.services.ontology.hub.registry_write import _entry_enabled


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

# ── registry_ensure.py ──
"""Ensure hub registry (catalog) reflects published ontologies."""


from datetime import datetime, timezone
from typing import Any

from basis.services.ontology.persistence.proposal_store import _get_field, _set_field


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
    from basis.services.ontology.browse.graph_scope import _iter_session_nodes

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
