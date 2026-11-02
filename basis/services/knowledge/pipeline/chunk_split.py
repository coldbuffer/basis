"""TextSplitter wiring for document ingest (product-supported chunk methods)."""

from __future__ import annotations

from pathlib import Path

from basis.services.knowledge.pipeline.document import TextIngestOptions

# Exposed in the Sources processing dialog; must match semantica.split.methods._SPLIT_METHODS keys.
PRODUCT_CHUNK_METHODS: frozenset[str] = frozenset(
    {
        "recursive",
        "sentence",
        "paragraph",
        "structural",
        "entity_aware",
    }
)
DEFAULT_CHUNK_METHOD = "recursive"
_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})


def default_chunk_method(filename: str | None) -> str:
    """Markdown keeps headings, lists, and code fences, so it splits by structure."""
    suffix = Path(filename or "").suffix.lower()
    if suffix in _MARKDOWN_SUFFIXES:
        return "structural"
    return DEFAULT_CHUNK_METHOD


def normalize_chunk_method(value: str | None) -> str:
    method = (value or DEFAULT_CHUNK_METHOD).strip().lower()
    if method not in PRODUCT_CHUNK_METHODS:
        raise ValueError(f"unsupported chunk method: {method}")
    return method


def text_splitter(options: TextIngestOptions):
    """Build a Semantica TextSplitter from ingest options."""
    from semantica.split import TextSplitter

    method = normalize_chunk_method(options.chunk_method)
    extra: dict[str, object] = {}
    if method == "structural":
        extra["max_chunk_size"] = options.chunk_size
        extra["respect_headers"] = True
        extra["respect_sections"] = True
    if method == "entity_aware":
        extra["ner_method"] = options.ner_method
        ner_model = (options.ner_model or "").strip()
        if ner_model:
            extra["model"] = ner_model
    return TextSplitter(
        method=method,
        chunk_size=options.chunk_size,
        chunk_overlap=options.chunk_overlap,
        **extra,
    )
