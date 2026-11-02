"""Ontology cumulative version history and snapshot restore."""

from __future__ import annotations


# ── version_cumulative.py ──
"""Cumulative ontology state from published version diffs (for compare / rollback)."""


from dataclasses import dataclass, field
from typing import Any

from basis.services.ontology.hub.draft_apply import as_draft_mapping
from basis.services.ontology.hub.draft_apply import structure_edges_from_diff
from basis.services.ontology.persistence.proposal_store import _get_field


def _diff_list(diff: Any, key: str) -> list[Any]:
    if diff is None:
        return []
    if hasattr(diff, key):
        return list(getattr(diff, key) or [])
    if isinstance(diff, dict):
        return list(diff.get(key) or [])
    return []


def _diff_dict(diff: Any, key: str) -> dict[str, Any]:
    if diff is None:
        return {}
    if hasattr(diff, key):
        raw = getattr(diff, key)
        return dict(raw or {}) if isinstance(raw, dict) else {}
    if isinstance(diff, dict):
        raw = diff.get(key) or {}
        return dict(raw) if isinstance(raw, dict) else {}
    return {}


def version_sort_key(version_id: str) -> tuple[int, ...] | tuple[str, ...]:
    text = str(version_id or "").strip()
    parts = text.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (text,)


def _edge_key(source: str, edge_type: str, target: str) -> tuple[str, str, str]:
    return (source.strip(), edge_type.strip(), target.strip())


@dataclass
class CumulativeOntologyState:
    classes: set[str] = field(default_factory=set)
    properties: set[str] = field(default_factory=set)
    individuals: set[str] = field(default_factory=set)
    class_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    property_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: set[tuple[str, str, str]] = field(default_factory=set)
    axioms: list[dict[str, Any]] = field(default_factory=list)

    def copy(self) -> CumulativeOntologyState:
        return CumulativeOntologyState(
            classes=set(self.classes),
            properties=set(self.properties),
            individuals=set(self.individuals),
            class_meta={k: dict(v) for k, v in self.class_meta.items()},
            property_meta={k: dict(v) for k, v in self.property_meta.items()},
            edges=set(self.edges),
            axioms=[dict(a) for a in self.axioms],
        )


def _merge_meta(target: dict[str, dict[str, Any]], uri: str, changes: Any) -> None:
    uri = str(uri or "").strip()
    if not uri:
        return
    row = dict(target.get(uri) or {})
    change_map = as_draft_mapping(changes)
    for key, value in change_map.items():
        row[key] = value
    target[uri] = row


def apply_diff_to_state(state: CumulativeOntologyState, diff: Any) -> None:
    for uri in _diff_list(diff, "removed_classes"):
        state.classes.discard(str(uri))
        state.class_meta.pop(str(uri), None)
    for uri in _diff_list(diff, "removed_properties"):
        state.properties.discard(str(uri))
        state.property_meta.pop(str(uri), None)
    for uri in _diff_list(diff, "removed_individuals"):
        state.individuals.discard(str(uri))

    for uri in _diff_list(diff, "added_classes"):
        text = str(uri).strip()
        if text:
            state.classes.add(text)
    for uri in _diff_list(diff, "added_properties"):
        text = str(uri).strip()
        if text:
            state.properties.add(text)
    for uri in _diff_list(diff, "added_individuals"):
        text = str(uri).strip()
        if text:
            state.individuals.add(text)

    for uri, changes in _diff_dict(diff, "modified_classes").items():
        text = str(uri).strip()
        if text:
            state.classes.add(text)
            _merge_meta(state.class_meta, text, changes)
    for uri, changes in _diff_dict(diff, "modified_properties").items():
        text = str(uri).strip()
        if text:
            state.properties.add(text)
            _merge_meta(state.property_meta, text, changes)

    for raw_edge in _diff_list(diff, "added_edges"):
        edge_map = as_draft_mapping(raw_edge)
        source = str(edge_map.get("source", "")).strip()
        target = str(edge_map.get("target", "")).strip()
        edge_type = str(edge_map.get("type", "")).strip()
        if source and target and edge_type:
            state.edges.add(_edge_key(source, edge_type, target))

    for edge in structure_edges_from_diff(diff):
        source = str(edge.get("source", "")).strip()
        target = str(edge.get("target", "")).strip()
        edge_type = str(edge.get("type", "")).strip()
        if source and target and edge_type:
            state.edges.add(_edge_key(source, edge_type, target))

    for raw in _diff_list(diff, "added_axioms"):
        axiom_map = as_draft_mapping(raw)
        if axiom_map:
            state.axioms.append(axiom_map)

    for raw in _diff_list(diff, "removed_axioms"):
        axiom_map = as_draft_mapping(raw)
        if axiom_map and axiom_map in state.axioms:
            state.axioms.remove(axiom_map)


