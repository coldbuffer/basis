"""Workspace reset preview counts — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.persistence.sql_stats import workspace_mcp_stats


def _count(conn: Any, sql: str, workspace_id: str) -> int:
    row = conn.execute(sql, (workspace_id,)).fetchone()
    return int(row["n"] if row else 0)


def workspace_reset_preview(conn: Any, workspace_id: str) -> dict[str, int]:
    stats = workspace_mcp_stats(conn, workspace_id)
    mapping_count = _count(
        conn,
        "SELECT COUNT(*) AS n FROM mappings WHERE workspace_id = ?",
        workspace_id,
    )
    review_count = _count(
        conn,
        "SELECT COUNT(*) AS n FROM review_items WHERE workspace_id = ?",
        workspace_id,
    )
    ingest_source_count = _count(
        conn,
        "SELECT COUNT(*) AS n FROM ingest_sources WHERE workspace_id = ?",
        workspace_id,
    )
    connector_connection_count = _count(
        conn,
        "SELECT COUNT(*) AS n FROM connector_connections WHERE workspace_id = ?",
        workspace_id,
    )
    reasoning_rule_count = _count(
        conn,
        "SELECT COUNT(*) AS n FROM reasoning_rules WHERE workspace_id = ?",
        workspace_id,
    )
    vocabulary_alignment_count = _count(
        conn,
        """
        SELECT COUNT(*) AS n FROM vocabulary_alignments WHERE workspace_id = ?
        """,
        workspace_id,
    )
    return {
        **stats,
        "mapping_count": mapping_count,
        "review_item_count": review_count,
        "ingest_source_count": ingest_source_count,
        "connector_connection_count": connector_connection_count,
        "reasoning_rule_count": reasoning_rule_count,
        "vocabulary_alignment_count": vocabulary_alignment_count,
    }
