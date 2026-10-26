"""Governor align_store merge when hub was loaded before sidecar existed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.ontology.hub.scoped_state import merged_governor_align_store
from tests.integration.ontology_hub_sidecar import write_alignment_sidecar


def test_merged_align_store_uses_sidecar_when_memory_empty(tmp_path: Path) -> None:
    workspace_id = "ws-merge-align"
    persistence = GraphPersistence(tmp_path)
    write_alignment_sidecar(
        persistence,
        workspace_id,
        {
            "a1": {
                "id": "a1",
                "source_uri": "http://example.org/a#X",
                "target_uri": "http://example.org/b#Y",
                "source_label": "X",
                "target_label": "Y",
                "relation": "skos:exactMatch",
                "confidence": 1.0,
            }
        },
    )

    app_state = MagicMock()
    app_state.ontology_alignments = {workspace_id: {}}
    app_state.ontology_registries = {workspace_id: {}}
    app_state.ontology_drafts = {workspace_id: {}}
    app_state.ontology_proposals = {workspace_id: {}}
    app_state.ontology_versions = {workspace_id: {}}
    app_state._ontology_hub_loaded = {workspace_id}
    app_state.graph_persistence = persistence

    request = MagicMock()
    request.app.state = app_state

    merged = merged_governor_align_store(request, workspace_id)
    assert "a1" in merged
    assert merged["a1"]["source_label"] == "X"
