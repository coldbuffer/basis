"""Project vocabulary alignments (L1) into the workspace graph session."""

from __future__ import annotations

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
