"""Background scheduled inbound sync for BOCP table mappings."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from basis.domain.graph.projection.projector import apply_rebuild_to_session
from basis.domain.ontology.hub.hub_persistence import read_registry_snapshot
from basis.domain.knowledge.schedulers.connector_mapping_poll_due import is_connector_mapping_poll_due
from basis.infra.runtime.observability.log_context import correlation_log_extra

logger = logging.getLogger(__name__)


def _rebuild_graph_projection_for_app(app: FastAPI, workspace_id: str) -> dict:
    """Rebuild graph projection from ledger after connector sync (no HTTP request)."""
    app.state.graph_session_registry.invalidate(workspace_id)
    knowledge = app.state.knowledge_store
    persistence = app.state.graph_persistence
    graphs = app.state.graphs
    session = graphs.get(workspace_id)
    if session is None:
        session, meta = persistence.load_snapshot(workspace_id)
        ledger = knowledge.get_projection_state(workspace_id)
        stale = meta is None or meta.projection_revision < ledger["revision"]
        has_ledger_docs = bool(knowledge.list_ready_documents_for_projection(workspace_id))
        if stale and (ledger["revision"] > 0 or has_ledger_docs):
            apply_rebuild_to_session(
                knowledge,
                workspace_id,
                session,
                ontology_registry=read_registry_snapshot(persistence, workspace_id),
            )
            ledger = knowledge.get_projection_state(workspace_id)
            persistence.save(
                workspace_id,
                session,
                projection_revision=ledger["revision"],
                schema_version=ledger["schema_version"],
            )
        graphs[workspace_id] = session
    meta = apply_rebuild_to_session(
        knowledge,
        workspace_id,
        session,
        ontology_registry=read_registry_snapshot(persistence, workspace_id),
    )
    ledger = knowledge.get_projection_state(workspace_id)
    persistence.save(
        workspace_id,
        session,
        projection_revision=ledger["revision"],
        schema_version=ledger["schema_version"],
    )
    app.state.ws_hub.try_broadcast(
        workspace_id,
        {
            "type": "projection_updated",
            "workspace_id": workspace_id,
            "projection_revision": ledger["revision"],
        },
    )
    return meta


def run_due_connector_syncs(app: FastAPI) -> int:
    """Run inbound sync for all due table mappings. Returns count executed."""
    knowledge = app.state.knowledge_store
    svc = knowledge.connector_sync_service()
    now = datetime.now(timezone.utc)
    ran = 0
    for workspace_id, mapping_id in knowledge.list_active_connector_table_mappings_global():
        rec = svc.get_table_mapping(workspace_id, mapping_id)
        if rec is None or not is_connector_mapping_poll_due(rec, now):
            continue
        try:
            stats = svc.sync_inbound_mapping(workspace_id, mapping_id)
            if stats.added > 0 or stats.updated > 0 or stats.deleted > 0:
                _rebuild_graph_projection_for_app(app, workspace_id)
            ran += 1
        except Exception:
            logger.exception(
                "scheduled connector sync failed kb=%s mapping=%s",
                workspace_id,
                mapping_id,
                extra=correlation_log_extra(workspace_id=workspace_id),
            )
    return ran
