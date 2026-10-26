"""Cumulative ontology version compare (published diff replay)."""

from __future__ import annotations

import json
from pathlib import Path

from basis.domain.ontology.hub.version_cumulative import compare_published_versions


def test_compare_trellis_1_1_0_to_1_5_0_includes_edges_and_class_meta() -> None:
    hub_path = Path("data/graphs/54347e21-208a-4379-ac0a-b7adf0a36ee0.ontology-hub.json")
    if not hub_path.is_file():
        return
    hub = json.loads(hub_path.read_text(encoding="utf-8"))
    uri = "https://basis.local/ontology/trellis#"
    entries = hub.get("versions", {}).get(uri) or []
    if len(entries) < 5:
        return

    result = compare_published_versions(entries, "1.1.0", "1.5.0")
    edge_added = result["edge_changes"]["added"]
    assert len(edge_added) >= 30
    changed_classes = result["class_changes"]["changed"]
    assert len(changed_classes) >= 10
    assert result["comparison_mode"] == "cumulative_snapshot"


def test_compare_same_version_is_empty_delta() -> None:
    entries = [
        {
            "version_id": "1.1.0",
            "diff_summary": {
                "added_classes": ["urn:ex:Class"],
                "added_properties": ["urn:ex:prop"],
            },
        }
    ]
    result = compare_published_versions(entries, "1.1.0", "1.1.0")
    assert result["class_changes"]["added"] == []
    assert result["edge_changes"]["added"] == []
