"""Build editor draft diffs to restore a published ontology version."""

from __future__ import annotations

from typing import Any

from basis.domain.ontology.hub.edge_refs import edge_removal_ref
from basis.domain.ontology.hub.proposal_store import _get_field
from basis.domain.ontology.hub.version_cumulative import (
    compare_published_versions,
    version_sort_key,
)


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
