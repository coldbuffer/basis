"""Ontology mapping rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import sqlite3
from typing import Any

_MAPPING_SELECT = """
    SELECT id, signature, target_uri, target_kind, direction, status,
           actor_id, why, created_at, invalidated_at, supersedes_id
"""


def mapping_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "signature": row["signature"],
        "target_uri": row["target_uri"],
        "target_kind": row["target_kind"],
        "direction": row["direction"],
        "status": row["status"],
        "actor_id": row["actor_id"],
        "why": row["why"],
        "created_at": row["created_at"],
        "invalidated_at": row["invalidated_at"],
        "supersedes_id": row["supersedes_id"],
    }


def list_mapping_rows(
    conn: Any,
    workspace_id: str,
    *,
    include_invalidated: bool,
    status: str | None,
    limit: int,
) -> list[Any]:
    clauses = ["workspace_id = ?"]
    params: list[Any] = [workspace_id]
    if not include_invalidated:
        clauses.append("invalidated_at IS NULL")
    if status:
        clauses.append("status = ?")
        params.append(status)
    params.append(limit)
    sql = f"""
        {_MAPPING_SELECT}
        FROM mappings
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at DESC
        LIMIT ?
    """
    return conn.execute(sql, tuple(params)).fetchall()


def insert_mapping(
    conn: Any,
    *,
    mapping_id: str,
    workspace_id: str,
    signature: str,
    target_uri: str | None,
    target_kind: str,
    direction: str,
    status: str,
    actor_id: str,
    why: str | None,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO mappings (
            id, workspace_id, signature, target_uri, target_kind, direction,
            status, actor_id, why, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mapping_id,
            workspace_id,
            signature,
            target_uri,
            target_kind,
            direction,
            status,
            actor_id,
            why,
            created_at,
        ),
    )


def fetch_mapping(conn: Any, workspace_id: str, mapping_id: str) -> Any:
    return conn.execute(
        f"""
        {_MAPPING_SELECT}
        FROM mappings
        WHERE workspace_id = ? AND id = ?
        """,
        (workspace_id, mapping_id),
    ).fetchone()


def fetch_mapping_status_row(conn: Any, workspace_id: str, mapping_id: str) -> Any:
    return conn.execute(
        "SELECT status, invalidated_at FROM mappings WHERE workspace_id = ? AND id = ?",
        (workspace_id, mapping_id),
    ).fetchone()


def update_mapping_status_row(
    conn: Any,
    workspace_id: str,
    mapping_id: str,
    *,
    status: str,
    why: str | None,
    actor_id: str,
) -> None:
    conn.execute(
        """
        UPDATE mappings
        SET status = ?, why = COALESCE(?, why), actor_id = ?
        WHERE workspace_id = ? AND id = ?
        """,
        (status, why, actor_id, workspace_id, mapping_id),
    )


def invalidate_mapping_row(
    conn: Any, workspace_id: str, mapping_id: str, invalidated_at: str
) -> None:
    conn.execute(
        """
        UPDATE mappings SET invalidated_at = ?
        WHERE workspace_id = ? AND id = ?
        """,
        (invalidated_at, workspace_id, mapping_id),
    )


def statements_for_entity_type_materialization(
    conn: Any,
    workspace_id: str,
    type_surface_phrases: list[str],
) -> list[Any]:
    if not type_surface_phrases:
        return []
    placeholders = ",".join("?" for _ in type_surface_phrases)
    sql = f"""
        SELECT s.id, s.subject_id, s.object_entity_id, s.object_value, s.confidence,
               e.canonical_label AS object_entity_label
        FROM statements s
        LEFT JOIN entities e
          ON e.id = s.object_entity_id AND e.workspace_id = s.workspace_id
        WHERE s.workspace_id = ?
          AND s.invalidated_at IS NULL
          AND s.status IN ('pending', 'confirmed')
          AND s.surface_phrase IN ({placeholders})
    """
    params: list[Any] = [workspace_id, *type_surface_phrases]
    return conn.execute(sql, tuple(params)).fetchall()


def list_distinct_surface_phrases(conn: Any, workspace_id: str, limit: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT surface_phrase
        FROM statements
        WHERE workspace_id = ?
          AND invalidated_at IS NULL
          AND TRIM(surface_phrase) != ''
        ORDER BY surface_phrase
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    return [row["surface_phrase"] for row in rows]


def statements_for_mapping_materialization(
    conn: Any, workspace_id: str, signature: str
) -> list[Any]:
    return conn.execute(
        """
        SELECT id, subject_id, object_entity_id, object_value, confidence
        FROM statements
        WHERE workspace_id = ?
          AND invalidated_at IS NULL
          AND surface_phrase = ?
          AND status IN ('pending', 'confirmed')
        """,
        (workspace_id, signature),
    ).fetchall()


def typed_fact_exists_for_statement_mapping(
    conn: Any, workspace_id: str, statement_id: str, mapping_id: str
) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM typed_facts
        WHERE workspace_id = ? AND from_statement_id = ? AND mapping_id = ?
          AND invalidated_at IS NULL
        LIMIT 1
        """,
        (workspace_id, statement_id, mapping_id),
    ).fetchone()
    return row is not None


def insert_typed_fact_from_statement(
    conn: Any,
    *,
    fact_id: str,
    workspace_id: str,
    subject_id: str,
    predicate_uri: str,
    object_entity_id: str | None,
    object_value: str | None,
    from_statement_id: str,
    mapping_id: str,
    confidence: float | None,
    recorded_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO typed_facts (
            id, workspace_id, subject_id, predicate_uri,
            object_entity_id, object_value, from_statement_id,
            mapping_id, confidence, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            workspace_id,
            subject_id,
            predicate_uri,
            object_entity_id,
            object_value,
            from_statement_id,
            mapping_id,
            confidence,
            recorded_at,
        ),
    )
