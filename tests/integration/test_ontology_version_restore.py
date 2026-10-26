"""Restore draft diff from published head to an older version."""

from __future__ import annotations

from basis.domain.ontology.hub.version_restore import build_restore_draft_diff, compare_changes_to_draft_diff
from basis.domain.ontology.hub.version_cumulative import compare_published_versions


def test_restore_diff_reverses_head_to_older() -> None:
    entries = [
        {"version_id": "1.0.0", "diff_summary": {"added_classes": ["urn:ex:A"], "added_properties": ["urn:ex:p"]}},
        {
            "version_id": "1.1.0",
            "diff_summary": {"added_classes": ["urn:ex:B"], "added_properties": ["urn:ex:q"]},
        },
    ]
    built = build_restore_draft_diff(entries, "1.0.0")
    assert built["head_version"] == "1.1.0"
    assert built["target_version"] == "1.0.0"
    assert built["already_at_target"] is False
    diff = built["diff"]
    assert "urn:ex:B" in diff["removed_classes"]
    assert "urn:ex:q" in diff["removed_properties"]
    assert "urn:ex:A" not in diff["removed_classes"]


def test_compare_changes_to_draft_diff_maps_edges() -> None:
    changes = compare_published_versions(
        [
            {"version_id": "1.0.0", "diff_summary": {}},
            {
                "version_id": "1.1.0",
                "diff_summary": {
                    "added_edges": [
                        {"source": "urn:ex:A", "target": "urn:ex:B", "type": "rdfs:subClassOf"},
                    ],
                },
            },
        ],
        "1.0.0",
        "1.1.0",
    )
    draft = compare_changes_to_draft_diff(changes)
    assert len(draft["added_edges"]) == 1
    assert draft["added_edges"][0]["type"] == "rdfs:subClassOf"
