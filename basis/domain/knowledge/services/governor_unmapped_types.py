"""Enqueue review items for ledger type labels without confirmed class mappings (L2)."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from basis.domain.errors import AdminError
from basis.domain.knowledge.store import KnowledgeStore

UNMAPPED_ENTITY_TYPE_KIND = "unmapped_entity_type"
UNMAPPED_ENTITY_TYPE_SUBJECT_TYPE = "entity_type_label"


def unmapped_entity_type_subject_id(label: str) -> str:
    return hashlib.sha256(label.strip().casefold().encode()).hexdigest()[:32]


def resolve_unmapped_entity_type_reviews(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    label: str,
    resolved_by: str,
    rationale: str | None = None,
) -> list[str]:
    """Close open governor items for ``label`` after a class mapping is confirmed."""
    needle = label.strip()
    if not needle:
        return []
    item = knowledge.find_open_review_item(
        workspace_id,
        kind=UNMAPPED_ENTITY_TYPE_KIND,
        subject_type=UNMAPPED_ENTITY_TYPE_SUBJECT_TYPE,
        subject_id=unmapped_entity_type_subject_id(needle),
    )
    if item is None:
        return []
    resolved = knowledge.resolve_review_item(
        workspace_id,
        item["id"],
        status="approved",
        resolved_by=resolved_by,
        rationale=rationale or "Resolved by confirmed class mapping",
    )
    return [resolved["id"]]


def maybe_resolve_unmapped_entity_type_for_mapping(
    knowledge: KnowledgeStore,
    workspace_id: str,
    mapping: dict[str, Any],
    *,
    resolved_by: str,
    rationale: str | None = None,
) -> list[str]:
    if str(mapping.get("status") or "") != "confirmed":
        return []
    if str(mapping.get("target_kind") or "") != "class":
        return []
    label = str(mapping.get("signature") or "").strip()
    if not label:
        return []
    return resolve_unmapped_entity_type_reviews(
        knowledge,
        workspace_id,
        label=label,
        resolved_by=resolved_by,
        rationale=rationale,
    )


def _confirmed_class_mapping_signatures(knowledge: KnowledgeStore, workspace_id: str) -> set[str]:
    mapped: set[str] = set()
    for row in knowledge.list_mappings(workspace_id, status="confirmed", limit=500):
        if str(row.get("target_kind") or "") != "class":
            continue
        signature = str(row.get("signature") or "").strip()
        if signature:
            mapped.add(signature.casefold())
    return mapped


def scan_unmapped_entity_type_labels(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    align_store: dict[str, Any] | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Enqueue open review items for taxonomic object labels lacking a confirmed type mapping."""
    from basis.domain.ontology.hub.catalog import suggest_alignment_target_uris

    mapped = _confirmed_class_mapping_signatures(knowledge, workspace_id)
    labels = knowledge.list_entity_type_object_labels(workspace_id, limit=limit)
    created: list[str] = []
    skipped = 0
    for label in labels:
        if label.casefold() in mapped:
            continue
        vocabulary_hits: list[dict[str, Any]] = []
        if align_store is not None:
            vocabulary_hits = suggest_alignment_target_uris(
                align_store,
                label=label,
                entity_type="class",
                limit=5,
            )
        subject_id = unmapped_entity_type_subject_id(label)
        try:
            item = knowledge.create_review_item(
                workspace_id,
                kind=UNMAPPED_ENTITY_TYPE_KIND,
                subject_type=UNMAPPED_ENTITY_TYPE_SUBJECT_TYPE,
                subject_id=subject_id,
                payload={
                    "label": label,
                    "vocabulary_alignment_suggestions": vocabulary_hits,
                },
                priority=3,
            )
            created.append(item["id"])
        except AdminError as exc:
            if exc.code == "review_exists":
                skipped += 1
                continue
            raise
    return {"created": len(created), "skipped": skipped, "item_ids": created}
