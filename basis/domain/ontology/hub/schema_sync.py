"""Re-materialize published ontology schema into the workspace graph session."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.ontology.hub.draft_apply import apply_removals, materialize_restrictions
from basis.domain.ontology.hub.draft_structure import structure_edges_from_diff
from basis.domain.ontology.hub.proposal_store import _get_field
from basis.domain.ontology.hub.registry_ensure import _ensure_ontology_root_node
from basis.domain.ontology.hub.registry_write import _entry_enabled


def _diff_list(diff: Any, key: str) -> list[Any]:
    if diff is None:
        return []
    if hasattr(diff, key):
        value = getattr(diff, key)
        return list(value or [])
    if isinstance(diff, dict):
        return list(diff.get(key) or [])
    return []


def _diff_dict(diff: Any, key: str) -> dict[str, Any]:
    if diff is None:
        return {}
    if hasattr(diff, key):
        value = getattr(diff, key)
        return dict(value or {}) if isinstance(value, dict) else {}
    if isinstance(diff, dict):
        raw = diff.get(key) or {}
        return dict(raw) if isinstance(raw, dict) else {}
    return {}


def _label_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _label_for_uri(diff: Any, uri: str, modified_key: str) -> str:
    modified = _diff_dict(diff, modified_key)
    entry = modified.get(uri) or {}
    label = entry.get("label")
    if label is not None and str(label).strip():
        return str(label).strip()
    return _label_from_uri(uri)


def _entity_properties(ontology_uri: str, label: str) -> dict[str, str]:
    return {"rdfs:label": label, "scheme_uri": ontology_uri}


def _session_add_nodes(session: Any, nodes: list[dict[str, Any]]) -> int:
    if hasattr(session, "add_nodes"):
        return int(session.add_nodes(nodes) or 0)
    added = 0
    for node in nodes:
        props = dict(node.get("properties") or {})
        created = session.add_node(
            str(node["id"]),
            str(node["type"]),
            content=node.get("content"),
            **props,
        )
        if created:
            added += 1
    return added


def _session_add_nodes_and_edges(
    session: Any,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[int, int]:
    if hasattr(session, "add_nodes_and_edges"):
        nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
        return int(nodes_added or 0), int(edges_added or 0)
    nodes_added = _session_add_nodes(session, nodes)
    edges_added = 0
    for edge in edges:
        props = dict(edge.get("properties") or {})
        if session.add_edge(
            str(edge["source"]),
            str(edge["target"]),
            str(edge.get("type") or "related_to"),
            **props,
        ):
            edges_added += 1
    return nodes_added, edges_added


def _version_diff(entry: Any) -> Any:
    return _get_field(entry, "diff_summary") or {}


def apply_ontology_diff_to_session(
    session: Any,
    ontology_uri: str,
    diff: Any,
    *,
    apply_removals_first: bool = True,
) -> dict[str, int]:
    """Apply one published draft diff to the graph (same as proposal publish)."""
    nodes_removed = 0
    edges_removed = 0
    if apply_removals_first:
        nodes_removed, edges_removed = apply_removals(session, diff, diff_list=_diff_list)

    nodes_added = 0
    edges_added = 0

    class_nodes = []
    for class_uri in _diff_list(diff, "added_classes"):
        label = _label_for_uri(diff, class_uri, "modified_classes")
        class_nodes.append(
            {
                "id": class_uri,
                "type": "owl:Class",
                "content": label,
                "properties": _entity_properties(ontology_uri, label),
            }
        )
    modified_classes = _diff_dict(diff, "modified_classes")
    added_class_set = set(_diff_list(diff, "added_classes"))
    for class_uri, changes in modified_classes.items():
        if class_uri in added_class_set:
            continue
        label = changes.get("label")
        if label is None or not str(label).strip():
            continue
        label_str = str(label).strip()
        class_nodes.append(
            {
                "id": class_uri,
                "type": "owl:Class",
                "content": label_str,
                "properties": _entity_properties(ontology_uri, label_str),
            }
        )
    if class_nodes:
        nodes_added += _session_add_nodes(session, class_nodes)

    property_nodes = []
    for prop_uri in _diff_list(diff, "added_properties"):
        label = _label_for_uri(diff, prop_uri, "modified_properties")
        property_nodes.append(
            {
                "id": prop_uri,
                "type": "owl:ObjectProperty",
                "content": label,
                "properties": _entity_properties(ontology_uri, label),
            }
        )
    modified_properties = _diff_dict(diff, "modified_properties")
    added_property_set = set(_diff_list(diff, "added_properties"))
    for prop_uri, changes in modified_properties.items():
        if prop_uri in added_property_set:
            continue
        label = changes.get("label")
        if label is None or not str(label).strip():
            continue
        label_str = str(label).strip()
        property_nodes.append(
            {
                "id": prop_uri,
                "type": "owl:ObjectProperty",
                "content": label_str,
                "properties": _entity_properties(ontology_uri, label_str),
            }
        )
    if property_nodes:
        nodes_added += _session_add_nodes(session, property_nodes)

    individual_nodes = []
    for ind_uri in _diff_list(diff, "added_individuals"):
        label = _label_from_uri(ind_uri)
        individual_nodes.append(
            {
                "id": ind_uri,
                "type": "owl:NamedIndividual",
                "content": label,
                "properties": _entity_properties(ontology_uri, label),
            }
        )
    if individual_nodes:
        nodes_added += _session_add_nodes(session, individual_nodes)

    restriction_nodes, restriction_edges = materialize_restrictions(
        ontology_uri,
        _diff_list(diff, "added_restrictions"),
    )
    if restriction_nodes:
        nodes_added += _session_add_nodes(session, restriction_nodes)

    edges_to_add: list[dict[str, Any]] = list(restriction_edges)
    edges_to_add.extend(structure_edges_from_diff(diff))

    if edges_to_add:
        _, added = _session_add_nodes_and_edges(session, [], edges_to_add)
        edges_added += added

    return {
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "nodes_removed": nodes_removed,
        "edges_removed": edges_removed,
    }


def _ontology_has_core_schema(
    session: Any,
    registry: dict[str, Any],
    versions: dict[str, Any] | None,
    ontology_uri: str,
) -> bool:
    from basis.domain.ontology.browse.graph_scope import collect_core_nodes, known_ontology_uris

    known = known_ontology_uris(session, registry)
    if ontology_uri not in known:
        return True
    return bool(collect_core_nodes(session, ontology_uri, known, versions=versions))


def materialize_published_schema_for_ontology(
    session: Any,
    registry: dict[str, Any],
    versions: dict[str, Any],
    ontology_uri: str,
) -> dict[str, Any]:
    """Replay published version diffs when schema nodes are missing from the graph."""
    ontology_uri = str(ontology_uri or "").strip()
    totals = {"nodes_added": 0, "edges_added": 0, "nodes_removed": 0, "edges_removed": 0, "versions_applied": 0}
    if not ontology_uri:
        return totals

    entries = versions.get(ontology_uri) or []
    for entry in entries:
        diff = _version_diff(entry)
        if not diff:
            continue
        chunk = apply_ontology_diff_to_session(session, ontology_uri, diff)
        totals["versions_applied"] += 1
        for key in ("nodes_added", "edges_added", "nodes_removed", "edges_removed"):
            totals[key] += int(chunk.get(key, 0))

    entry = registry.get(ontology_uri) or {}
    name = str(_get_field(entry, "name") or ontology_uri)
    description = _get_field(entry, "description")
    totals["ontology_root_nodes_added"] = _ensure_ontology_root_node(
        session,
        ontology_uri,
        name,
        str(description) if description else None,
    )
    return totals


def sync_enabled_ontology_schema(
    session: Any,
    registry: dict[str, Any],
    versions: dict[str, Any] | None,
) -> dict[str, Any]:
    """Repair missing schema for enabled registry ontologies that have published versions."""
    versions = versions or {}
    repaired: list[dict[str, Any]] = []
    for key, entry in registry.items():
        if not _entry_enabled(entry):
            continue
        uri = str(_get_field(entry, "uri", key) or key).strip()
        if not uri or not (versions.get(uri) or []):
            continue
        if _ontology_has_core_schema(session, registry, versions, uri):
            continue
        stats = materialize_published_schema_for_ontology(session, registry, versions, uri)
        stats["ontology_uri"] = uri
        repaired.append(stats)
    return {"repaired": bool(repaired), "ontologies": repaired}


def _hub_sidecar_path(persistence: GraphPersistence, workspace_id: str) -> Path:
    return persistence.graph_path(workspace_id).with_suffix(".ontology-hub.json")


def read_hub_registry_and_versions(
    persistence: GraphPersistence,
    workspace_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    path = _hub_sidecar_path(persistence, workspace_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if int(payload.get("schema_version", 0)) != 1:
        return None
    return dict(payload.get("registry") or {}), dict(payload.get("versions") or {})


def repair_schema_after_projection_rebuild(
    session: Any,
    persistence: GraphPersistence,
    workspace_id: str,
    *,
    registry: dict[str, Any] | None = None,
    versions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loaded = read_hub_registry_and_versions(persistence, workspace_id)
    if loaded is None and registry is None:
        return {"repaired": False}
    disk_registry, disk_versions = loaded if loaded is not None else ({}, {})
    reg = registry if registry is not None else disk_registry
    vers = versions if versions is not None else disk_versions
    if not reg and not vers:
        return {"repaired": False}
    return sync_enabled_ontology_schema(session, reg, vers)


def ensure_ontology_schema_materialized(
    session: Any,
    registry: dict[str, Any],
    versions: dict[str, Any] | None,
    ontology_uri: str,
) -> dict[str, Any]:
    """Ensure one ontology has schema nodes before hub graph reads."""
    uri = str(ontology_uri or "").strip()
    if not uri or _ontology_has_core_schema(session, registry, versions, uri):
        return {"repaired": False}
    stats = materialize_published_schema_for_ontology(session, registry, versions or {}, uri)
    return {"repaired": True, "ontology_uri": uri, **stats}
