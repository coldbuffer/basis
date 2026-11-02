"""Map semantica GraphBuilder output into canonical ledger tables."""

from __future__ import annotations

from typing import Any

from basis.services.knowledge.store import KnowledgeStore
from basis.services.knowledge.pipeline.kg_apply import _entity_id, _rel_endpoints


def _entity_label(entity: dict[str, Any]) -> str:
    for key in ("name", "text", "id"):
        value = entity.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return "unknown"


def _surface_phrase(relationship: dict[str, Any]) -> str:
    for key in ("predicate", "type", "relation", "label"):
        value = relationship.get(key)
        if value is not None and str(value).strip():
            raw = str(value).strip()
            if raw.startswith("http://") or raw.startswith("https://"):
                return "related_to"
            return raw
    return "related_to"


def _quote_for_relationship(
    chunk_text: str, subject_label: str, object_label: str, surface: str
) -> tuple[str, int | None, int | None]:
    for candidate in (
        f"{subject_label} {surface} {object_label}",
        f"{subject_label} {object_label}",
        surface,
    ):
        if not candidate:
            continue
        start = chunk_text.find(candidate)
        if start >= 0:
            end = start + len(candidate)
            return candidate, start, end
    if surface and surface in chunk_text:
        start = chunk_text.index(surface)
        return surface, start, start + len(surface)
    return surface or subject_label, None, None


def apply_kg_to_ledger(
    knowledge: KnowledgeStore,
    workspace_id: str,
    version_id: str,
    chunk_id: str,
    chunk_text: str,
    kg: dict[str, Any],
    *,
    proposed_by: str,
    statement_status: str = "pending",
) -> dict[str, int]:
    """Persist entities/relationships as ledger rows; record drops for invalid output."""
    entities = kg.get("entities") or []
    relationships = kg.get("relationships") or []
    entities_written = 0
    statements_written = 0
    drops_recorded = 0

    label_to_entity_id: dict[str, str] = {}

    for entity in entities:
        if not isinstance(entity, dict):
            knowledge.add_extraction_drop(
                workspace_id,
                version_id,
                chunk_id,
                "invalid_entity",
                {"reason": "not_a_dict"},
            )
            drops_recorded += 1
            continue
        label = _entity_label(entity)
        if label == "unknown" or label == chunk_text.strip():
            continue
        node_key = _entity_id(entity)
        if node_key in label_to_entity_id:
            continue
        entity_id = knowledge.get_or_create_entity_by_label(workspace_id, label)
        label_to_entity_id[node_key] = entity_id
        label_to_entity_id[label] = entity_id
        entities_written += 1

    for relationship in relationships:
        if not isinstance(relationship, dict):
            knowledge.add_extraction_drop(
                workspace_id,
                version_id,
                chunk_id,
                "invalid_relationship",
                {"reason": "not_a_dict"},
            )
            drops_recorded += 1
            continue
        source_id, target_id = _rel_endpoints(relationship)
        if not source_id or not target_id:
            knowledge.add_extraction_drop(
                workspace_id,
                version_id,
                chunk_id,
                "missing_endpoints",
                {"relationship": relationship},
            )
            drops_recorded += 1
            continue

        subject_label = str(source_id)
        object_label = str(target_id)
        subject_entity = label_to_entity_id.get(subject_label) or knowledge.get_or_create_entity_by_label(
            workspace_id, subject_label
        )
        object_entity = label_to_entity_id.get(object_label) or knowledge.get_or_create_entity_by_label(
            workspace_id, object_label
        )
        label_to_entity_id.setdefault(subject_label, subject_entity)
        label_to_entity_id.setdefault(object_label, object_entity)

        surface = _surface_phrase(relationship)
        confidence = relationship.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = None

        quote, quote_start, quote_end = _quote_for_relationship(
            chunk_text, subject_label, object_label, surface
        )
        if knowledge.has_statement_on_chunk(
            workspace_id,
            chunk_id,
            subject_entity,
            surface,
            object_entity_id=object_entity,
            object_value=None,
        ):
            continue

        try:
            knowledge.add_open_statement(
                workspace_id,
                subject_id=subject_entity,
                surface_phrase=surface,
                object_entity_id=object_entity,
                object_value=None,
                status=statement_status,
                proposed_by=proposed_by,
                chunk_id=chunk_id,
                quote=quote,
                quote_start=quote_start,
                quote_end=quote_end,
                confidence=confidence,
            )
            statements_written += 1
        except Exception as exc:
            knowledge.add_extraction_drop(
                workspace_id,
                version_id,
                chunk_id,
                "statement_rejected",
                {"message": str(exc), "relationship": relationship},
            )
            drops_recorded += 1

    return {
        "ledger_entities_written": entities_written,
        "ledger_statements_written": statements_written,
        "ledger_drops_recorded": drops_recorded,
    }
