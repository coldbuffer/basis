"""Hard-delete a document — canonical DB SQL (+ blob cleanup via store)."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore

_STATEMENT_REVIEW_SUBJECT_TYPES = ("statement", "statement_remember")


def _in_clause(ids: list[str]) -> str:
    return ",".join("?" * len(ids))


def _delete_by_ids(
    conn: Any,
    table: str,
    workspace_id: str,
    column: str,
    ids: list[str],
) -> int:
    if not ids:
        return 0
    placeholders = _in_clause(ids)
    result = conn.execute(
        f"DELETE FROM {table} WHERE workspace_id = ? AND {column} IN ({placeholders})",
        (workspace_id, *ids),
    )
    return int(result.rowcount if result.rowcount >= 0 else 0)


def _entity_still_referenced(conn: Any, workspace_id: str, entity_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM statements
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (subject_id = ? OR object_entity_id = ?)
        LIMIT 1
        """,
        (workspace_id, entity_id, entity_id),
    ).fetchone()
    if row is not None:
        return True
    row = conn.execute(
        """
        SELECT 1 FROM typed_facts
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (subject_id = ? OR object_entity_id = ?)
        LIMIT 1
        """,
        (workspace_id, entity_id, entity_id),
    ).fetchone()
    if row is not None:
        return True
    row = conn.execute(
        """
        SELECT 1 FROM entity_merges
        WHERE workspace_id = ? AND reverted_at IS NULL
          AND (source_entity_id = ? OR target_entity_id = ?)
        LIMIT 1
        """,
        (workspace_id, entity_id, entity_id),
    ).fetchone()
    return row is not None



