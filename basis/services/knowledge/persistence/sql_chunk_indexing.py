"""Chunk rows for vector indexing — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def list_chunks_for_indexing_rows(
    conn: Any, workspace_id: str, chunk_ids: list[str] | None
) -> list[Any]:
    if chunk_ids:
        placeholders = ",".join("?" * len(chunk_ids))
        return conn.execute(
            f"""
            SELECT c.id AS chunk_id, c.version_id, c.text,
                   d.id AS document_id, d.title AS document_title
            FROM chunks c
            INNER JOIN document_versions dv ON dv.id = c.version_id
            INNER JOIN documents d ON d.id = dv.document_id
            WHERE c.workspace_id = ? AND c.id IN ({placeholders})
            """,
            (workspace_id, *chunk_ids),
        ).fetchall()
    return conn.execute(
        """
        SELECT c.id AS chunk_id, c.version_id, c.text,
               d.id AS document_id, d.title AS document_title
        FROM chunks c
        INNER JOIN document_versions dv ON dv.id = c.version_id
        INNER JOIN documents d ON d.id = dv.document_id
        WHERE c.workspace_id = ?
        """,
        (workspace_id,),
    ).fetchall()


def chunk_ids_matching_filters(
    conn: Any,
    workspace_id: str,
    *,
    document_id: str | None,
    entity_id: str | None,
    created_after: str | None,
    created_before: str | None,
) -> set[str]:
    clauses = ["c.workspace_id = ?"]
    params: list[Any] = [workspace_id]
    if document_id:
        clauses.append("d.id = ?")
        params.append(document_id)
    if created_after:
        clauses.append("d.created_at >= ?")
        params.append(created_after)
    if created_before:
        clauses.append("d.created_at <= ?")
        params.append(created_before)
    if entity_id:
        clauses.append(
            """
            EXISTS (
                SELECT 1 FROM statement_evidence se
                INNER JOIN statements s ON s.id = se.statement_id
                WHERE se.chunk_id = c.id AND se.workspace_id = c.workspace_id
                  AND s.invalidated_at IS NULL
                  AND (s.subject_id = ? OR s.object_entity_id = ?)
            )
            """
        )
        params.extend([entity_id, entity_id])
    sql = f"""
        SELECT DISTINCT c.id AS chunk_id
        FROM chunks c
        INNER JOIN document_versions dv ON dv.id = c.version_id
        INNER JOIN documents d ON d.id = dv.document_id
        WHERE {" AND ".join(clauses)}
    """
    rows = conn.execute(sql, tuple(params)).fetchall()
    return {row["chunk_id"] for row in rows}
