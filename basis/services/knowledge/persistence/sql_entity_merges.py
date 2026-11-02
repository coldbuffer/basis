"""Entity merge ledger rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import sqlite3
from typing import Any


def entity_merge_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "source_entity_id": row["source_entity_id"],
        "target_entity_id": row["target_entity_id"],
        "decision_id": row["decision_id"],
        "actor_id": row["actor_id"],
        "why": row["why"],
        "created_at": row["created_at"],
        "reverted_at": row["reverted_at"],
        "reverted_by": row["reverted_by"],
    }


def insert_entity_merge(
    conn: Any,
    *,
    merge_id: str,
    workspace_id: str,
    source_entity_id: str,
    target_entity_id: str,
    decision_id: str | None,
    actor_id: str | None,
    why: str | None,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO entity_merges(
            id, workspace_id, source_entity_id, target_entity_id,
            decision_id, actor_id, why, created_at, reverted_at, reverted_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (
            merge_id,
            workspace_id,
            source_entity_id,
            target_entity_id,
            decision_id,
            actor_id,
            why,
            created_at,
        ),
    )


def fetch_entity_merge_by_id(conn: Any, merge_id: str) -> Any:
    return conn.execute("SELECT * FROM entity_merges WHERE id = ?", (merge_id,)).fetchone()


def fetch_entity_merge_for_workspace(conn: Any, merge_id: str, workspace_id: str) -> Any:
    return conn.execute(
        "SELECT * FROM entity_merges WHERE id = ? AND workspace_id = ?",
        (merge_id, workspace_id),
    ).fetchone()


def revert_entity_merge_row(
    conn: Any,
    merge_id: str,
    workspace_id: str,
    *,
    reverted_at: str,
    reverted_by: str,
) -> None:
    conn.execute(
        """
        UPDATE entity_merges
        SET reverted_at = ?, reverted_by = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (reverted_at, reverted_by, merge_id, workspace_id),
    )


def list_entity_merge_rows(
    conn: Any, workspace_id: str, *, active_only: bool, limit: int
) -> list[Any]:
    clause = "AND reverted_at IS NULL" if active_only else ""
    return conn.execute(
        f"""
        SELECT * FROM entity_merges
        WHERE workspace_id = ? {clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
