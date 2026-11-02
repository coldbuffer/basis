"""Entity browse / search — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def entity_browse_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "entity_id": row["id"],
        "canonical_label": row["canonical_label"],
        "description": row["description"],
        "entity_kind": row["entity_kind"],
    }


def list_active_entity_id_label_rows(conn: Any, workspace_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT id AS entity_id, canonical_label
        FROM entities
        WHERE workspace_id = ? AND invalidated_at IS NULL
        """,
        (workspace_id,),
    ).fetchall()


def count_browse_entities(conn: Any, workspace_id: str, *, pattern: str | None) -> int:
    if pattern:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM entities
            WHERE workspace_id = ? AND invalidated_at IS NULL
              AND (canonical_label LIKE ? OR description LIKE ?)
            """,
            (workspace_id, pattern, pattern),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM entities
            WHERE workspace_id = ? AND invalidated_at IS NULL
            """,
            (workspace_id,),
        ).fetchone()
    return int(row["n"] or 0)


def list_recent_entity_rows(
    conn: Any, workspace_id: str, *, limit: int, offset: int
) -> list[Any]:
    return conn.execute(
        """
        SELECT id, canonical_label, description, entity_kind
        FROM entities
        WHERE workspace_id = ? AND invalidated_at IS NULL
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (workspace_id, limit, offset),
    ).fetchall()


def find_entity_rows(
    conn: Any, workspace_id: str, *, pattern: str, limit: int, offset: int
) -> list[Any]:
    return conn.execute(
        """
        SELECT id, canonical_label, description, entity_kind
        FROM entities
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (canonical_label LIKE ? OR description LIKE ?)
        ORDER BY canonical_label
        LIMIT ? OFFSET ?
        """,
        (workspace_id, pattern, pattern, limit, offset),
    ).fetchall()
