"""Review-gated vocabulary alignment publish (L1 proposal → approve)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from basis.domain.errors import AdminError
from basis.domain.knowledge.store import KnowledgeStore

VOCABULARY_ALIGNMENT_REVIEW_KIND = "vocabulary_alignment_change"
VOCABULARY_ALIGNMENT_REVIEW_SUBJECT_TYPE = "alignment_proposal"


def _proposal_subject_id(action: str, **parts: Any) -> str:
    payload = json.dumps({"action": action, **parts}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _upsert_payload(
    *,
    source_uri: str,
    target_uri: str,
    relation: str,
    source_label: str | None = None,
    target_label: str | None = None,
    confidence: float = 1.0,
    provenance: str | None = None,
    source: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    return {
        "action": "upsert",
        "source_uri": source_uri,
        "target_uri": target_uri,
        "relation": relation,
        "source_label": source_label,
        "target_label": target_label,
        "confidence": confidence,
        "provenance": provenance,
        "source": source,
        "reviewer": reviewer,
    }


def propose_vocabulary_alignment_upsert(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    source_uri: str,
    target_uri: str,
    relation: str,
    source_label: str | None = None,
    target_label: str | None = None,
    confidence: float = 1.0,
    provenance: str | None = None,
    source: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    payload = _upsert_payload(
        source_uri=source_uri,
        target_uri=target_uri,
        relation=relation,
        source_label=source_label,
        target_label=target_label,
        confidence=confidence,
        provenance=provenance,
        source=source,
        reviewer=reviewer,
    )
    subject_id = _proposal_subject_id("upsert", source_uri=source_uri, target_uri=target_uri, relation=relation)
    try:
        item = knowledge.create_review_item(
            workspace_id,
            kind=VOCABULARY_ALIGNMENT_REVIEW_KIND,
            subject_type=VOCABULARY_ALIGNMENT_REVIEW_SUBJECT_TYPE,
            subject_id=subject_id,
            payload=payload,
        )
    except AdminError as exc:
        if exc.code != "review_exists":
            raise
        item = knowledge.find_open_review_item(
            workspace_id,
            kind=VOCABULARY_ALIGNMENT_REVIEW_KIND,
            subject_type=VOCABULARY_ALIGNMENT_REVIEW_SUBJECT_TYPE,
            subject_id=subject_id,
        )
        if item is None:
            raise
    return {
        "status": "proposed",
        "review_item_id": item["id"],
        "proposal_subject_id": subject_id,
        "payload": payload,
    }


def propose_vocabulary_alignment_delete(
    knowledge: KnowledgeStore,
    workspace_id: str,
    alignment_id: str,
    *,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"action": "delete", "alignment_id": alignment_id}
    if snapshot:
        payload["alignment"] = snapshot
    subject_id = _proposal_subject_id("delete", alignment_id=alignment_id)
    try:
        item = knowledge.create_review_item(
            workspace_id,
            kind=VOCABULARY_ALIGNMENT_REVIEW_KIND,
            subject_type=VOCABULARY_ALIGNMENT_REVIEW_SUBJECT_TYPE,
            subject_id=subject_id,
            payload=payload,
        )
    except AdminError as exc:
        if exc.code != "review_exists":
            raise
        item = knowledge.find_open_review_item(
            workspace_id,
            kind=VOCABULARY_ALIGNMENT_REVIEW_KIND,
            subject_type=VOCABULARY_ALIGNMENT_REVIEW_SUBJECT_TYPE,
            subject_id=subject_id,
        )
        if item is None:
            raise
    return {
        "status": "proposed",
        "review_item_id": item["id"],
        "proposal_subject_id": subject_id,
        "payload": payload,
    }


def publish_vocabulary_alignment_proposal(
    align_store: dict[str, Any],
    graph_session: Any,
    persist_hub: Callable[[], None],
    payload: dict[str, Any],
) -> dict[str, Any]:
    from basis.domain.ontology.hub.alignment_graph import (
        apply_vocabulary_alignment_edge,
        remove_vocabulary_alignment_edge,
    )
    from basis.domain.ontology.hub.catalog import delete_alignment, upsert_alignment

    action = str(payload.get("action") or "")
    if action == "upsert":
        result = upsert_alignment(
            align_store,
            graph_session,
            source_uri=str(payload.get("source_uri") or ""),
            target_uri=str(payload.get("target_uri") or ""),
            relation=str(payload.get("relation") or ""),
            source_label=payload.get("source_label"),
            target_label=payload.get("target_label"),
            confidence=float(payload.get("confidence", 1.0)),
            provenance=payload.get("provenance"),
            source=payload.get("source"),
            reviewer=payload.get("reviewer"),
        )
        apply_vocabulary_alignment_edge(graph_session, result)
        persist_hub()
        return {"status": "published", "alignment": result}
    if action == "delete":
        alignment_id = str(payload.get("alignment_id") or "")
        if not alignment_id:
            raise AdminError(422, "validation_error", "alignment_id is required for delete proposal")
        result = delete_alignment(align_store, alignment_id)
        remove_vocabulary_alignment_edge(graph_session, alignment_id)
        persist_hub()
        return {"status": "published", **result}
    raise AdminError(422, "validation_error", f"Unsupported alignment proposal action: {action}")


def vocabulary_alignment_requires_review(knowledge: KnowledgeStore, workspace_id: str) -> bool:
    return bool(knowledge.get_governance_config(workspace_id).vocabulary_alignment_requires_review)
