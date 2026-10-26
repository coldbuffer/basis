"""Scoped purge for workspace reset (not full workspace delete)."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.persistence.sql_delete import (
    _delete_workspace_rows,
    _null_workspace_supersedes,
)
from basis.domain.knowledge.services.workspace_reset_scopes import (
    SCOPE_CONNECTORS,
    SCOPE_GOVERNANCE,
    SCOPE_GRAPH,
    SCOPE_KNOWLEDGE,
    SCOPE_REASONING,
)


def purge_workspace_reset_data(
    conn: Any,
    workspace_id: str,
    scopes: frozenset[str],
    *,
    retain_job_ids: tuple[str, ...] = (),
) -> None:
    if SCOPE_KNOWLEDGE in scopes:
        conn.execute(
            """
            DELETE FROM chat_citations
            WHERE message_id IN (SELECT id FROM chat_messages WHERE workspace_id = ?)
            """,
            (workspace_id,),
        )
        _delete_workspace_rows(conn, "chat_messages", workspace_id)
        _delete_workspace_rows(conn, "chat_sessions", workspace_id)

        conn.execute(
            """
            DELETE FROM fact_derivations
            WHERE derived_fact_id IN (SELECT id FROM derived_facts WHERE workspace_id = ?)
               OR (
                    premise_kind = 'statement'
                    AND premise_id IN (SELECT id FROM statements WHERE workspace_id = ?)
               )
            """,
            (workspace_id, workspace_id),
        )
        _delete_workspace_rows(conn, "derived_facts", workspace_id)

        for table in ("agent_decisions", "statements", "mappings", "typed_facts"):
            _null_workspace_supersedes(conn, table, workspace_id)

        _delete_workspace_rows(conn, "review_items", workspace_id)
        _delete_workspace_rows(conn, "agent_decisions", workspace_id)
        _delete_workspace_rows(conn, "entity_merges", workspace_id)
        _delete_workspace_rows(conn, "statement_evidence", workspace_id)
        _delete_workspace_rows(conn, "statement_qualifiers", workspace_id)
        _delete_workspace_rows(conn, "time_mentions", workspace_id)
        _delete_workspace_rows(conn, "typed_facts", workspace_id)
        _delete_workspace_rows(conn, "statements", workspace_id)
        _delete_workspace_rows(conn, "mappings", workspace_id)
        _delete_workspace_rows(conn, "entity_names", workspace_id)
        _delete_workspace_rows(conn, "entities", workspace_id)

        _delete_workspace_rows(conn, "embedding_records", workspace_id)
        _delete_workspace_rows(conn, "extraction_drops", workspace_id)
        _delete_workspace_rows(conn, "chunks", workspace_id)

        conn.execute(
            "UPDATE documents SET current_version_id = NULL WHERE workspace_id = ?",
            (workspace_id,),
        )
        _delete_workspace_rows(conn, "document_versions", workspace_id)
        _delete_workspace_rows(conn, "documents", workspace_id)

        _delete_workspace_rows(conn, "alerts", workspace_id)
        _delete_workspace_rows(conn, "projection_state", workspace_id)

        if retain_job_ids:
            placeholders = ",".join("?" for _ in retain_job_ids)
            conn.execute(
                f"DELETE FROM jobs WHERE workspace_id = ? AND id NOT IN ({placeholders})",
                (workspace_id, *retain_job_ids),
            )
        else:
            _delete_workspace_rows(conn, "jobs", workspace_id)

    if SCOPE_CONNECTORS in scopes:
        _delete_workspace_rows(conn, "entity_sync_outbox", workspace_id)
        _delete_workspace_rows(conn, "entity_external_refs", workspace_id)
        _delete_workspace_rows(conn, "source_table_mappings", workspace_id)
        _delete_workspace_rows(conn, "connector_runs", workspace_id)
        _delete_workspace_rows(conn, "ingest_sources", workspace_id)
        for table in (
            "connector_policies",
            "connector_oauth_configs",
            "connector_connections",
        ):
            _delete_workspace_rows(conn, table, workspace_id)

    if SCOPE_REASONING in scopes:
        _delete_workspace_rows(conn, "reasoning_rules", workspace_id)

    if SCOPE_GOVERNANCE in scopes:
        _delete_workspace_rows(conn, "governance_configs", workspace_id)

    if SCOPE_GRAPH in scopes:
        _delete_workspace_rows(conn, "vocabulary_alignments", workspace_id)
