"""Workspace search config, keyword search, and embedding records — KnowledgeStore API."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.knowledge.persistence import sql_chunk_indexing as idx_persist
from basis.services.knowledge.persistence import sql_chunk_keyword_search as kw_persist
from basis.services.knowledge.persistence import sql_embedding_records as emb_persist
from basis.services.knowledge.persistence import sql_search_config as sc_persist
from basis.services.knowledge.search.search_config import SearchConfig, validate_search_config

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SearchAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def get_search_config(self, workspace_id: str) -> SearchConfig:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            conn = self._store._conn
            row = sc_persist.fetch_search_config_row(conn, workspace_id)
            if row is None:
                now = _now()
                chunk_backend = (
                    "postgres_ledger"
                    if self._store._db.backend == "postgres"
                    else "sqlite_ledger"
                )
                vector_backend = (
                    "pgvector" if self._store._db.backend == "postgres" else "sqlite_vec"
                )
                sc_persist.insert_default_search_config(
                    conn,
                    workspace_id,
                    chunk_backend=chunk_backend,
                    vector_backend=vector_backend,
                    created_at=now,
                    updated_at=now,
                )
                conn.commit()
                return SearchConfig(
                    workspace_id=workspace_id,
                    chunk_backend=chunk_backend,
                    vector_backend=vector_backend,
                )
        return sc_persist.search_config_from_row(row)

    def update_search_config(
        self,
        workspace_id: str,
        *,
        embedding_model_id: str | None,
        keyword_enabled: bool,
        semantic_enabled: bool,
        default_mode: str,
        auto_index: bool,
        chunk_backend: str = "sqlite_ledger",
        vector_backend: str = "sqlite_vec",
    ) -> SearchConfig:
        config = SearchConfig(
            workspace_id=workspace_id,
            chunk_backend=chunk_backend,
            vector_backend=vector_backend,
            embedding_model_id=embedding_model_id or None,
            keyword_enabled=keyword_enabled,
            semantic_enabled=semantic_enabled,
            default_mode=default_mode,  # type: ignore[arg-type]
            auto_index=auto_index,
        )
        validate_search_config(config)
        expected_chunk_backend = (
            "postgres_ledger" if self._store._db.backend == "postgres" else "sqlite_ledger"
        )
        if config.chunk_backend != expected_chunk_backend:
            raise AdminError(
                422,
                "chunk_backend_mismatch",
                "Chunk 存储必须与当前部署的 canonical 数据库一致",
            )
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            now = _now()
            sc_persist.upsert_search_config(self._store._conn, config, now=now)
            self._store._conn.commit()
        return config

    def search_chunks_keyword(
        self, workspace_id: str, *, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        limit = min(max(1, limit), 50)
        if self._store._db.backend == "postgres":
            return self._search_postgres(workspace_id, query=query, limit=limit)
        if len(query) >= 3:
            try:
                return self._search_fts(workspace_id, query=query, limit=limit)
            except sqlite3.OperationalError:
                pass
        return self._search_like(workspace_id, query=query, limit=limit)

    def _search_postgres(self, workspace_id: str, *, query: str, limit: int) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = kw_persist.search_chunks_postgres(
                self._store._conn, workspace_id, query=query, limit=limit
            )
        return [kw_persist.chunk_hit_from_row(row) for row in rows]

    def _search_fts(self, workspace_id: str, *, query: str, limit: int) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = kw_persist.search_chunks_fts(
                self._store._conn, workspace_id, query=query, limit=limit
            )
        return [kw_persist.chunk_hit_from_row(row) for row in rows]

    def _search_like(self, workspace_id: str, *, query: str, limit: int) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = kw_persist.search_chunks_like(
                self._store._conn, workspace_id, query=query, limit=limit
            )
        return [kw_persist.chunk_hit_from_row(row) for row in rows]

    def search_chunks(self, workspace_id: str, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.search_chunks_keyword(workspace_id, query=query, limit=limit)

    def get_chunks_by_ids(self, workspace_id: str, chunk_ids: list[str]) -> list[dict[str, Any]]:
        if not chunk_ids:
            return []
        with self._store._lock:
            rows = kw_persist.fetch_chunks_by_ids(self._store._conn, workspace_id, chunk_ids)
        return [kw_persist.chunk_hit_from_row(row) for row in rows]

    def list_chunks_for_indexing(
        self, workspace_id: str, chunk_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = idx_persist.list_chunks_for_indexing_rows(
                self._store._conn, workspace_id, chunk_ids
            )
        return [
            {
                "chunk_id": row["chunk_id"],
                "version_id": row["version_id"],
                "document_id": row["document_id"],
                "document_title": row["document_title"] or "",
                "text": row["text"] or "",
            }
            for row in rows
        ]

    def chunk_ids_matching_filters(
        self,
        workspace_id: str,
        *,
        document_id: str | None = None,
        entity_id: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> set[str]:
        with self._store._lock:
            return idx_persist.chunk_ids_matching_filters(
                self._store._conn,
                workspace_id,
                document_id=document_id,
                entity_id=entity_id,
                created_after=created_after,
                created_before=created_before,
            )

    def get_embedding_record(
        self, workspace_id: str, chunk_id: str, model_ref: str
    ) -> dict[str, Any] | None:
        with self._store._lock:
            row = emb_persist.fetch_embedding_record(
                self._store._conn, workspace_id, chunk_id, model_ref
            )
        if row is None:
            return None
        return dict(row)

    def upsert_embedding_record(
        self,
        workspace_id: str,
        *,
        chunk_id: str,
        model_ref: str,
        dimension: int,
        content_sha256: str,
        vector_key: str,
    ) -> None:
        now = _now()
        record_id = str(uuid.uuid4())
        with self._store._lock:
            emb_persist.upsert_embedding_record(
                self._store._conn,
                record_id=record_id,
                workspace_id=workspace_id,
                chunk_id=chunk_id,
                model_ref=model_ref,
                dimension=dimension,
                content_sha256=content_sha256,
                vector_key=vector_key,
                created_at=now,
            )
            self._store._conn.commit()

    def delete_all_embedding_records(self, workspace_id: str) -> int:
        with self._store._lock:
            n = emb_persist.delete_all_embedding_records(self._store._conn, workspace_id)
            self._store._conn.commit()
            return n
