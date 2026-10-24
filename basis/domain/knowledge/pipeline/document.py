"""Document ingest via semantica SDK (normalize → extract → GraphBuilder → ContextGraph)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.pipeline.extract_timeout import run_sync_with_timeout
from basis.domain.knowledge.pipeline.kg_apply import apply_kg_to_session


@dataclass(frozen=True)
class TextIngestOptions:
    """Controls how raw text is processed before landing on the workspace graph."""

    extract: bool = True
    chunk: bool = False
    chunk_method: str = "recursive"
    chunk_size: int = 1800
    chunk_overlap: int = 250
    ner_method: str = "llm"
    relation_method: str = "llm"
    ner_model: str | None = None  # unused (LLM-only product surface)
    llm_model: str | None = None  # Chat model id for LLM extract (per job)
    llm_endpoint_id: str | None = None  # Catalog entry id for provider credentials
    extract_relations: bool = True
    extract_triplets: bool = False
    merge_entities: bool = True


def _normalize_text(text: str) -> str:
    from semantica.normalize import clean_text, normalize_text

    cleaned = clean_text(text, method="default")
    if not cleaned:
        return ""
    return normalize_text(cleaned, method="default")


def build_kg_from_text(
    doc_id: str,
    text: str,
    options: TextIngestOptions,
    *,
    chat_llm: dict[str, str | None] | None = None,
    extract_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Run semantica GraphBuilder on plain text segments.

    ``doc_id`` is Basis's graph/ledger document key only — it must not be passed as a
    GraphBuilder source ``id``, or extraction is skipped (prebuilt-entity shortcut).
    """
    from semantica.kg import GraphBuilder

    from basis.domain.knowledge.pipeline.extract_kwargs import semantica_build_kwargs

    builder = GraphBuilder(merge_entities=options.merge_entities, resolve_conflicts=False)
    segments: list[str] = [text]

    if options.chunk and len(text) > options.chunk_size:
        from basis.domain.knowledge.pipeline.chunk_split import text_splitter

        splitter = text_splitter(options)
        chunks = splitter.split(text)
        segments = [
            chunk.text
            for chunk in chunks
            if getattr(chunk, "text", "").strip()
        ] or [text]

    build_kwargs = semantica_build_kwargs(options, chat_llm)

    merged: dict[str, Any] = {"entities": [], "relationships": [], "metadata": {}}
    timeout = float(extract_timeout_seconds or 0)
    for segment in segments:
        def _build_segment() -> dict[str, Any]:
            return builder.build(segment, **build_kwargs)

        kg_part = (
            run_sync_with_timeout(_build_segment, timeout)
            if timeout > 0
            else _build_segment()
        )
        merged["entities"].extend(kg_part.get("entities") or [])
        merged["relationships"].extend(kg_part.get("relationships") or [])
    return merged


def ingest_text(
    session: GraphSession,
    doc_id: str,
    text: str,
    *,
    options: TextIngestOptions | None = None,
) -> dict[str, Any]:
    """Record a document and optionally run semantica extraction into the workspace graph."""
    options = options or TextIngestOptions()
    session.add_node(doc_id, "document", content=text, text=text)

    normalized = _normalize_text(text)
    result: dict[str, Any] = {
        **session.stats(),
        "doc_id": doc_id,
        "entities_added": 0,
        "relationships_added": 0,
        "extracted": False,
    }

    if not options.extract or not normalized.strip():
        return result

    kg = build_kg_from_text(doc_id, normalized, options)
    applied = apply_kg_to_session(session, kg, doc_id=doc_id)
    result.update(applied)
    result["extracted"] = True
    result.update(session.stats())
    return result
