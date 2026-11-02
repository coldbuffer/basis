"""Ledger rows read for graph projection — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def list_ready_documents_for_projection(
    conn: Any,
    workspace_id: str,
    *,
    include_version_ids: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    extra = tuple(v for v in (include_version_ids or ()) if v)
    if extra:
        placeholders = ", ".join("?" for _ in extra)
        status_clause = f"(dv.status = 'ready' OR dv.id IN ({placeholders}))"
        params: tuple[Any, ...] = (workspace_id, *extra)
    else:
        status_clause = "dv.status = 'ready'"
        params = (workspace_id,)
    rows = conn.execute(
        f"""
        SELECT d.id AS document_id, d.external_key, dv.id AS version_id,
               dv.created_at AS version_created_at
        FROM documents d
        INNER JOIN document_versions dv ON dv.id = d.current_version_id
        WHERE d.workspace_id = ? AND d.deleted_at IS NULL AND {status_clause}
        ORDER BY d.created_at ASC
        """,
        params,
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        version_id = row["version_id"]
        chunks = conn.execute(
            """
            SELECT text FROM chunks
            WHERE workspace_id = ? AND version_id = ?
            ORDER BY ordinal
            """,
            (workspace_id, version_id),
        ).fetchall()
        text = "\n\n".join(c["text"] or "" for c in chunks)
        graph_doc_id = row["external_key"] or row["document_id"]
        items.append(
            {
                "document_id": row["document_id"],
                "version_id": version_id,
                "graph_doc_id": graph_doc_id,
                "text": text,
                "version_created_at": row["version_created_at"],
            }
        )
    return items


def list_entities_for_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, canonical_label, description, entity_kind, created_at
        FROM entities
        WHERE workspace_id = ? AND invalidated_at IS NULL
        ORDER BY created_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_entities_for_temporal_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, canonical_label, description, entity_kind, created_at, invalidated_at
        FROM entities
        WHERE workspace_id = ?
        ORDER BY created_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _statement_projection_items(rows: list[Any], *, temporal: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        graph_doc_id = row["external_key"] or row["ledger_document_id"]
        item: dict[str, Any] = {
            "statement_id": row["statement_id"],
            "subject_id": row["subject_id"],
            "surface_phrase": row["surface_phrase"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "confidence": row["confidence"],
            "status": row["status"],
            "evidence_id": row["evidence_id"],
            "chunk_id": row["chunk_id"],
            "graph_doc_id": graph_doc_id,
            "recorded_at": row["recorded_at"],
        }
        if temporal:
            item["invalidated_at"] = row["invalidated_at"]
        items.append(item)
    return items


_STATEMENT_JOIN = """
    FROM statements s
    LEFT JOIN statement_evidence e ON e.statement_id = s.id AND e.workspace_id = s.workspace_id
    LEFT JOIN chunks c ON c.id = e.chunk_id
    LEFT JOIN document_versions dv ON dv.id = c.version_id
    LEFT JOIN documents d ON d.id = dv.document_id
"""


def list_statements_for_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT
            s.id AS statement_id,
            s.subject_id,
            s.surface_phrase,
            s.object_entity_id,
            s.object_value,
            s.confidence,
            s.status,
            s.recorded_at,
            e.id AS evidence_id,
            e.chunk_id,
            d.external_key,
            d.id AS ledger_document_id
        {_STATEMENT_JOIN}
        WHERE s.workspace_id = ?
          AND s.invalidated_at IS NULL
          AND s.status IN ('pending', 'confirmed')
        ORDER BY s.recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return _statement_projection_items(rows, temporal=False)


def list_statements_for_temporal_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        SELECT
            s.id AS statement_id,
            s.subject_id,
            s.surface_phrase,
            s.object_entity_id,
            s.object_value,
            s.confidence,
            s.status,
            s.recorded_at,
            s.invalidated_at,
            e.id AS evidence_id,
            e.chunk_id,
            d.external_key,
            d.id AS ledger_document_id
        {_STATEMENT_JOIN}
        WHERE s.workspace_id = ?
          AND s.status IN ('pending', 'confirmed', 'invalidated', 'superseded')
        ORDER BY s.recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return _statement_projection_items(rows, temporal=True)


def list_typed_facts_for_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, subject_id, predicate_uri, object_entity_id, object_value,
               mapping_id, confidence, recorded_at
        FROM typed_facts
        WHERE workspace_id = ? AND invalidated_at IS NULL
        ORDER BY recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "predicate_uri": row["predicate_uri"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "mapping_id": row["mapping_id"],
            "confidence": row["confidence"],
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]


def list_typed_facts_for_temporal_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, subject_id, predicate_uri, object_entity_id, object_value,
               mapping_id, confidence, recorded_at, invalidated_at
        FROM typed_facts
        WHERE workspace_id = ?
        ORDER BY recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "predicate_uri": row["predicate_uri"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "mapping_id": row["mapping_id"],
            "confidence": row["confidence"],
            "recorded_at": row["recorded_at"],
            "invalidated_at": row["invalidated_at"],
        }
        for row in rows
    ]


def list_derived_facts_for_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, subject_id, predicate_uri, object_entity_id, object_value, rule_id,
               recorded_at
        FROM derived_facts
        WHERE workspace_id = ? AND invalidated_at IS NULL
        ORDER BY recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "predicate_uri": row["predicate_uri"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "rule_id": row["rule_id"],
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]


def list_derived_facts_for_temporal_projection(conn: Any, workspace_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, subject_id, predicate_uri, object_entity_id, object_value, rule_id,
               recorded_at, invalidated_at
        FROM derived_facts
        WHERE workspace_id = ?
        ORDER BY recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "predicate_uri": row["predicate_uri"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "rule_id": row["rule_id"],
            "recorded_at": row["recorded_at"],
            "invalidated_at": row["invalidated_at"],
        }
        for row in rows
    ]
