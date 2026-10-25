"""Build optional ConflictScanContext from HTTP request (graph + ontology hub)."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from basis.domain.errors import AdminError
from basis.domain.graph.session.guard import require_graph_session
from basis.domain.knowledge.conflict.scan_context import (
    ConflictScanContext,
    load_hub_registry_from_disk,
)
from basis.domain.knowledge.store import KnowledgeStore
from basis.interface.http.shared.deps import graph_runtime_for


def build_conflict_scan_context(
    request: Request,
    workspace_id: str,
    knowledge: KnowledgeStore,
) -> ConflictScanContext | None:
    try:
        runtime = graph_runtime_for(request, workspace_id)
        session = require_graph_session(runtime)
    except AdminError as exc:
        if exc.code in ("graph_runtime_unavailable", "graph_session_required"):
            return None
        raise
    except Exception:
        return None

    app_state = request.app.state
    registries = getattr(app_state, "ontology_registries", None)
    registry: dict[str, Any] = {}
    if isinstance(registries, dict):
        registry = dict(registries.get(workspace_id) or {})
    if not registry:
        persistence = getattr(app_state, "graph_persistence", None)
        if persistence is not None:
            registry = load_hub_registry_from_disk(persistence._dir.parent, workspace_id)
    if not registry:
        return None
    config = knowledge.get_governance_config(workspace_id)
    return ConflictScanContext(
        graph_session=session,
        ontology_registry=registry,
        ontology_uri=config.governance_ontology_uri,
    )
