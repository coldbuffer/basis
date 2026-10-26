"""Per-workspace in-memory ontology registry, alignments, drafts, proposals, versions."""

from __future__ import annotations

from typing import Any

from basis.domain.ontology.hub.hub_persistence import ensure_ontology_hub_loaded


class OntologyHubState:
    """Ensure per-workspace hub stores exist and load sidecar persistence once per process."""

    def __init__(self, request: Any, workspace_id: str) -> None:
        self._request = request
        self._workspace_id = workspace_id

    def __enter__(self) -> OntologyHubState:
        app_state = self._request.app.state
        if not hasattr(app_state, "ontology_alignments"):
            app_state.ontology_alignments = {}
        if not hasattr(app_state, "ontology_registries"):
            app_state.ontology_registries = {}
        if not hasattr(app_state, "ontology_drafts"):
            app_state.ontology_drafts = {}
        if not hasattr(app_state, "ontology_proposals"):
            app_state.ontology_proposals = {}
        if not hasattr(app_state, "ontology_versions"):
            app_state.ontology_versions = {}
        app_state.ontology_alignments.setdefault(self._workspace_id, {})
        app_state.ontology_registries.setdefault(self._workspace_id, {})
        app_state.ontology_drafts.setdefault(self._workspace_id, {})
        app_state.ontology_proposals.setdefault(self._workspace_id, {})
        app_state.ontology_versions.setdefault(self._workspace_id, {})
        ensure_ontology_hub_loaded(self._request, self._workspace_id)
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def merged_governor_align_store(request: Any, workspace_id: str) -> dict[str, Any]:
    """Published vocabulary alignments for governor scans (hub state: SQL + sidecar hydrate)."""
    with OntologyHubState(request, workspace_id):
        return dict(request.app.state.ontology_alignments.get(workspace_id) or {})
