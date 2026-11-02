"""Statement + evidence rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def has_statement_on_chunk(
    conn: Any,
    workspace_id: str,
    chunk_id: str,
    subject_id: str,
    surface_phrase: str,
    *,
    object_entity_id: str | None,
    object_value: str | None,
) -> bool:
    if object_entity_id is not None:
        row = conn.execute(
            """
            SELECT s.id FROM statements s
            INNER JOIN statement_evidence e ON e.statement_id = s.id AND e.chunk_id = ?
            WHERE s.workspace_id = ? AND s.subject_id = ? AND s.surface_phrase = ?
              AND s.object_entity_id = ? AND s.invalidated_at IS NULL
            LIMIT 1
            """,
            (chunk_id, workspace_id, subject_id, surface_phrase, object_entity_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT s.id FROM statements s
            INNER JOIN statement_evidence e ON e.statement_id = s.id AND e.chunk_id = ?
            WHERE s.workspace_id = ? AND s.subject_id = ? AND s.surface_phrase = ?
              AND s.object_value = ? AND s.invalidated_at IS NULL
            LIMIT 1
            """,
            (chunk_id, workspace_id, subject_id, surface_phrase, object_value),
        ).fetchone()
    return row is not None


def has_equivalent_statement(
    conn: Any,
    workspace_id: str,
    subject_id: str,
    surface_phrase: str,
    *,
    object_entity_id: str | None,
    object_value: str | None,
) -> bool:
    if object_entity_id is not None:
        row = conn.execute(
            """
            SELECT id FROM statements
            WHERE workspace_id = ? AND subject_id = ? AND surface_phrase = ?
              AND object_entity_id = ? AND invalidated_at IS NULL
              AND status IN ('pending', 'confirmed')
            LIMIT 1
            """,
            (workspace_id, subject_id, surface_phrase, object_entity_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id FROM statements
            WHERE workspace_id = ? AND subject_id = ? AND surface_phrase = ?
              AND object_value = ? AND invalidated_at IS NULL
              AND status IN ('pending', 'confirmed')
            LIMIT 1
            """,
            (workspace_id, subject_id, surface_phrase, object_value),
        ).fetchone()
    return row is not None


def count_statements_for_version(conn: Any, workspace_id: str, version_id: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM statements s
        INNER JOIN statement_evidence e ON e.statement_id = s.id
        INNER JOIN chunks c ON c.id = e.chunk_id
        WHERE c.workspace_id = ? AND c.version_id = ? AND s.invalidated_at IS NULL
        """,
        (workspace_id, version_id),
    ).fetchone()
    return int(row["n"])


def insert_statement_with_evidence(
    conn: Any,
    *,
    statement_id: str,
    workspace_id: str,
    subject_id: str,
    surface_phrase: str,
    object_entity_id: str | None,
    object_value: str | None,
    confidence: float | None,
    status: str,
    proposed_by: str,
    recorded_at: str,
    evidence_id: str,
    chunk_id: str,
    quote: str,
    quote_start: int | None,
    quote_end: int | None,
) -> None:
    conn.execute(
        """
        INSERT INTO statements(
            id, workspace_id, subject_id, surface_phrase, object_entity_id, object_value,
            object_datatype, confidence, status, proposed_by, recorded_at,
            invalidated_at, supersedes_id
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, NULL)
        """,
        (
            statement_id,
            workspace_id,
            subject_id,
            surface_phrase,
            object_entity_id,
            object_value,
            confidence,
            status,
            proposed_by,
            recorded_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO statement_evidence(
            id, workspace_id, statement_id, chunk_id, quote, quote_start, quote_end, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (evidence_id, workspace_id, statement_id, chunk_id, quote, quote_start, quote_end, recorded_at),
    )


def fetch_statement_workspace_status(conn: Any, statement_id: str) -> Any:
    return conn.execute(
        "SELECT workspace_id, status FROM statements WHERE id = ?", (statement_id,)
    ).fetchone()


def fetch_statement_for_workspace(conn: Any, statement_id: str) -> Any:
    return conn.execute("SELECT workspace_id FROM statements WHERE id = ?", (statement_id,)).fetchone()


def update_statement_status(
    conn: Any,
    workspace_id: str,
    statement_id: str,
    status: str,
    invalidated_at: str | None,
) -> None:
    conn.execute(
        """
        UPDATE statements
        SET status = ?, invalidated_at = COALESCE(?, invalidated_at)
        WHERE id = ? AND workspace_id = ?
        """,
        (status, invalidated_at, statement_id, workspace_id),
    )


def invalidate_statement_row(conn: Any, workspace_id: str, statement_id: str, invalidated_at: str) -> None:
    conn.execute(
        """
        UPDATE statements
        SET status = 'invalidated', invalidated_at = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (invalidated_at, statement_id, workspace_id),
    )


def list_active_statement_rows(conn: Any, workspace_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT
            s.id AS statement_id,
            s.subject_id,
            s.surface_phrase,
            s.object_entity_id,
            s.object_value,
            s.status,
            s.proposed_by,
            (
                SELECT e.quote
                FROM statement_evidence e
                WHERE e.statement_id = s.id AND e.workspace_id = s.workspace_id
                ORDER BY e.created_at
                LIMIT 1
            ) AS quote
        FROM statements s
        WHERE s.workspace_id = ?
          AND s.invalidated_at IS NULL
          AND s.status IN ('pending', 'confirmed')
        ORDER BY s.recorded_at ASC
        """,
        (workspace_id,),
    ).fetchall()


def list_active_statements_below_confidence_rows(
    conn: Any, workspace_id: str, confidence_min: float
) -> list[Any]:
    return conn.execute(
        """
        SELECT id AS statement_id, subject_id, surface_phrase,
               object_entity_id, object_value, status, confidence
        FROM statements
        WHERE workspace_id = ?
          AND invalidated_at IS NULL
          AND status IN ('pending', 'confirmed')
          AND confidence IS NOT NULL
          AND confidence < ?
        ORDER BY confidence ASC, recorded_at ASC
        """,
        (workspace_id, confidence_min),
    ).fetchall()


def list_statements_for_chunk_rows(
    conn: Any, workspace_id: str, chunk_id: str, limit: int
) -> list[Any]:
    return conn.execute(
        """
        SELECT
            s.id AS statement_id,
            s.surface_phrase,
            s.subject_id,
            s.object_entity_id,
            s.object_value,
            s.status,
            e.quote
        FROM statements s
        INNER JOIN statement_evidence e ON e.statement_id = s.id AND e.chunk_id = ?
        WHERE s.workspace_id = ? AND s.invalidated_at IS NULL
        ORDER BY s.recorded_at DESC
        LIMIT ?
        """,
        (chunk_id, workspace_id, limit),
    ).fetchall()


def fetch_statement_browse_row(conn: Any, workspace_id: str, statement_id: str) -> Any:
    return conn.execute(
        """
        SELECT id, subject_id, surface_phrase, object_entity_id, object_value, status
        FROM statements
        WHERE workspace_id = ? AND id = ? AND invalidated_at IS NULL
        """,
        (workspace_id, statement_id),
    ).fetchone()


def list_entity_fact_rows(
    conn: Any, workspace_id: str, entity_id: str, limit: int
) -> list[Any]:
    return conn.execute(
        """
        SELECT
            s.id,
            s.surface_phrase,
            s.object_entity_id,
            s.object_value,
            s.status,
            s.confidence,
            s.recorded_at,
            (
                SELECT e.chunk_id
                FROM statement_evidence e
                WHERE e.statement_id = s.id AND e.workspace_id = ?
                ORDER BY e.created_at
                LIMIT 1
            ) AS evidence_chunk_id,
            (
                SELECT e.quote
                FROM statement_evidence e
                WHERE e.statement_id = s.id AND e.workspace_id = ?
                ORDER BY e.created_at
                LIMIT 1
            ) AS evidence_quote
        FROM statements s
        WHERE s.workspace_id = ? AND s.subject_id = ? AND s.invalidated_at IS NULL
        ORDER BY s.recorded_at DESC
        LIMIT ?
        """,
        (workspace_id, workspace_id, workspace_id, entity_id, limit),
    ).fetchall()
