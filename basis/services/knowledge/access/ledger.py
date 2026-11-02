"""Ledger browse: timeline, entities, chunks, statements — KnowledgeStore API."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from basis.services.knowledge.persistence import sql_chunks as chunk_persist
from basis.services.knowledge.persistence import sql_document_timeline as timeline_persist
from basis.services.knowledge.persistence import sql_entity_browse as entity_persist
from basis.services.knowledge.persistence import sql_stats as stats_persist
from basis.services.knowledge.persistence import sql_statements as stmt_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


class LedgerAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def list_document_timeline_events(
        self,
        workspace_id: str,
        document_id: str,
        *,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 500)
        events: list[dict[str, Any]] = []
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            conn = self._store._conn
            doc = timeline_persist.fetch_document_header(conn, workspace_id, document_id)
            if doc is None:
                return []
            version_rows = timeline_persist.list_document_version_rows(
                conn, workspace_id, document_id
            )
            version_ids = [row["id"] for row in version_rows]
            for row in version_rows:
                events.append(
                    {
                        "kind": "version_created",
                        "at": row["created_at"],
                        "version_id": row["id"],
                        "status": row["status"],
                        "byte_size": row["byte_size"],
                    }
                )
            if version_ids:
                for row in timeline_persist.list_ingest_jobs_for_versions(
                    conn, workspace_id, version_ids
                ):
                    events.append(
                        {
                            "kind": "processing_job",
                            "at": row["finished_at"] or row["created_at"],
                            "job_id": row["id"],
                            "status": row["status"],
                            "error_code": row["error_code"],
                        }
                    )
                for row in timeline_persist.list_statements_for_document_versions(
                    conn, workspace_id, version_ids
                ):
                    events.append(
                        {
                            "kind": "statement_recorded",
                            "at": row["recorded_at"],
                            "statement_id": row["id"],
                            "surface_phrase": row["surface_phrase"],
                            "status": row["status"],
                            "invalidated_at": row["invalidated_at"],
                            "chunk_id": row["chunk_id"],
                        }
                    )
                for row in timeline_persist.list_time_mentions_for_versions(
                    conn, workspace_id, version_ids
                ):
                    events.append(
                        {
                            "kind": "time_mention",
                            "at": row["statement_at"],
                            "mention_id": row["id"],
                            "text": row["text"],
                            "char_start": row["char_start"],
                            "char_end": row["char_end"],
                            "chunk_id": row["chunk_id"],
                        }
                    )
        events.sort(key=lambda ev: str(ev.get("at") or ""))
        return events[-limit:]

    def list_active_statements(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = stmt_persist.list_active_statement_rows(self._store._conn, workspace_id)
        return [dict(row) for row in rows]

    def list_active_entity_id_labels(self, workspace_id: str) -> list[dict[str, str]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = entity_persist.list_active_entity_id_label_rows(
                self._store._conn, workspace_id
            )
        return [
            {
                "entity_id": str(row["entity_id"]),
                "canonical_label": row["canonical_label"] or "",
            }
            for row in rows
        ]

    def list_active_statements_below_confidence(
        self, workspace_id: str, confidence_min: float
    ) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = stmt_persist.list_active_statements_below_confidence_rows(
                self._store._conn, workspace_id, confidence_min
            )
        return [dict(row) for row in rows]

    def workspace_mcp_stats(self, workspace_id: str) -> dict[str, int]:
        with self._store._lock:
            return stats_persist.workspace_mcp_stats(self._store._conn, workspace_id)

    def list_statements_for_chunk(
        self, workspace_id: str, chunk_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 100)
        with self._store._lock:
            self._store._assert_row_in_workspace("chunks", chunk_id, workspace_id)
            rows = stmt_persist.list_statements_for_chunk_rows(
                self._store._conn, workspace_id, chunk_id, limit
            )
        return [
            {
                "statement_id": row["statement_id"],
                "surface_phrase": row["surface_phrase"],
                "subject_id": row["subject_id"],
                "object_entity_id": row["object_entity_id"],
                "object_value": row["object_value"],
                "status": row["status"],
                "quote": row["quote"],
            }
            for row in rows
        ]

    def get_chunk(self, workspace_id: str, chunk_id: str) -> dict[str, Any] | None:
        with self._store._lock:
            row = chunk_persist.fetch_chunk_with_document(
                self._store._conn, workspace_id, chunk_id
            )
        if row is None:
            return None
        return {
            "chunk_id": row["id"],
            "document_id": row["document_id"],
            "document_title": row["document_title"] or "",
            **chunk_persist.chunk_api_row(row),
        }

    def count_browse_entities(self, workspace_id: str, *, query: str = "") -> int:
        query = query.strip()
        pattern = f"%{query.replace('%', '')}%" if query else None
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return entity_persist.count_browse_entities(
                self._store._conn, workspace_id, pattern=pattern
            )

    def list_recent_entities(
        self,
        workspace_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 50)
        offset = max(0, offset)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = entity_persist.list_recent_entity_rows(
                self._store._conn, workspace_id, limit=limit, offset=offset
            )
        return [entity_persist.entity_browse_row(row) for row in rows]

    def find_entities(
        self,
        workspace_id: str,
        *,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        limit = min(max(1, limit), 50)
        offset = max(0, offset)
        pattern = f"%{query.replace('%', '')}%"
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = entity_persist.find_entity_rows(
                self._store._conn, workspace_id, pattern=pattern, limit=limit, offset=offset
            )
        return [entity_persist.entity_browse_row(row) for row in rows]

    def list_entity_facts(
        self, workspace_id: str, *, entity_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 100)
        with self._store._lock:
            self._store._assert_row_in_workspace("entities", entity_id, workspace_id)
            rows = stmt_persist.list_entity_fact_rows(
                self._store._conn, workspace_id, entity_id, limit
            )
        return [
            {
                "statement_id": row["id"],
                "surface_phrase": row["surface_phrase"],
                "object_entity_id": row["object_entity_id"],
                "object_value": row["object_value"],
                "status": row["status"],
                "confidence": row["confidence"],
                "recorded_at": row["recorded_at"],
                "evidence_chunk_id": row["evidence_chunk_id"],
                "evidence_quote": row["evidence_quote"],
            }
            for row in rows
        ]

    def get_statement_browse(
        self, workspace_id: str, *, statement_id: str
    ) -> dict[str, Any] | None:
        with self._store._lock:
            row = stmt_persist.fetch_statement_browse_row(
                self._store._conn, workspace_id, statement_id
            )
        if row is None:
            return None
        return {
            "statement_id": row["id"],
            "subject_id": row["subject_id"],
            "surface_phrase": row["surface_phrase"],
            "object_entity_id": row["object_entity_id"],
            "object_value": row["object_value"],
            "status": row["status"],
        }
