"""Embedding index metadata — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def fetch_embedding_record(
    conn: Any, workspace_id: str, chunk_id: str, model_ref: str
) -> Any:
    return conn.execute(
        """
        SELECT content_sha256, model_ref, dimension, vector_key
        FROM embedding_records
        WHERE workspace_id = ? AND chunk_id = ? AND model_ref = ?
        """,
        (workspace_id, chunk_id, model_ref),
    ).fetchone()


def upsert_embedding_record(
    conn: Any,
    *,
    record_id: str,
    workspace_id: str,
    chunk_id: str,
    model_ref: str,
    dimension: int,
    content_sha256: str,
    vector_key: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO embedding_records (
            id, workspace_id, chunk_id, model_ref, dimension, content_sha256, vector_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chunk_id, model_ref) DO UPDATE SET
            dimension = excluded.dimension,
            content_sha256 = excluded.content_sha256,
            vector_key = excluded.vector_key,
            created_at = excluded.created_at
        """,
        (
            record_id,
            workspace_id,
            chunk_id,
            model_ref,
            dimension,
            content_sha256,
            vector_key,
            created_at,
        ),
    )


def delete_all_embedding_records(conn: Any, workspace_id: str) -> int:
    cur = conn.execute("DELETE FROM embedding_records WHERE workspace_id = ?", (workspace_id,))
    return int(cur.rowcount)
