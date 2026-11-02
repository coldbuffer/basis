"""Entity rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def find_active_entity_id_by_label(conn: Any, workspace_id: str, label: str) -> Any:
    return conn.execute(
        """
        SELECT id FROM entities
        WHERE workspace_id = ? AND canonical_label = ? AND invalidated_at IS NULL
        LIMIT 1
        """,
        (workspace_id, label),
    ).fetchone()


def insert_entity(
    conn: Any,
    *,
    entity_id: str,
    workspace_id: str,
    canonical_label: str | None,
    description: str | None,
    entity_kind: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO entities(
            id, workspace_id, canonical_label, description, entity_kind, created_at, invalidated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (entity_id, workspace_id, canonical_label, description, entity_kind, created_at),
    )


def entity_labels_by_ids(
    conn: Any, workspace_id: str, entity_ids: list[str]
) -> dict[str, str | None]:
    if not entity_ids:
        return {}
    unique = list(dict.fromkeys(entity_ids))
    placeholders = ",".join("?" * len(unique))
    rows = conn.execute(
        f"""
        SELECT id, canonical_label FROM entities
        WHERE workspace_id = ? AND invalidated_at IS NULL
          AND id IN ({placeholders})
        """,
        (workspace_id, *unique),
    ).fetchall()
    labels: dict[str, str | None] = {eid: None for eid in unique}
    for row in rows:
        labels[row["id"]] = (row["canonical_label"] or "").strip() or None
    return labels


def active_entity_exists(conn: Any, workspace_id: str, entity_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM entities
        WHERE id = ? AND workspace_id = ? AND invalidated_at IS NULL
        """,
        (entity_id, workspace_id),
    ).fetchone()
    return row is not None


def count_entities_named(conn: Any, workspace_id: str, label: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM entities
        WHERE workspace_id = ? AND canonical_label = ? AND invalidated_at IS NULL
        """,
        (workspace_id, label),
    ).fetchone()
    return int(row["n"])
