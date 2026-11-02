"""Versioned per-workspace retrieval configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from basis.services.errors import AdminError

SearchMode = Literal["keyword", "semantic", "hybrid"]

SUPPORTED_CHUNK_BACKENDS = ("sqlite_ledger", "postgres_ledger")
SUPPORTED_VECTOR_BACKENDS = ("sqlite_vec", "pgvector")
SUPPORTED_SEARCH_MODES = ("keyword", "semantic", "hybrid")


@dataclass(frozen=True)
class SearchConfig:
    workspace_id: str
    schema_version: int = 1
    chunk_backend: str = "sqlite_ledger"
    vector_backend: str = "sqlite_vec"
    embedding_model_id: str | None = None
    keyword_enabled: bool = True
    semantic_enabled: bool = True
    default_mode: SearchMode = "hybrid"
    auto_index: bool = True

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_search_config(config: SearchConfig) -> None:
    if config.chunk_backend not in SUPPORTED_CHUNK_BACKENDS:
        raise AdminError(422, "unsupported_chunk_backend", "不支持的 chunk 存储")
    if config.vector_backend not in SUPPORTED_VECTOR_BACKENDS:
        raise AdminError(422, "unsupported_vector_backend", "不支持的向量存储")
    if config.default_mode not in SUPPORTED_SEARCH_MODES:
        raise AdminError(422, "bad_search_mode", "无效的默认搜索模式")
    if config.default_mode == "keyword" and not config.keyword_enabled:
        raise AdminError(422, "search_mode_disabled", "默认全文搜索未启用")
    if config.default_mode == "semantic" and not config.semantic_enabled:
        raise AdminError(422, "search_mode_disabled", "默认语义搜索未启用")
    if config.default_mode == "hybrid" and not (
        config.keyword_enabled and config.semantic_enabled
    ):
        raise AdminError(422, "search_mode_disabled", "混合搜索需要启用全文与语义搜索")
