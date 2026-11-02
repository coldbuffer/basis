"""Workspace search policy rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any

from basis.services.knowledge.search.search_config import SearchConfig


def fetch_search_config_row(conn: Any, workspace_id: str) -> Any:
    return conn.execute("SELECT * FROM search_configs WHERE workspace_id = ?", (workspace_id,)).fetchone()


def insert_default_search_config(
    conn: Any,
    workspace_id: str,
    *,
    chunk_backend: str,
    vector_backend: str,
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO search_configs (
            workspace_id, schema_version, chunk_backend, vector_backend,
            embedding_model_id, keyword_enabled, semantic_enabled,
            default_mode, auto_index, created_at, updated_at
        ) VALUES (?, 1, ?, ?, NULL, 1, 1, 'hybrid', 1, ?, ?)
        """,
        (workspace_id, chunk_backend, vector_backend, created_at, updated_at),
    )


def search_config_from_row(row: Any) -> SearchConfig:
    return SearchConfig(
        workspace_id=row["workspace_id"],
        schema_version=int(row["schema_version"]),
        chunk_backend=row["chunk_backend"],
        vector_backend=row["vector_backend"],
        embedding_model_id=row["embedding_model_id"],
        keyword_enabled=bool(row["keyword_enabled"]),
        semantic_enabled=bool(row["semantic_enabled"]),
        default_mode=row["default_mode"],
        auto_index=bool(row["auto_index"]),
    )


def upsert_search_config(conn: Any, config: SearchConfig, *, now: str) -> None:
    conn.execute(
        """
        INSERT INTO search_configs (
            workspace_id, schema_version, chunk_backend, vector_backend,
            embedding_model_id, keyword_enabled, semantic_enabled,
            default_mode, auto_index, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id) DO UPDATE SET
            schema_version = excluded.schema_version,
            chunk_backend = excluded.chunk_backend,
            vector_backend = excluded.vector_backend,
            embedding_model_id = excluded.embedding_model_id,
            keyword_enabled = excluded.keyword_enabled,
            semantic_enabled = excluded.semantic_enabled,
            default_mode = excluded.default_mode,
            auto_index = excluded.auto_index,
            updated_at = excluded.updated_at
        """,
        (
            config.workspace_id,
            config.schema_version,
            config.chunk_backend,
            config.vector_backend,
            config.embedding_model_id,
            int(config.keyword_enabled),
            int(config.semantic_enabled),
            config.default_mode,
            int(config.auto_index),
            now,
            now,
        ),
    )
