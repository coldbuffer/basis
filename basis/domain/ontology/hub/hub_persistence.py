"""Per-workspace ontology hub sidecar (registry, alignments, drafts, proposals, versions)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from basis.domain.graph.projection.snapshot_store import GraphPersistence, _atomic_replace, _workspace_write_lock

_HUB_SCHEMA_VERSION = 1


def _hub_path(persistence: GraphPersistence, workspace_id: str) -> Path:
    return persistence.graph_path(workspace_id).with_suffix(".ontology-hub.json")


def _serialize_store(store: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in store.items():
        if hasattr(value, "model_dump"):
            out[key] = value.model_dump(mode="json")
        else:
            out[key] = value
    return out


def _serialize_versions(versions: dict[str, Any]) -> dict[str, list[Any]]:
    serialized: dict[str, list[Any]] = {}
    for ontology_uri, entries in versions.items():
        row: list[Any] = []
        for entry in entries or []:
            if hasattr(entry, "model_dump"):
                row.append(entry.model_dump(mode="json"))
            else:
                row.append(entry)
        serialized[ontology_uri] = row
    return serialized


def _rehydrate_drafts(model: Any, raw: dict[str, Any]) -> dict[str, Any]:
    return {key: model.model_validate(value) for key, value in raw.items()}


def _rehydrate_proposals(model: Any, raw: dict[str, Any]) -> dict[str, Any]:
    return {key: model.model_validate(value) for key, value in raw.items()}


def _rehydrate_versions(model: Any, raw: dict[str, Any]) -> dict[str, list[Any]]:
    hydrated: dict[str, list[Any]] = {}
    for ontology_uri, entries in raw.items():
        hydrated[ontology_uri] = [model.model_validate(entry) for entry in (entries or [])]
    return hydrated


def ensure_ontology_hub_loaded(request: Any, workspace_id: str) -> None:
    """Load sidecar into app.state once per process (if present on disk)."""
    app_state = request.app.state
    loaded: set[str] = getattr(app_state, "_ontology_hub_loaded", set())
    if workspace_id in loaded:
        return

    persistence: GraphPersistence = app_state.graph_persistence
    path = _hub_path(persistence, workspace_id)
    backfill_needed = False
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
        if int(payload.get("schema_version", 0)) == _HUB_SCHEMA_VERSION:
            from basis.domain.ontology.hub.hub_models import (
                DraftResponse,
                ProposalResponse,
                VersionEntry,
            )

            app_state.ontology_registries[workspace_id] = dict(payload.get("registry") or {})
            app_state.ontology_alignments[workspace_id] = dict(payload.get("alignments") or {})
            app_state.ontology_drafts[workspace_id] = _rehydrate_drafts(DraftResponse, payload.get("drafts") or {})
            app_state.ontology_proposals[workspace_id] = _rehydrate_proposals(
                ProposalResponse, payload.get("proposals") or {}
            )
            app_state.ontology_versions[workspace_id] = _rehydrate_versions(
                VersionEntry, payload.get("versions") or {}
            )
            from basis.domain.ontology.hub.registry_ensure import backfill_registry_from_versions

            reg = app_state.ontology_registries[workspace_id]
            vers = app_state.ontology_versions[workspace_id]
            backfill_needed = bool(backfill_registry_from_versions(reg, vers))

    loaded.add(workspace_id)
    app_state._ontology_hub_loaded = loaded
    if backfill_needed:
        persist_ontology_hub(request, workspace_id)


def persist_ontology_hub(request: Any, workspace_id: str) -> None:
    """Write in-memory hub stores to the sidecar (no-op if never initialized)."""
    app_state = request.app.state
    loaded: set[str] = getattr(app_state, "_ontology_hub_loaded", set())
    if workspace_id not in loaded:
        return

    persistence: GraphPersistence = app_state.graph_persistence
    path = _hub_path(persistence, workspace_id)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    payload = {
        "schema_version": _HUB_SCHEMA_VERSION,
        "registry": dict(app_state.ontology_registries.get(workspace_id) or {}),
        "alignments": _serialize_store(app_state.ontology_alignments.get(workspace_id) or {}),
        "drafts": _serialize_store(app_state.ontology_drafts.get(workspace_id) or {}),
        "proposals": _serialize_store(app_state.ontology_proposals.get(workspace_id) or {}),
        "versions": _serialize_versions(app_state.ontology_versions.get(workspace_id) or {}),
    }
    with _workspace_write_lock(workspace_id):
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _atomic_replace(tmp, path)


def read_registry_snapshot(
    persistence: GraphPersistence,
    workspace_id: str,
) -> dict[str, Any] | None:
    """Return registry from the hub sidecar, or None if the sidecar file does not exist."""
    path = _hub_path(persistence, workspace_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if int(payload.get("schema_version", 0)) != _HUB_SCHEMA_VERSION:
        return {}
    return dict(payload.get("registry") or {})


def delete_ontology_hub(persistence: GraphPersistence, workspace_id: str) -> None:
    path = _hub_path(persistence, workspace_id)
    with _workspace_write_lock(workspace_id):
        if path.is_file():
            path.unlink()
