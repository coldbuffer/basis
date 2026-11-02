"""Chunk retrieval: config, embeddings, vector indexes, hybrid search service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.services.knowledge.search.search_config import SearchConfig, SearchMode, validate_search_config

if TYPE_CHECKING:
    from basis.services.knowledge.search.chunk_search import ChunkSearchService

__all__ = [
    "ChunkSearchService",
    "SearchConfig",
    "SearchMode",
    "validate_search_config",
]


def __getattr__(name: str):
    if name == "ChunkSearchService":
        from basis.services.knowledge.search.chunk_search import ChunkSearchService

        return ChunkSearchService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
