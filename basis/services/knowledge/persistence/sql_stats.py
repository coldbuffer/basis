"""Aggregate workspace counts — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def workspace_mcp_stats(conn: Any, workspace_id: str) -> dict[str, int]:
    docs = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE workspace_id = ?", (workspace_id,)
    ).fetchone()["n"]
    chunks = conn.execute(
        "SELECT COUNT(*) AS n FROM chunks WHERE workspace_id = ?", (workspace_id,)
    ).fetchone()["n"]
    entities = conn.execute(
        """
        SELECT COUNT(*) AS n FROM entities
        WHERE workspace_id = ? AND invalidated_at IS NULL
        """,
        (workspace_id,),
    ).fetchone()["n"]
    statements = conn.execute(
        """
        SELECT COUNT(*) AS n FROM statements
        WHERE workspace_id = ? AND invalidated_at IS NULL
        """,
        (workspace_id,),
    ).fetchone()["n"]
    return {
        "document_count": int(docs),
        "chunk_count": int(chunks),
        "entity_count": int(entities),
        "statement_count": int(statements),
    }
