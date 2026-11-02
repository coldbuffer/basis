"""Delete one ledger entity — canonical DB SQL."""

from __future__ import annotations

from typing import Any

from basis.services.errors import AdminError
from basis.services.knowledge.persistence.sql_connector_sync import purge_entity_connector_sync_data

_STATEMENT_REVIEW_SUBJECT_TYPES = ("statement", "statement_remember")
_PREVIEW_LIMIT = 500


def _in_clause(ids: list[str]) -> str:
    return ",".join("?" * len(ids))


def _load_entity(conn: Any, workspace_id: str, entity_id: str) -> Any:
    row = conn.execute(
        """
        SELECT id, canonical_label
        FROM entities
        WHERE workspace_id = ? AND id = ?
        """,
        (workspace_id, entity_id),
    ).fetchone()
    if row is None:
        raise AdminError(404, "not_found", "实体不存在")
    return row


def _statement_rows(conn: Any, workspace_id: str, entity_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT
            s.id,
            s.subject_id,
            subj.canonical_label AS subject_label,
            s.surface_phrase,
            s.object_entity_id,
            obj.canonical_label AS object_label,
            s.object_value,
            s.status,
            (
                SELECT e.quote
                FROM statement_evidence e
                WHERE e.statement_id = s.id AND e.workspace_id = ?
                ORDER BY e.created_at
                LIMIT 1
            ) AS evidence_quote
        FROM statements s
        INNER JOIN entities subj ON subj.id = s.subject_id
        LEFT JOIN entities obj ON obj.id = s.object_entity_id
        WHERE s.workspace_id = ?
          AND (s.subject_id = ? OR s.object_entity_id = ?)
        ORDER BY s.recorded_at DESC
        """,
        (workspace_id, workspace_id, entity_id, entity_id),
    ).fetchall()


def _statement_payload(row: Any, entity_id: str) -> dict[str, Any]:
    subject_id = row["subject_id"]
    object_entity_id = row["object_entity_id"]
    if subject_id == entity_id and object_entity_id == entity_id:
        role = "both"
    elif subject_id == entity_id:
        role = "subject"
    else:
        role = "object"
    return {
        "statement_id": row["id"],
        "role": role,
        "subject_id": subject_id,
        "subject_label": row["subject_label"],
        "surface_phrase": row["surface_phrase"],
        "object_entity_id": object_entity_id,
        "object_label": row["object_label"],
        "object_value": row["object_value"],
        "status": row["status"],
        "evidence_quote": row["evidence_quote"],
    }


def _count(conn: Any, sql: str, params: tuple[Any, ...]) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row["n"])


def _related_counts(
    conn: Any,
    workspace_id: str,
    entity_id: str,
    statement_ids: list[str],
) -> dict[str, int]:
    typed_sql = """
        SELECT COUNT(*) AS n FROM typed_facts
        WHERE workspace_id = ? AND (subject_id = ? OR object_entity_id = ?
    """
    typed_params: list[Any] = [workspace_id, entity_id, entity_id]
    if statement_ids:
        typed_sql += f" OR from_statement_id IN ({_in_clause(statement_ids)})"
        typed_params.extend(statement_ids)
    typed_sql += ")"
    return {
        "typed_fact_count": _count(conn, typed_sql, tuple(typed_params)),
        "derived_fact_count": _count(
            conn,
            """
            SELECT COUNT(*) AS n FROM derived_facts
            WHERE workspace_id = ? AND (subject_id = ? OR object_entity_id = ?)
            """,
            (workspace_id, entity_id, entity_id),
        ),
        "merge_count": _count(
            conn,
            """
            SELECT COUNT(*) AS n FROM entity_merges
            WHERE workspace_id = ? AND (source_entity_id = ? OR target_entity_id = ?)
            """,
            (workspace_id, entity_id, entity_id),
        ),
    }


def _null_fk(conn: Any, table: str, column: str, ids: list[str]) -> None:
    if not ids:
        return
    conn.execute(
        f"UPDATE {table} SET {column} = NULL WHERE {column} IN ({_in_clause(ids)})",
        tuple(ids),
    )


def _delete_workspace_scoped_ids(conn: Any, table: str, workspace_id: str, column: str, ids: list[str]) -> None:
    if not ids:
        return
    conn.execute(
        f"DELETE FROM {table} WHERE workspace_id = ? AND {column} IN ({_in_clause(ids)})",
        (workspace_id, *ids),
    )


def preview_entity_deletion(conn: Any, workspace_id: str, entity_id: str) -> dict[str, Any]:
    entity = _load_entity(conn, workspace_id, entity_id)
    rows = _statement_rows(conn, workspace_id, entity_id)
    statements = [_statement_payload(row, entity_id) for row in rows]
    counts = _related_counts(
        conn,
        workspace_id,
        entity_id,
        [row["id"] for row in rows],
    )
    shown = statements[:_PREVIEW_LIMIT]
    return {
        "entity_id": entity["id"],
        "canonical_label": entity["canonical_label"],
        "statement_count": len(statements),
        "statements_truncated": len(statements) > len(shown),
        "statements": shown,
        **counts,
    }


def execute_delete_entity(conn: Any, workspace_id: str, entity_id: str) -> dict[str, Any]:
    entity = _load_entity(conn, workspace_id, entity_id)
    statement_ids = [row["id"] for row in _statement_rows(conn, workspace_id, entity_id)]

    typed_sql = """
        SELECT id FROM typed_facts
        WHERE workspace_id = ? AND (subject_id = ? OR object_entity_id = ?
    """
    typed_params: list[Any] = [workspace_id, entity_id, entity_id]
    if statement_ids:
        typed_sql += f" OR from_statement_id IN ({_in_clause(statement_ids)})"
        typed_params.extend(statement_ids)
    typed_sql += ")"
    typed_ids = [row["id"] for row in conn.execute(typed_sql, tuple(typed_params)).fetchall()]

    derived_ids = [
        row["id"]
        for row in conn.execute(
            """
            SELECT id FROM derived_facts
            WHERE workspace_id = ? AND (subject_id = ? OR object_entity_id = ?)
            """,
            (workspace_id, entity_id, entity_id),
        ).fetchall()
    ]

    if derived_ids:
        conn.execute(
            f"""
            DELETE FROM fact_derivations
            WHERE derived_fact_id IN ({_in_clause(derived_ids)})
            """,
            tuple(derived_ids),
        )
    if statement_ids:
        conn.execute(
            f"""
            DELETE FROM fact_derivations
            WHERE premise_kind = 'statement'
              AND premise_id IN ({_in_clause(statement_ids)})
            """,
            tuple(statement_ids),
        )
    _delete_workspace_scoped_ids(conn, "derived_facts", workspace_id, "id", derived_ids)

    _null_fk(conn, "statements", "supersedes_id", statement_ids)
    _null_fk(conn, "typed_facts", "supersedes_id", typed_ids)
    _delete_workspace_scoped_ids(conn, "statement_evidence", workspace_id, "statement_id", statement_ids)
    _delete_workspace_scoped_ids(conn, "statement_qualifiers", workspace_id, "statement_id", statement_ids)
    _delete_workspace_scoped_ids(conn, "time_mentions", workspace_id, "statement_id", statement_ids)
    _delete_workspace_scoped_ids(conn, "typed_facts", workspace_id, "id", typed_ids)
    for subject_type in _STATEMENT_REVIEW_SUBJECT_TYPES:
        if not statement_ids:
            break
        conn.execute(
            f"""
            DELETE FROM review_items
            WHERE workspace_id = ? AND subject_type = ?
              AND subject_id IN ({_in_clause(statement_ids)})
            """,
            (workspace_id, subject_type, *statement_ids),
        )
    _delete_workspace_scoped_ids(conn, "statements", workspace_id, "id", statement_ids)

    conn.execute(
        "DELETE FROM statement_qualifiers WHERE workspace_id = ? AND entity_id = ?",
        (workspace_id, entity_id),
    )
    purge_entity_connector_sync_data(conn, workspace_id, entity_id)
    conn.execute(
        "DELETE FROM entity_names WHERE workspace_id = ? AND entity_id = ?",
        (workspace_id, entity_id),
    )
    conn.execute(
        """
        DELETE FROM entity_merges
        WHERE workspace_id = ? AND (source_entity_id = ? OR target_entity_id = ?)
        """,
        (workspace_id, entity_id, entity_id),
    )
    conn.execute(
        "DELETE FROM entities WHERE workspace_id = ? AND id = ?",
        (workspace_id, entity_id),
    )
    conn.commit()

    return {
        "entity_id": entity["id"],
        "canonical_label": entity["canonical_label"],
        "statements_removed": len(statement_ids),
        "typed_facts_removed": len(typed_ids),
        "derived_facts_removed": len(derived_ids),
    }
