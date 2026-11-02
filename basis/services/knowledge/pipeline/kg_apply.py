"""Project semantica GraphBuilder output into a Basis GraphSession."""

from __future__ import annotations

from typing import Any

from basis.services.graph.projection.session import GraphSession


def _entity_id(entity: dict[str, Any]) -> str:
    for key in ("id", "entity_id", "name", "text"):
        value = entity.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return "unknown"


def _rel_endpoints(relationship: dict[str, Any]) -> tuple[str | None, str | None]:
    source = relationship.get("source") or relationship.get("source_id") or relationship.get("subject")
    target = relationship.get("target") or relationship.get("target_id") or relationship.get("object")
    if source is None or target is None:
        return None, None
    return str(source), str(target)


def apply_kg_to_session(
    session: GraphSession,
    kg: dict[str, Any],
    *,
    doc_id: str,
    link_document: bool = True,
) -> dict[str, int]:
    """Merge builder entities/relationships into the per-workspace ContextGraph."""
    entities = kg.get("entities") or []
    relationships = kg.get("relationships") or []
    entities_added = 0
    relationships_added = 0

    for entity in entities:
        if not isinstance(entity, dict):
            continue
        node_id = _entity_id(entity)
        node_type = str(entity.get("type") or entity.get("label") or "entity")
        name = entity.get("name") or entity.get("text") or node_id
        metadata = entity.get("metadata") if isinstance(entity.get("metadata"), dict) else {}
        session.add_node(
            node_id,
            node_type,
            name=name,
            document_id=doc_id,
            confidence=entity.get("confidence"),
            **metadata,
        )
        if link_document:
            session.add_edge(node_id, doc_id, "mentioned_in", document_id=doc_id)
        entities_added += 1

    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue
        source_id, target_id = _rel_endpoints(relationship)
        if not source_id or not target_id:
            continue
        edge_type = str(relationship.get("type") or relationship.get("predicate") or "related_to")
        metadata = relationship.get("metadata") if isinstance(relationship.get("metadata"), dict) else {}
        session.add_edge(
            source_id,
            target_id,
            edge_type,
            document_id=doc_id,
            confidence=relationship.get("confidence"),
            **metadata,
        )
        relationships_added += 1

    return {
        "entities_added": entities_added,
        "relationships_added": relationships_added,
    }
