"""Chunk keyword search SQL — canonical DB (caller holds lock)."""

from __future__ import annotations

import sqlite3
from typing import Any


def chunk_hit_from_row(row: sqlite3.Row) -> dict[str, Any]:
    text = row["text"] or ""
    hit: dict[str, Any] = {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "document_title": row["document_title"] or "",
        "ordinal": row["ordinal"],
        "text": text,
        "snippet": text[:400],
    }
    if "keyword_score" in row.keys():
        hit["keyword_score"] = float(row["keyword_score"])
    return hit


def search_chunks_postgres(
    conn: Any, workspace_id: str, *, query: str, limit: int
) -> list[sqlite3.Row]:
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return conn.execute(
        """
        WITH ranked AS MATERIALIZED (
            SELECT id AS chunk_id, 1 - (text <-> ?) AS keyword_score
            FROM chunks
            WHERE workspace_id = ? AND text ILIKE ? ESCAPE '\\'
            ORDER BY text <-> ?, created_at DESC
            LIMIT ?
        )
        SELECT c.id AS chunk_id, c.ordinal, c.text,
               d.id AS document_id, d.title AS document_title,
               ranked.keyword_score
        FROM ranked
        INNER JOIN chunks c ON c.id = ranked.chunk_id
        INNER JOIN document_versions dv
            ON dv.id = c.version_id AND dv.workspace_id = c.workspace_id
        INNER JOIN documents d
            ON d.id = dv.document_id AND d.workspace_id = c.workspace_id
        ORDER BY ranked.keyword_score DESC, c.created_at DESC
        """,
        (query, workspace_id, pattern, query, limit),
    ).fetchall()


def search_chunks_fts(conn: Any, workspace_id: str, *, query: str, limit: int) -> list[Any]:
    escaped_query = query.replace('"', '""')
    match_query = f'"{escaped_query}"'
    return conn.execute(
        """
        WITH ranked AS MATERIALIZED (
            SELECT chunk_id, -rank AS keyword_score
            FROM chunks_fts
            WHERE chunks_fts MATCH ? AND chunks_fts.workspace_id = ?
            ORDER BY rank
            LIMIT ?
        )
        SELECT c.id AS chunk_id, c.ordinal, c.text,
               d.id AS document_id, d.title AS document_title,
               ranked.keyword_score
        FROM ranked
        INNER JOIN chunks c ON c.id = ranked.chunk_id
        INNER JOIN document_versions dv
            ON dv.id = c.version_id AND dv.workspace_id = c.workspace_id
        INNER JOIN documents d
            ON d.id = dv.document_id AND d.workspace_id = c.workspace_id
        ORDER BY ranked.keyword_score DESC, c.created_at DESC
        """,
        (match_query, workspace_id, limit),
    ).fetchall()


def search_chunks_like(conn: Any, workspace_id: str, *, query: str, limit: int) -> list[Any]:
    pattern = f"%{query.replace('%', '')}%"
    return conn.execute(
        """
        SELECT c.id AS chunk_id, c.ordinal, c.text, d.id AS document_id, d.title AS document_title
        FROM chunks c
        INNER JOIN document_versions dv ON dv.id = c.version_id AND dv.workspace_id = c.workspace_id
        INNER JOIN documents d ON d.id = dv.document_id AND d.workspace_id = c.workspace_id
        WHERE c.workspace_id = ? AND c.text LIKE ?
        ORDER BY c.created_at DESC
        LIMIT ?
        """,
        (workspace_id, pattern, limit),
    ).fetchall()


def fetch_chunks_by_ids(conn: Any, workspace_id: str, chunk_ids: list[str]) -> list[Any]:
    placeholders = ",".join("?" * len(chunk_ids))
    return conn.execute(
        f"""
        SELECT c.id AS chunk_id, c.ordinal, c.text, d.id AS document_id, d.title AS document_title
        FROM chunks c
        INNER JOIN document_versions dv ON dv.id = c.version_id AND dv.workspace_id = c.workspace_id
        INNER JOIN documents d ON d.id = dv.document_id AND d.workspace_id = c.workspace_id
        WHERE c.workspace_id = ? AND c.id IN ({placeholders})
        """,
        (workspace_id, *chunk_ids),
    ).fetchall()
