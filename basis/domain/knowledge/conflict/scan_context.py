"""Optional graph / ontology hub inputs for conflict SHACL scans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConflictScanContext:
    """When set, enables Ontology Hub SHACL (L3) in addition to ledger synthetic shapes."""

    graph_session: Any
    ontology_registry: dict[str, Any]
    ontology_uri: str | None = None


def load_hub_registry_from_disk(data_dir: Path, workspace_id: str) -> dict[str, Any]:
    from basis.domain.graph.projection.snapshot_store import GraphPersistence
    from basis.domain.ontology.hub.hub_persistence import _hub_path

    persistence = GraphPersistence(data_dir)
    path = _hub_path(persistence, workspace_id)
    if not path.is_file():
        return {}
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if int(payload.get("schema_version", 0)) != 1:
        return {}
    registry = payload.get("registry")
    return dict(registry) if isinstance(registry, dict) else {}
