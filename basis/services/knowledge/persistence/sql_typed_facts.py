"""Typed fact rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def list_typed_facts_for_subject(
    conn: Any,
    workspace_id: str,
    subject_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, subject_id, predicate_uri, object_entity_id, object_value,
               from_statement_id, mapping_id, confidence, recorded_at
        FROM typed_facts
        WHERE workspace_id = ? AND subject_id = ? AND invalidated_at IS NULL
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        (workspace_id, subject_id, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "predicate_uri": row["predicate_uri"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "from_statement_id": row["from_statement_id"],
            "mapping_id": row["mapping_id"],
            "confidence": row["confidence"],
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]


def invalidate_active_typed_facts_for_predicate(
    conn: Any,
    workspace_id: str,
    subject_id: str,
    predicate_uri: str,
    invalidated_at: str,
) -> int:
    cur = conn.execute(
        """
        UPDATE typed_facts
        SET invalidated_at = ?
        WHERE workspace_id = ? AND subject_id = ? AND predicate_uri = ?
          AND invalidated_at IS NULL
        """,
        (invalidated_at, workspace_id, subject_id, predicate_uri),
    )
    return int(cur.rowcount or 0)


def insert_direct_typed_fact(
    conn: Any,
    *,
    fact_id: str,
    workspace_id: str,
    subject_id: str,
    predicate_uri: str,
    object_entity_id: str | None,
    object_value: str | None,
    recorded_at: str,
    confidence: float | None = 1.0,
    import_provenance_json: str = '{"source":"assign_entity_type"}',
) -> None:
    conn.execute(
        """
        INSERT INTO typed_facts (
            id, workspace_id, subject_id, predicate_uri,
            object_entity_id, object_value, from_statement_id,
            mapping_id, import_provenance_json, confidence, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
        """,
        (
            fact_id,
            workspace_id,
            subject_id,
            predicate_uri,
            object_entity_id,
            object_value,
            import_provenance_json,
            confidence,
            recorded_at,
        ),
    )


def list_typed_facts_limited(conn: Any, workspace_id: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, subject_id, predicate_uri, object_entity_id, object_value,
               from_statement_id, mapping_id, confidence, recorded_at
        FROM typed_facts
        WHERE workspace_id = ? AND invalidated_at IS NULL
        ORDER BY recorded_at DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "subject_id": row["subject_id"],
            "predicate_uri": row["predicate_uri"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "from_statement_id": row["from_statement_id"],
            "mapping_id": row["mapping_id"],
            "confidence": row["confidence"],
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]
