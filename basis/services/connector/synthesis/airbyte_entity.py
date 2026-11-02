"""Airbyte declarative connector manifests → BOCP entity actions (P2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from basis.services.connector.synthesis.paths import airbyte_connectors_root


def airbyte_manifest_path(service: str) -> Path | None:
    root = airbyte_connectors_root()
    if root is None:
        return None
    for name in (service, service.replace("_", "-")):
        candidate = root / name / "manifest.yaml"
        if candidate.is_file():
            return candidate
    return None


def load_airbyte_manifest_raw(service: str) -> dict[str, Any] | None:
    path = airbyte_manifest_path(service)
    if path is None:
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def merge_airbyte_entities(service: str) -> list[Any]:
    """Return BOCP entity actions from Airbyte when implemented (P2)."""
    _ = load_airbyte_manifest_raw(service)
    return []
