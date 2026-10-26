"""In-memory graph projection load/save/rebuild (transport-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from basis.domain.graph.projection.projector import apply_rebuild_to_session
from basis.domain.graph.projection.session import GraphSession
from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.knowledge.store import KnowledgeStore

if TYPE_CHECKING:
    from basis.domain.graph.session.registry import GraphSessionRegistry


@dataclass
class GraphProjectionBindings:
    graphs: dict[str, GraphSession]
    persistence: GraphPersistence
    knowledge: KnowledgeStore
    graph_session_registry: GraphSessionRegistry
    persist_ontology_hub: Callable[[str], None]
    broadcast_projection: Callable[[str, int], None]
    load_ontology_registry: Callable[[str], dict[str, Any] | None] | None = None


def _ontology_registry_for_workspace(
    bindings: GraphProjectionBindings,
    workspace_id: str,
) -> dict[str, Any] | None:
    if bindings.load_ontology_registry is None:
        return None
    return bindings.load_ontology_registry(workspace_id)


def apply_rebuild_for_workspace(
    bindings: GraphProjectionBindings,
    workspace_id: str,
    session: GraphSession,
    *,
    include_version_ids: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    from basis.domain.ontology.hub.registry_scope import published_entity_uris_for_enabled_ontologies
    from basis.domain.ontology.hub.schema_sync import read_hub_registry_and_versions

    ontology_registry = _ontology_registry_for_workspace(bindings, workspace_id)
    published_uris: set[str] | None = None
    hub_snapshot = read_hub_registry_and_versions(bindings.persistence, workspace_id)
    if hub_snapshot is not None:
        hub_registry, hub_versions = hub_snapshot
        registry_for_preserve = ontology_registry if ontology_registry is not None else hub_registry
        published_uris = published_entity_uris_for_enabled_ontologies(
            registry_for_preserve or {},
            hub_versions,
        )

    meta = apply_rebuild_to_session(
        bindings.knowledge,
        workspace_id,
        session,
        include_version_ids=include_version_ids,
        ontology_registry=ontology_registry,
        ontology_published_entity_uris=published_uris,
    )
    from basis.domain.ontology.hub.schema_sync import repair_schema_after_projection_rebuild

    repair_registry = ontology_registry
    repair_versions = hub_snapshot[1] if hub_snapshot is not None else None
    if repair_registry is None and hub_snapshot is not None:
        repair_registry = hub_snapshot[0]
    repair_schema_after_projection_rebuild(
        session,
        bindings.persistence,
        workspace_id,
        registry=repair_registry,
        versions=repair_versions,
    )
    return meta


def graph_session_for_workspace(bindings: GraphProjectionBindings, workspace_id: str) -> GraphSession:
    session = bindings.graphs.get(workspace_id)
    if session is not None:
        return session

    session, meta = bindings.persistence.load_snapshot(workspace_id)
    ledger = bindings.knowledge.get_projection_state(workspace_id)
    stale = meta is None or meta.projection_revision < ledger["revision"]
    has_ledger_docs = bool(bindings.knowledge.list_ready_documents_for_projection(workspace_id))
    if stale and (ledger["revision"] > 0 or has_ledger_docs):
        apply_rebuild_for_workspace(bindings, workspace_id, session)
        ledger = bindings.knowledge.get_projection_state(workspace_id)
        bindings.persistence.save(
            workspace_id,
            session,
            projection_revision=ledger["revision"],
            schema_version=ledger["schema_version"],
        )
    bindings.graphs[workspace_id] = session
    return session


def save_graph(bindings: GraphProjectionBindings, workspace_id: str, *, sync_ledger: bool = True) -> None:
    session = graph_session_for_workspace(bindings, workspace_id)
    knowledge = bindings.knowledge
    if sync_ledger:
        from basis.domain.knowledge.services.graph_sync import sync_graph_to_ledger

        synced = sync_graph_to_ledger(knowledge, workspace_id, session)
        if synced["entities_created"] or synced["statements_created"]:
            apply_rebuild_for_workspace(bindings, workspace_id, session)
    ledger = knowledge.get_projection_state(workspace_id)
    bindings.persistence.save(
        workspace_id,
        session,
        projection_revision=ledger["revision"],
        schema_version=ledger["schema_version"],
    )
    bindings.graph_session_registry.invalidate(workspace_id)
    bindings.persist_ontology_hub(workspace_id)
    bindings.broadcast_projection(workspace_id, int(ledger["revision"]))


def rebuild_graph_projection(bindings: GraphProjectionBindings, workspace_id: str) -> dict:
    bindings.graph_session_registry.invalidate(workspace_id)
    session = graph_session_for_workspace(bindings, workspace_id)
    meta = apply_rebuild_for_workspace(bindings, workspace_id, session)
    save_graph(bindings, workspace_id)
    return meta
