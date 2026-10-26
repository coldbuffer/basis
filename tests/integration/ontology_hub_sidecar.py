"""Shared helpers for ontology hub sidecar JSON in integration tests."""

from __future__ import annotations

import json
from typing import Any

from basis.domain.graph.projection.snapshot_store import GraphPersistence


def write_alignment_sidecar(
    persistence: GraphPersistence,
    workspace_id: str,
    alignments: dict[str, dict[str, Any]],
) -> None:
    path = persistence.graph_path(workspace_id).with_suffix(".ontology-hub.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "registry": {},
                "alignments": alignments,
                "drafts": {},
                "proposals": {},
                "versions": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
