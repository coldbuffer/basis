"""Vocabulary alignment graph edges and review workflow."""

from __future__ import annotations


# ── alignment_graph.py ──
"""Project vocabulary alignments (L1) into the workspace graph session."""


from typing import Any

from typing import Protocol

_PROJECTION_LAYER = "vocabulary_alignment"


class _GraphSessionLike(Protocol):
    graph: Any

    def add_node(self, node_id: str, node_type: str, content: str | None = None, **properties: Any) -> bool: ...

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str = "related_to",
        **properties: Any,
    ) -> bool: ...


def _edge_metadata(edge: Any) -> dict[str, Any]:
    meta = getattr(edge, "metadata", None)
    return dict(meta) if isinstance(meta, dict) else {}


def purge_vocabulary_alignment_edges(session: _GraphSessionLike) -> int:
    """Remove all vocabulary-alignment projection edges. Returns count purged."""
    graph = session.graph
    removed = 0
    for edge in list(graph.edges):
        meta = _edge_metadata(edge)
        if meta.get("projection_layer") != _PROJECTION_LAYER:
            continue
        edge_id = getattr(edge, "edge_id", None)
        if edge_id and graph.purge_edge(edge_id):
            removed += 1
    return removed


def _ensure_ontology_node(session: _GraphSessionLike, uri: str, label: str | None) -> None:
    if session.graph.find_node(uri) is not None:
        return
    session.add_node(
        uri,
        "ontology_entity",
        content=label or uri,
        projection_layer=_PROJECTION_LAYER,
    )


def apply_vocabulary_alignment_edge(session: _GraphSessionLike, alignment: dict[str, Any]) -> None:
    """Upsert one alignment as a typed edge between ontology entity nodes."""
    source = str(alignment.get("source_uri") or "").strip()
    target = str(alignment.get("target_uri") or "").strip()
    relation = str(alignment.get("relation") or "").strip()
    alignment_id = str(alignment.get("id") or "").strip()
    if not source or not target or not relation or not alignment_id:
        return

    remove_vocabulary_alignment_edge(session, alignment_id)

    _ensure_ontology_node(session, source, alignment.get("source_label"))
    _ensure_ontology_node(session, target, alignment.get("target_label"))

    props: dict[str, Any] = {
        "projection_layer": _PROJECTION_LAYER,
        "vocabulary_alignment_id": alignment_id,
        "alignment_relation": relation,
        "predicate_uri": alignment.get("predicate_uri"),
        "confidence": alignment.get("confidence"),
    }
    edge_type = f"{_PROJECTION_LAYER}:{alignment_id}"
    added = session.add_edge(
        source,
        target,
        edge_type,
        **{k: v for k, v in props.items() if v is not None},
    )
    if not added:
        import uuid

        fallback_type = f"{edge_type}:{uuid.uuid4().hex[:8]}"
        session.add_edge(
            source,
            target,
            fallback_type,
            **{k: v for k, v in props.items() if v is not None},
        )


def remove_vocabulary_alignment_edge(session: _GraphSessionLike, alignment_id: str) -> bool:
    graph = session.graph
    for edge in list(graph.edges):
        meta = _edge_metadata(edge)
        if meta.get("projection_layer") != _PROJECTION_LAYER:
            continue
        if meta.get("vocabulary_alignment_id") != alignment_id:
            continue
        edge_id = getattr(edge, "edge_id", None)
        if edge_id:
            return bool(graph.purge_edge(edge_id))
    return False


def reapply_vocabulary_alignments(session: _GraphSessionLike, align_store: dict[str, Any]) -> int:
    """Replace all vocabulary-alignment edges from the hub store."""
    purge_vocabulary_alignment_edges(session)
    applied = 0
    for item in align_store.values():
        if isinstance(item, dict):
            apply_vocabulary_alignment_edge(session, item)
            applied += 1
    return applied

# ── alignment_review.py ──
"""Review-gated vocabulary alignment publish (L1 proposal → approve)."""


import hashlib
import json
from typing import Any, Callable

from basis.services.errors import AdminError
from basis.services.knowledge.store import KnowledgeStore

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
    from basis.services.ontology.hub.catalog import delete_alignment, upsert_alignment

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
