"""Import legacy ContextGraph JSON snapshots into the knowledge ledger."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from basis.services.graph.projection.snapshot_store import GraphPersistence
from basis.services.graph.projection.projector import apply_rebuild_to_session
from basis.services.graph.projection.session import GraphSession
from basis.services.knowledge.store import KnowledgeStore

_SKIP_NODE_TYPES = frozenset({"owl:Ontology", "projection_meta"})
_LEGACY_QUOTE = "legacy_import"
_LEGACY_PROPOSED_BY = "legacy_import"


@dataclass
class MigrationReport:
    workspace_id: str
    graph_path: str
    dry_run: bool
    documents_seen: int = 0
    documents_created: int = 0
    entities_seen: int = 0
    entities_mapped: int = 0
    statements_seen: int = 0
    statements_created: int = 0
    edges_skipped: list[dict[str, Any]] = field(default_factory=list)
    unmappable: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "graph_path": self.graph_path,
            "dry_run": self.dry_run,
            "documents_seen": self.documents_seen,
            "documents_created": self.documents_created,
            "entities_seen": self.entities_seen,
            "entities_mapped": self.entities_mapped,
            "statements_seen": self.statements_seen,
            "statements_created": self.statements_created,
            "edges_skipped": self.edges_skipped,
            "unmappable": self.unmappable,
        }


def _node_text(node: Any) -> str:
    content = node.content
    if isinstance(content, str) and content.strip():
        return content
    props = node.properties if isinstance(node.properties, dict) else {}
    for key in ("text", "name", "content", "rdfs:label"):
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return str(node.node_id)


def _collect_edges(session: GraphSession) -> list[Any]:
    edges = session.graph.edges
    if isinstance(edges, dict):
        return list(edges.values())
    return list(edges)


def migrate_legacy_graph(
    knowledge: KnowledgeStore,
    persistence: GraphPersistence,
    workspace_id: str,
    *,
    dry_run: bool = True,
    rebuild_projection: bool = False,
) -> MigrationReport:
    path = persistence.graph_path(workspace_id)
    report = MigrationReport(
        workspace_id=workspace_id,
        graph_path=str(path),
        dry_run=dry_run,
    )
    if not path.is_file():
        report.unmappable.append({"code": "no_graph_file", "detail": "snapshot missing"})
        return report

    session, _meta = persistence.load_snapshot(workspace_id)
    document_chunks: dict[str, str] = {}
    entity_map: dict[str, str] = {}
    document_ids: set[str] = set()
    entity_nodes: list[Any] = []

    for node in session.graph.nodes.values():
        node_id = node.node_id
        node_type = node.node_type
        if node_type == "document":
            report.documents_seen += 1
            document_ids.add(node_id)
            text = _node_text(node)
            if not dry_run:
                _doc_row, chunk_id, created = knowledge.ensure_legacy_document(
                    workspace_id,
                    external_key=node_id,
                    title=node_id,
                    text=text,
                )
                document_chunks[node_id] = chunk_id
                if created:
                    report.documents_created += 1
            continue

        if node_type in _SKIP_NODE_TYPES or node_id.startswith("literal:"):
            report.edges_skipped.append(
                {"kind": "node", "node_id": node_id, "reason": f"skip_type:{node_type}"}
            )
            continue

        report.entities_seen += 1
        entity_nodes.append(node)

    for node in entity_nodes:
        label = _node_text(node)
        if dry_run:
            continue
        entity_map[node.node_id] = knowledge.get_or_create_entity_by_label(workspace_id, label)
        report.entities_mapped += 1

    default_chunk_id: str | None = next(iter(document_chunks.values()), None)

    for edge in _collect_edges(session):
        edge_type = edge.edge_type
        source_id = edge.source_id
        target_id = edge.target_id
        if edge_type == "mentioned_in":
            report.edges_skipped.append(
                {
                    "kind": "edge",
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                    "reason": "mentioned_in",
                }
            )
            continue

        report.statements_seen += 1
        if source_id in document_ids or target_id in document_ids:
            report.unmappable.append(
                {
                    "code": "document_endpoint",
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                }
            )
            continue

        subject = entity_map.get(source_id)
        target_entity = entity_map.get(target_id)
        if not subject or not target_entity:
            report.unmappable.append(
                {
                    "code": "missing_entity",
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                }
            )
            continue

        chunk_id = document_chunks.get(source_id) or document_chunks.get(target_id) or default_chunk_id
        if chunk_id is None:
            report.unmappable.append(
                {
                    "code": "no_document_chunk",
                    "source": source_id,
                    "target": target_id,
                    "type": edge_type,
                }
            )
            continue

        if dry_run:
            continue

        if knowledge.has_statement_on_chunk(
            workspace_id,
            chunk_id,
            subject,
            edge_type,
            object_entity_id=target_entity,
            object_value=None,
        ):
            continue

        knowledge.add_open_statement(
            workspace_id,
            subject_id=subject,
            surface_phrase=edge_type,
            object_entity_id=target_entity,
            object_value=None,
            status="confirmed",
            proposed_by=_LEGACY_PROPOSED_BY,
            chunk_id=chunk_id,
            quote=_LEGACY_QUOTE,
        )
        report.statements_created += 1

    if not dry_run and rebuild_projection:
        apply_rebuild_to_session(knowledge, workspace_id, session)
        ledger = knowledge.get_projection_state(workspace_id)
        persistence.save(
            workspace_id,
            session,
            projection_revision=ledger["revision"],
            schema_version=ledger["schema_version"],
        )

    return report


def migrate_all_legacy_graphs(
    knowledge: KnowledgeStore,
    persistence: GraphPersistence,
    workspace_ids: list[str],
    *,
    dry_run: bool = True,
    rebuild_projection: bool = False,
) -> list[dict[str, Any]]:
    return [
        migrate_legacy_graph(
            knowledge,
            persistence,
            workspace_id,
            dry_run=dry_run,
            rebuild_projection=rebuild_projection,
        ).to_dict()
        for workspace_id in workspace_ids
    ]


def print_reports(reports: list[dict[str, Any]]) -> None:
    print(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))