def execute_hard_delete_document(
    store: KnowledgeStore,
    workspace_id: str,
    document_id: str,
) -> dict[str, Any]:
    """Remove document rows, blobs, chunks, vectors (caller), and rebuild graph (caller)."""
    conn = store._conn
    doc = conn.execute(
                """
        SELECT id, external_key, title
        FROM documents
        WHERE id = ? AND workspace_id = ? AND deleted_at IS NULL
                """,
        (document_id, workspace_id),
    ).fetchone()
    if doc is None:
        raise AdminError(404, "not_found", "文档不存在")

    version_rows = conn.execute(
                """
        SELECT id, blob_key
        FROM document_versions
        WHERE workspace_id = ? AND document_id = ?
                """,
        (workspace_id, document_id),
    ).fetchall()
    version_ids = [row["id"] for row in version_rows]
    blob_keys = [row["blob_key"] for row in version_rows if row["blob_key"]]

    if version_ids:
        placeholders = _in_clause(version_ids)
        active = conn.execute(
            f"""
            SELECT id FROM jobs
            WHERE workspace_id = ? AND kind = 'ingest'
              AND subject_type = 'document_version'
              AND subject_id IN ({placeholders})
              AND status IN ('queued', 'running')
            LIMIT 1
            """,
            (workspace_id, *version_ids),
        ).fetchone()
        if active is not None:
            raise AdminError(409, "processing_active", "文档正在处理，请稍后再删除")

    chunk_ids: list[str] = []
    if version_ids:
        placeholders = _in_clause(version_ids)
        chunk_rows = conn.execute(
            f"""
            SELECT id FROM chunks
            WHERE workspace_id = ? AND version_id IN ({placeholders})
            """,
            (workspace_id, *version_ids),
        ).fetchall()
        chunk_ids = [row["id"] for row in chunk_rows]

    evidence_ids: list[str] = []
    statement_ids_from_chunks: list[str] = []
    if chunk_ids:
        placeholders = _in_clause(chunk_ids)
        evidence_rows = conn.execute(
            f"""
            SELECT id, statement_id FROM statement_evidence
            WHERE workspace_id = ? AND chunk_id IN ({placeholders})
            """,
            (workspace_id, *chunk_ids),
        ).fetchall()
        evidence_ids = [row["id"] for row in evidence_rows]
        statement_ids_from_chunks = list(
            {row["statement_id"] for row in evidence_rows}
        )

    if chunk_ids or evidence_ids:
        clauses = []
        params: list[Any] = []
        if chunk_ids:
            clauses.append(f"chunk_id IN ({_in_clause(chunk_ids)})")
            params.extend(chunk_ids)
        if evidence_ids:
            clauses.append(f"evidence_id IN ({_in_clause(evidence_ids)})")
            params.extend(evidence_ids)
        conn.execute(
            f"DELETE FROM chat_citations WHERE {' OR '.join(clauses)}",
            tuple(params),
        )

    _delete_by_ids(conn, "embedding_records", workspace_id, "chunk_id", chunk_ids)
    _delete_by_ids(conn, "time_mentions", workspace_id, "chunk_id", chunk_ids)
    if version_ids:
        _delete_by_ids(conn, "extraction_drops", workspace_id, "version_id", version_ids)
    _delete_by_ids(conn, "extraction_drops", workspace_id, "chunk_id", chunk_ids)

    _delete_by_ids(conn, "statement_evidence", workspace_id, "chunk_id", chunk_ids)

    removed_statement_ids: list[str] = []
    for statement_id in statement_ids_from_chunks:
        row = conn.execute(
            """
            SELECT 1 FROM statement_evidence
            WHERE workspace_id = ? AND statement_id = ?
            LIMIT 1
            """,
            (workspace_id, statement_id),
        ).fetchone()
        if row is None:
            removed_statement_ids.append(statement_id)

    entity_candidates: set[str] = set()
    if removed_statement_ids:
        placeholders = _in_clause(removed_statement_ids)
        stmt_rows = conn.execute(
            f"""
            SELECT id, subject_id, object_entity_id
            FROM statements
            WHERE workspace_id = ? AND id IN ({placeholders})
            """,
            (workspace_id, *removed_statement_ids),
        ).fetchall()
        for row in stmt_rows:
            entity_candidates.add(row["subject_id"])
            if row["object_entity_id"]:
                entity_candidates.add(row["object_entity_id"])

        conn.execute(
            f"""
            DELETE FROM fact_derivations
            WHERE premise_kind = 'statement'
              AND premise_id IN ({placeholders})
            """,
            tuple(removed_statement_ids),
        )
        _delete_by_ids(
            conn, "statement_qualifiers", workspace_id, "statement_id", removed_statement_ids
        )
        _delete_by_ids(
            conn, "time_mentions", workspace_id, "statement_id", removed_statement_ids
        )
        conn.execute(
            f"""
            DELETE FROM typed_facts
            WHERE workspace_id = ? AND from_statement_id IN ({placeholders})
            """,
            (workspace_id, *removed_statement_ids),
        )
        for subject_type in _STATEMENT_REVIEW_SUBJECT_TYPES:
            conn.execute(
                f"""
                DELETE FROM review_items
                WHERE workspace_id = ? AND subject_type = ?
                  AND subject_id IN ({placeholders})
                """,
                (workspace_id, subject_type, *removed_statement_ids),
            )
        conn.execute(
            f"DELETE FROM statements WHERE workspace_id = ? AND id IN ({placeholders})",
            (workspace_id, *removed_statement_ids),
        )

    if evidence_ids:
        placeholders = _in_clause(evidence_ids)
        conn.execute(
            f"""
            DELETE FROM entity_names
            WHERE workspace_id = ? AND evidence_id IN ({placeholders})
            """,
            (workspace_id, *evidence_ids),
        )

    removed_entity_ids: list[str] = []
    for entity_id in entity_candidates:
        if _entity_still_referenced(conn, workspace_id, entity_id):
            continue
        removed_entity_ids.append(entity_id)
    if removed_entity_ids:
        _delete_by_ids(conn, "entity_names", workspace_id, "entity_id", removed_entity_ids)
        _delete_by_ids(conn, "entities", workspace_id, "id", removed_entity_ids)

    _delete_by_ids(conn, "chunks", workspace_id, "id", chunk_ids)
    if version_ids:
        conn.execute(
            f"""
            DELETE FROM jobs
            WHERE workspace_id = ? AND subject_type = 'document_version'
              AND subject_id IN ({_in_clause(version_ids)})
            """,
            (workspace_id, *version_ids),
        )
        conn.execute(
            f"""
            DELETE FROM document_versions
            WHERE workspace_id = ? AND document_id = ?
            """,
            (workspace_id, document_id),
        )
    conn.execute(
        "DELETE FROM documents WHERE workspace_id = ? AND id = ?",
        (workspace_id, document_id),
    )
    conn.commit()

    for blob_key in blob_keys:
        try:
            store._blob_store.delete(workspace_id, blob_key)
        except OSError:
            pass

    doc_id = doc["external_key"] or document_id
    return {
        "document_id": document_id,
        "doc_id": doc_id,
        "title": doc["title"],
        "version_ids": version_ids,
        "chunk_ids": chunk_ids,
        "statements_removed": len(removed_statement_ids),
        "entities_removed": len(removed_entity_ids),
    }
