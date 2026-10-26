"""Soft-invalidate ledger entities and related rows — canonical DB SQL."""

from __future__ import annotations

from typing import Any

from basis.domain.errors import AdminError


def _entity_row(conn: Any, workspace_id: str, entity_id: str) -> Any:
    return conn.execute(
        """
        SELECT id, canonical_label, invalidated_at
        FROM entities
        WHERE workspace_id = ? AND id = ?
        """,
        (workspace_id, entity_id),
    ).fetchone()


def invalidate_statements_touching_entity(
    conn: Any,
    workspace_id: str,
    entity_id: str,
    invalidated_at: str,
) -> int:
    cur = conn.execute(
        """
        UPDATE statements
        SET status = 'invalidated', invalidated_at = ?
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (subject_id = ? OR object_entity_id = ?)
        """,
        (invalidated_at, workspace_id, entity_id, entity_id),
    )
    return int(cur.rowcount or 0)


def invalidate_typed_facts_touching_entity(
    conn: Any,
    workspace_id: str,
    entity_id: str,
    invalidated_at: str,
) -> int:
    cur = conn.execute(
        """
        UPDATE typed_facts
        SET invalidated_at = ?
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (subject_id = ? OR object_entity_id = ?)
        """,
        (invalidated_at, workspace_id, entity_id, entity_id),
    )
    return int(cur.rowcount or 0)


def invalidate_derived_facts_touching_entity(
    conn: Any,
    workspace_id: str,
    entity_id: str,
    invalidated_at: str,
) -> int:
    cur = conn.execute(
        """
        UPDATE derived_facts
        SET invalidated_at = ?
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND (subject_id = ? OR object_entity_id = ?)
        """,
        (invalidated_at, workspace_id, entity_id, entity_id),
    )
    return int(cur.rowcount or 0)


def invalidate_entity_row(
    conn: Any,
    workspace_id: str,
    entity_id: str,
    invalidated_at: str,
) -> None:
    cur = conn.execute(
        """
        UPDATE entities
        SET invalidated_at = ?
        WHERE workspace_id = ? AND id = ? AND invalidated_at IS NULL
        """,
        (invalidated_at, workspace_id, entity_id),
    )
    if int(cur.rowcount or 0) == 0:
        row = _entity_row(conn, workspace_id, entity_id)
        if row is None:
            raise AdminError(404, "not_found", "实体不存在")
        if row["invalidated_at"]:
            return
        raise AdminError(409, "invalidate_failed", "实体无法失效")


def execute_invalidate_entity(
    conn: Any,
    workspace_id: str,
    entity_id: str,
    invalidated_at: str,
) -> dict[str, Any]:
    row = _entity_row(conn, workspace_id, entity_id)
    if row is None:
        raise AdminError(404, "not_found", "实体不存在")
    if row["invalidated_at"]:
        return {
            "entity_id": entity_id,
            "canonical_label": row["canonical_label"],
            "already_invalidated": True,
            "statements_invalidated": 0,
            "typed_facts_invalidated": 0,
            "derived_facts_invalidated": 0,
        }
    statements = invalidate_statements_touching_entity(conn, workspace_id, entity_id, invalidated_at)
    typed = invalidate_typed_facts_touching_entity(conn, workspace_id, entity_id, invalidated_at)
    derived = invalidate_derived_facts_touching_entity(conn, workspace_id, entity_id, invalidated_at)
    invalidate_entity_row(conn, workspace_id, entity_id, invalidated_at)
    return {
        "entity_id": entity_id,
        "canonical_label": row["canonical_label"],
        "already_invalidated": False,
        "statements_invalidated": statements,
        "typed_facts_invalidated": typed,
        "derived_facts_invalidated": derived,
    }