def cumulative_state_at_version(
    version_entries: list[Any],
    version_id: str,
) -> CumulativeOntologyState:
    target = str(version_id or "").strip()
    if not target:
        raise ValueError("version_id is required")

    ordered = sorted(
        version_entries,
        key=lambda entry: version_sort_key(str(_get_field(entry, "version_id", ""))),
    )
    state = CumulativeOntologyState()
    seen_target = False
    for entry in ordered:
        vid = str(_get_field(entry, "version_id", "")).strip()
        diff = _get_field(entry, "diff_summary") or {}
        apply_diff_to_state(state, diff)
        if vid == target:
            seen_target = True
            break
    if not seen_target:
        raise KeyError(target)
    return state


def _meta_changed(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left != right


def diff_cumulative_states(
    from_state: CumulativeOntologyState,
    to_state: CumulativeOntologyState,
) -> dict[str, Any]:
    """Changes when moving from ``from_state`` to ``to_state`` (v1 → v2)."""
    added_classes = sorted(to_state.classes - from_state.classes)
    removed_classes = sorted(from_state.classes - to_state.classes)
    changed_classes: list[dict[str, Any]] = []
    for uri in sorted(from_state.classes & to_state.classes):
        left_meta = from_state.class_meta.get(uri, {})
        right_meta = to_state.class_meta.get(uri, {})
        if _meta_changed(left_meta, right_meta):
            changed_classes.append({"uri": uri, "from": left_meta, "to": right_meta})

    added_properties = sorted(to_state.properties - from_state.properties)
    removed_properties = sorted(from_state.properties - to_state.properties)
    changed_properties: list[dict[str, Any]] = []
    for uri in sorted(from_state.properties & to_state.properties):
        left_meta = from_state.property_meta.get(uri, {})
        right_meta = to_state.property_meta.get(uri, {})
        if _meta_changed(left_meta, right_meta):
            changed_properties.append({"uri": uri, "from": left_meta, "to": right_meta})

    added_individuals = sorted(to_state.individuals - from_state.individuals)
    removed_individuals = sorted(from_state.individuals - to_state.individuals)

    added_edges = [
        {"source": s, "type": t, "target": u}
        for s, t, u in sorted(to_state.edges - from_state.edges)
    ]
    removed_edges = [
        {"source": s, "type": t, "target": u}
        for s, t, u in sorted(from_state.edges - to_state.edges)
    ]

    return {
        "class_changes": {
            "added": added_classes,
            "removed": removed_classes,
            "changed": changed_classes,
        },
        "property_changes": {
            "added": added_properties,
            "removed": removed_properties,
            "changed": changed_properties,
        },
        "individual_changes": {
            "added": added_individuals,
            "removed": removed_individuals,
        },
        "edge_changes": {
            "added": added_edges,
            "removed": removed_edges,
        },
        "axiom_changes": {
            "added_count": max(0, len(to_state.axioms) - len(from_state.axioms)),
            "removed_count": max(0, len(from_state.axioms) - len(to_state.axioms)),
        },
    }


def compare_published_versions(
    version_entries: list[Any],
    version1: str,
    version2: str,
) -> dict[str, Any]:
    state1 = cumulative_state_at_version(version_entries, version1)
    state2 = cumulative_state_at_version(version_entries, version2)
    changes = diff_cumulative_states(state1, state2)
    changes["version1"] = version1
    changes["version2"] = version2
    changes["comparison_mode"] = "cumulative_snapshot"
    return changes

# ── version_restore.py ──
"""Build editor draft diffs to restore a published ontology version."""


from typing import Any

from basis.services.ontology.hub.registry_scope import edge_removal_ref
from basis.services.ontology.persistence.proposal_store import _get_field


def _latest_version_id(version_entries: list[Any]) -> str:
    if not version_entries:
        raise ValueError("no published versions")
    ordered = sorted(
        version_entries,
        key=lambda entry: version_sort_key(str(_get_field(entry, "version_id", ""))),
    )
    return str(_get_field(ordered[-1], "version_id", "")).strip()


def compare_changes_to_draft_diff(changes: dict[str, Any]) -> dict[str, Any]:
    """Map cumulative compare payload to ``DraftDiff``-shaped dict."""
    class_changes = changes.get("class_changes") or {}
    property_changes = changes.get("property_changes") or {}
    individual_changes = changes.get("individual_changes") or {}
    edge_changes = changes.get("edge_changes") or {}

    modified_classes: dict[str, dict[str, Any]] = {}
    for item in class_changes.get("changed") or []:
        if not isinstance(item, dict):
            continue
        uri = str(item.get("uri") or "").strip()
        to_meta = item.get("to")
        if uri and isinstance(to_meta, dict):
            modified_classes[uri] = dict(to_meta)

    modified_properties: dict[str, dict[str, Any]] = {}
    for item in property_changes.get("changed") or []:
        if not isinstance(item, dict):
            continue
        uri = str(item.get("uri") or "").strip()
        to_meta = item.get("to")
        if uri and isinstance(to_meta, dict):
            modified_properties[uri] = dict(to_meta)

    added_edges: list[dict[str, str]] = []
    for raw in edge_changes.get("added") or []:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "").strip()
        target = str(raw.get("target") or "").strip()
        edge_type = str(raw.get("type") or "").strip()
        if source and target and edge_type:
            added_edges.append({"source": source, "target": target, "type": edge_type})

    removed_edges: list[str] = []
    for raw in edge_changes.get("removed") or []:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source") or "").strip()
        target = str(raw.get("target") or "").strip()
        edge_type = str(raw.get("type") or "").strip()
        if source and target and edge_type:
            removed_edges.append(edge_removal_ref(source, edge_type, target))

    return {
        "added_classes": list(class_changes.get("added") or []),
        "removed_classes": list(class_changes.get("removed") or []),
        "modified_classes": modified_classes,
        "added_properties": list(property_changes.get("added") or []),
        "removed_properties": list(property_changes.get("removed") or []),
        "modified_properties": modified_properties,
        "added_individuals": list(individual_changes.get("added") or []),
        "removed_individuals": list(individual_changes.get("removed") or []),
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "added_axioms": [],
        "removed_axioms": [],
    }


def build_restore_draft_diff(
    version_entries: list[Any],
    target_version_id: str,
) -> dict[str, Any]:
    """Diff from current head published version to ``target_version_id`` (for editor draft)."""
    target = str(target_version_id or "").strip()
    if not target:
        raise ValueError("target_version is required")
    head = _latest_version_id(version_entries)
    if head == target:
        return {
            "head_version": head,
            "target_version": target,
            "already_at_target": True,
            "diff": {},
        }
    changes = compare_published_versions(version_entries, head, target)
    diff = compare_changes_to_draft_diff(changes)
    return {
        "head_version": head,
        "target_version": target,
        "already_at_target": False,
        "comparison_mode": changes.get("comparison_mode"),
        "diff": diff,
    }
