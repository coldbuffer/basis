"""Vector index backend contract and the initial sqlite-vec implementation."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger(__name__)


class VectorIndexBackend(Protocol):
    name: str

    def manifest(self, workspace_id: str) -> dict[str, Any]: ...

    def upsert(
        self,
        workspace_id: str,
        vectors: np.ndarray,
        *,
        ids: list[str],
        metadata: list[dict[str, Any]],
        model_ref: str,
    ) -> None: ...

    def search(
        self,
        workspace_id: str,
        query_vector: np.ndarray,
        *,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    def delete(self, workspace_id: str, ids: list[str]) -> None: ...

    def reset(self, workspace_id: str) -> None: ...


class SQLiteVectorIndex:
    """One rebuildable sqlite-vec database per workspace."""

    name = "sqlite_vec"

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._lock = threading.Lock()
        self._stores: dict[str, Any] = {}

    def _workspace_dir(self, workspace_id: str) -> Path:
        path = self._data_dir / "search" / workspace_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _manifest_path(self, workspace_id: str) -> Path:
        return self._workspace_dir(workspace_id) / "manifest.json"

    def manifest(self, workspace_id: str) -> dict[str, Any]:
        path = self._manifest_path(workspace_id)
        if not path.is_file():
            # Read the name used by the pre-backend-abstraction implementation.
            legacy = self._workspace_dir(workspace_id) / "meta.json"
            path = legacy if legacy.is_file() else path
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_manifest(self, workspace_id: str, *, model_ref: str, dimension: int) -> None:
        self._manifest_path(workspace_id).write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "backend": self.name,
                    "model_ref": model_ref,
                    "dimension": dimension,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _store(self, workspace_id: str, dimension: int):
        from semantica.vector_store.sqlite_vec_store import SQLiteVecStore

        with self._lock:
            cached = self._stores.get(workspace_id)
            if cached is not None:
                if cached.dimension != dimension:
                    raise ValueError("vector dimension changed; reindex is required")
                return cached
            store = SQLiteVecStore(
                db_path=str(self._workspace_dir(workspace_id) / "vectors.db"),
                table_name="chunk_vectors",
                dimension=dimension,
                distance_metric="cosine",
                use_wal=True,
            )
            self._stores[workspace_id] = store
            return store

    def upsert(
        self,
        workspace_id: str,
        vectors: np.ndarray,
        *,
        ids: list[str],
        metadata: list[dict[str, Any]],
        model_ref: str,
    ) -> None:
        if not len(vectors):
            return
        dimension = int(vectors.shape[1])
        manifest = self.manifest(workspace_id)
        if manifest and (
            manifest.get("model_ref") != model_ref
            or int(manifest.get("dimension", 0)) != dimension
        ):
            raise ValueError("embedding model changed; reindex is required")
        self._store(workspace_id, dimension).add(vectors, metadata=metadata, ids=ids)
        self._write_manifest(workspace_id, model_ref=model_ref, dimension=dimension)

    def delete(self, workspace_id: str, ids: list[str]) -> None:
        if not ids:
            return
        manifest = self.manifest(workspace_id)
        dimension = int(manifest.get("dimension", 0))
        if not dimension:
            return
        self._store(workspace_id, dimension).delete(ids)

    def search(
        self,
        workspace_id: str,
        query_vector: np.ndarray,
        *,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        manifest = self.manifest(workspace_id)
        dimension = int(manifest.get("dimension", 0))
        if not dimension:
            return []
        return self._store(workspace_id, dimension).search(
            query_vector, top_k=limit, filter=filters
        )

    def reset(self, workspace_id: str) -> None:
        with self._lock:
            store = self._stores.pop(workspace_id, None)
        if store is not None:
            store.close()
        workspace_dir = self._workspace_dir(workspace_id)
        for name in ("vectors.db", "vectors.db-wal", "vectors.db-shm", "manifest.json", "meta.json"):
            path = workspace_dir / name
            if path.is_file():
                path.unlink()


class PgVectorIndex:
    """Shared PostgreSQL pgvector table partitioned by embedding dimension."""

    name = "pgvector"

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @staticmethod
    def _vector(vector: np.ndarray) -> str:
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def manifest(self, workspace_id: str) -> dict[str, Any]:
        with self._engine.connect() as conn:
            row = conn.exec_driver_sql(
                """
                SELECT backend, model_ref, dimension
                FROM vector_manifests WHERE workspace_id = %s
                """,
                (workspace_id,),
            ).mappings().first()
        return dict(row) if row else {}

    def _ensure_partition(self, conn: Any, dimension: int) -> None:
        partition = f"chunk_vectors_d{dimension}"
        index = f"{partition}_hnsw_cosine"
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (dimension,))
        conn.exec_driver_sql(
            f"""
            CREATE TABLE IF NOT EXISTS {partition}
            PARTITION OF chunk_vectors FOR VALUES IN ({dimension})
            """
        )
        try:
            with conn.begin_nested():
                conn.exec_driver_sql(
                    f"""
                    CREATE INDEX IF NOT EXISTS {index}
                    ON {partition}
                    USING hnsw ((embedding::vector({dimension})) vector_cosine_ops)
                    """
                )
        except ProgrammingError as exc:
            orig = getattr(exc, "orig", None)
            msg = str(orig or exc).lower()
            if "must be owner" in msg or getattr(orig, "sqlstate", None) == "42501":
                logger.warning(
                    "Skipping HNSW index on %s (insufficient privilege): %s",
                    partition,
                    orig or exc,
                )
            else:
                raise

    def upsert(
        self,
        workspace_id: str,
        vectors: np.ndarray,
        *,
        ids: list[str],
        metadata: list[dict[str, Any]],
        model_ref: str,
    ) -> None:
        if not len(vectors):
            return
        dimension = int(vectors.shape[1])
        current = self.manifest(workspace_id)
        if current and (
            current.get("model_ref") != model_ref
            or int(current.get("dimension", 0)) != dimension
        ):
            raise ValueError("embedding model changed; reindex is required")
        with self._engine.begin() as conn:
            self._ensure_partition(conn, dimension)
            conn.exec_driver_sql(
                """
                INSERT INTO chunk_vectors(
                    workspace_id, chunk_id, dimension, embedding, metadata, model_ref
                ) VALUES (%s, %s, %s, %s::vector, %s::jsonb, %s)
                ON CONFLICT (workspace_id, chunk_id, dimension) DO UPDATE SET
                    embedding = excluded.embedding,
                    metadata = excluded.metadata,
                    model_ref = excluded.model_ref
                """,
                [
                    (
                        workspace_id,
                        chunk_id,
                        dimension,
                        self._vector(vector),
                        json.dumps(meta),
                        model_ref,
                    )
                    for chunk_id, vector, meta in zip(ids, vectors, metadata)
                ],
            )
            conn.exec_driver_sql(
                """
                INSERT INTO vector_manifests(
                    workspace_id, backend, model_ref, dimension, updated_at
                ) VALUES (%s, 'pgvector', %s, %s, CURRENT_TIMESTAMP::text)
                ON CONFLICT (workspace_id) DO UPDATE SET
                    backend = excluded.backend,
                    model_ref = excluded.model_ref,
                    dimension = excluded.dimension,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, model_ref, dimension),
            )

    def delete(self, workspace_id: str, ids: list[str]) -> None:
        if not ids:
            return
        with self._engine.begin() as conn:
            for offset in range(0, len(ids), 500):
                batch = ids[offset : offset + 500]
                placeholders = ",".join("%s" for _ in batch)
                conn.exec_driver_sql(
                    f"""
                    DELETE FROM chunk_vectors
                    WHERE workspace_id = %s AND chunk_id IN ({placeholders})
                    """,
                    (workspace_id, *batch),
                )

    def search(
        self,
        workspace_id: str,
        query_vector: np.ndarray,
        *,
        limit: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        dimension = len(query_vector)
        clauses = ["workspace_id = %s", "dimension = %s"]
        where_params: list[Any] = [workspace_id, dimension]
        if filters:
            for key, value in filters.items():
                if key not in {"document_id", "version_id"}:
                    raise ValueError(f"unsupported pgvector filter: {key}")
                clauses.append(f"metadata ->> '{key}' = %s")
                where_params.append(value)
        query = self._vector(query_vector)
        params = [query, *where_params, query, limit]
        with self._engine.connect() as conn:
            rows = conn.exec_driver_sql(
                f"""
                SELECT chunk_id AS id,
                       1 - (embedding::vector({dimension}) <=> %s::vector({dimension})) AS score,
                       metadata
                FROM chunk_vectors
                WHERE {' AND '.join(clauses)}
                ORDER BY embedding::vector({dimension}) <=> %s::vector({dimension})
                LIMIT %s
                """,
                tuple(params),
            ).mappings().all()
        return [dict(row) for row in rows]

    def reset(self, workspace_id: str) -> None:
        with self._engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM chunk_vectors WHERE workspace_id = %s", (workspace_id,))
            conn.exec_driver_sql(
                "DELETE FROM vector_manifests WHERE workspace_id = %s", (workspace_id,)
            )
