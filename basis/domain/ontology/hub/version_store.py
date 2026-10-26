"""Ontology version list and compare (explicit per-workspace store)."""

from __future__ import annotations

import logging
from typing import Any

from basis.domain.errors import AdminError

logger = logging.getLogger(__name__)


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _version_field(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def list_versions(versions: dict[str, Any], ontology_uri: str) -> list[dict[str, Any]]:
    entries = versions.get(ontology_uri, [])
    return [_dump(entry) for entry in entries]


def compare_versions(
    session: Any,
    versions: dict[str, Any],
    ontology_uri: str,
    body: Any,
) -> dict[str, Any]:
    from basis.domain.ontology.hub.version_cumulative import compare_published_versions

    ontology_versions = versions.get(ontology_uri, [])
    v1_record = next(
        (v for v in ontology_versions if _version_field(v, "version_id") == body.version1),
        None,
    )
    v2_record = next(
        (v for v in ontology_versions if _version_field(v, "version_id") == body.version2),
        None,
    )
    if not v1_record or not v2_record:
        raise AdminError(404, "not_found", "One or both versions not found.")

    try:
        snapshot_diff = compare_published_versions(
            ontology_versions,
            str(body.version1),
            str(body.version2),
        )
    except KeyError:
        raise AdminError(404, "not_found", "One or both versions not found.") from None
    except Exception as exc:
        logger.error("Version comparison failed: %s", exc)
        raise AdminError(500, "internal_error", f"Version comparison failed: {exc}") from exc

    metadata_changes = {
        "version_id": {"from": body.version1, "to": body.version2},
        "author": {
            "from": _version_field(v1_record, "author"),
            "to": _version_field(v2_record, "author"),
        },
        "date": {
            "from": _version_field(v1_record, "date"),
            "to": _version_field(v2_record, "date"),
        },
        "state": {
            "from": _version_field(v1_record, "state"),
            "to": _version_field(v2_record, "state"),
        },
    }

    edge_changes = snapshot_diff.get("edge_changes") or {}
    individual_changes = snapshot_diff.get("individual_changes") or {}
    axiom_summary = snapshot_diff.get("axiom_changes") or {}

    return {
        "version1": body.version1,
        "version2": body.version2,
        "comparison_mode": snapshot_diff.get("comparison_mode", "cumulative_snapshot"),
        "metadata_changes": metadata_changes,
        "class_changes": snapshot_diff.get("class_changes") or {},
        "property_changes": snapshot_diff.get("property_changes") or {},
        "individual_changes": individual_changes,
        "edge_changes": edge_changes,
        "restriction_changes": {
            "added": [],
            "removed": [],
            "changed": [],
        },
        "axiom_changes": {
            "added": [],
            "removed": [],
            "changed": [],
            "added_count": axiom_summary.get("added_count", 0),
            "removed_count": axiom_summary.get("removed_count", 0),
        },
    }
