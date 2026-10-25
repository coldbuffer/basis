"""KnowledgeStore façade: DB lock, blob store, scope guards, delegates to ``access/*``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from basis.infra.runtime.database import Database, get_sqlite_database
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.access.connector import ConnectorAccess
from basis.domain.knowledge.access.governance import GovernanceAccess
from basis.domain.knowledge.access.document_delete import DocumentDeleteAccess
from basis.domain.knowledge.access.entity_delete import EntityDeleteAccess
from basis.domain.knowledge.access.entity_merges import EntityMergesAccess
from basis.domain.knowledge.access.graph_staging import GraphStagingAccess
from basis.domain.knowledge.access.documents import DocumentsAccess
from basis.domain.knowledge.access.ingest_ledger import IngestLedgerAccess
from basis.domain.knowledge.access.ledger import LedgerAccess
from basis.domain.knowledge.access.ingest_sources import IngestSourcesAccess
from basis.domain.knowledge.access.alerts import WorkspaceAlertsAccess
from basis.domain.ontology.reasoning_rules import ReasoningRulesAccess
from basis.domain.knowledge.access.processing import ProcessingJobsAccess
from basis.domain.knowledge.access.facts import FactsAccess
from basis.domain.ontology.mappings import MappingsAccess
from basis.domain.knowledge.access.projection import ProjectionAccess
from basis.domain.knowledge.access.review import ReviewAccess, merge_review_subject_key
from basis.domain.knowledge.access.search import SearchAccess
from basis.domain.knowledge.persistence import sql_guards as ledger_guards


class KnowledgeStore:
    """Canonical ledger access shared with AdminStore."""

    def __init__(self, db_path: Path | Database, blob_store: BlobStore) -> None:
        self._blob_store = blob_store
        if isinstance(db_path, Database):
            self._db = db_path
            self._owns_db_ref = False
        else:
            self._db = get_sqlite_database(db_path)
            self._owns_db_ref = True
        self._lock = self._db.lock
        self._conn = self._db.conn
        self._connector = ConnectorAccess(self)
        self._graph_staging = GraphStagingAccess(self)
        self._entity_delete = EntityDeleteAccess(self)
        self._entity_merges = EntityMergesAccess(self)
        self._document_delete = DocumentDeleteAccess(self)
        self._processing = ProcessingJobsAccess(self)
        self._documents = DocumentsAccess(self)
        self._ingest_ledger = IngestLedgerAccess(self)
        self._review = ReviewAccess(self)
        self._mappings = MappingsAccess(self)
        self._projection = ProjectionAccess(self)
        self._facts = FactsAccess(self)
        self._ingest_sources = IngestSourcesAccess(self)
        self._reasoning_rules = ReasoningRulesAccess(self)
        self._alerts = WorkspaceAlertsAccess(self)
        self._governance = GovernanceAccess(self)
        self._search = SearchAccess(self)
        self._ledger = LedgerAccess(self)

    def close(self) -> None:
        if self._owns_db_ref:
            self._db.release()

    @property
    def database(self) -> Database:
        return self._db

    def hard_delete_document(self, workspace_id: str, document_id: str) -> dict[str, Any]:
        return self._document_delete.execute_hard_delete_document(workspace_id, document_id)

    def delete_entity(self, workspace_id: str, entity_id: str) -> dict[str, Any]:
        return self._entity_delete.execute_delete_entity(workspace_id, entity_id)

    PROJECTION_SCHEMA_VERSION = 1

    def merge_review_subject_key(primary_id: str, duplicate_ids: list[str]) -> str:
        return merge_review_subject_key(primary_id, duplicate_ids)

    def _assert_workspace_exists(self, workspace_id: str) -> None:
        ledger_guards.assert_workspace_exists(self._conn, workspace_id)

    def _assert_row_in_workspace(self, table: str, row_id: str, workspace_id: str) -> None:
        ledger_guards.assert_row_in_workspace(self._conn, table, row_id, workspace_id)

def _workspace_access_delegate(access_attr: str, method_name: str):
    def _wrapped(self, *args, **kwargs):
        return getattr(getattr(self, access_attr), method_name)(*args, **kwargs)

    _wrapped.__name__ = method_name
    _wrapped.__qualname__ = f"KnowledgeStore.{method_name}"
    return _wrapped


for _name in (
    "connector_vault_persistence",
    "connector_sync_persistence",
    "get_platform_allowed_providers",
    "connector_runtime",
    "connector_sync_service",
    "list_source_table_mapping_ids",
    "list_entity_sync_outbox_ids",
    "reject_entity_sync_outbox",
    "list_connector_runs",
    "list_active_connector_table_mappings_global",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_connector", _name))

for _name in ("graph_staging_at", "upsert_graph_staging_session"):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_graph_staging", _name))

for _name in ("preview_entity_deletion", "execute_delete_entity"):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_entity_delete", _name))

for _name in (
    "store_upload_bytes",
    "store_document_bytes",
    "append_document_version",
    "get_document_summary",
    "resolve_document_ref",
    "find_document_by_external_key",
    "first_chunk_id_for_version",
    "ensure_legacy_document",
    "list_documents",
    "read_version_bytes",
    "list_chunks_for_version",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_documents", _name))

for _name in (
    "find_processing_job_by_idempotency_key",
    "create_processing_job",
    "get_version",
    "get_processing_context",
    "get_job",
    "list_processing_jobs",
    "set_job_result",
    "set_version_status",
    "set_job_status",
    "fail_version",
    "fail_job",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_processing", _name))

for _name in (
    "get_or_create_entity_by_label",
    "create_entity",
    "count_entities_named",
    "find_entity_id_by_label",
    "has_statement_on_chunk",
    "has_equivalent_statement",
    "add_extraction_drop",
    "count_statements_for_version",
    "add_open_statement",
    "create_chunk",
    "create_chunks",
    "set_statement_status",
    "invalidate_statement",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_ingest_ledger", _name))

for _name in (
    "create_review_item",
    "count_review_items",
    "list_review_items",
    "find_open_review_item",
    "get_review_item",
    "resolve_review_item",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_review", _name))

for _name in (
    "list_mappings",
    "create_mapping",
    "get_mapping",
    "update_mapping_status",
    "list_distinct_surface_phrases",
    "list_entity_type_object_labels",
    "entity_type_surface_phrases",
    "materialize_mapping_facts",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_mappings", _name))

for _name in (
    "get_ledger_temporal_bounds",
    "ensure_projection_state",
    "get_projection_state",
    "set_projection_status",
    "bump_projection_revision",
    "list_ready_documents_for_projection",
    "list_entities_for_projection",
    "list_statements_for_projection",
    "list_statements_for_temporal_projection",
    "list_entities_for_temporal_projection",
    "list_typed_facts_for_temporal_projection",
    "list_derived_facts_for_temporal_projection",
    "list_typed_facts_for_projection",
    "list_derived_facts_for_projection",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_projection", _name))

for _name in (
    "list_typed_facts",
    "insert_derived_fact",
    "list_derived_facts",
    "list_derived_facts_for_entity",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_facts", _name))

for _name in (
    "entity_labels_by_ids",
    "ledger_entity_exists",
    "record_agent_decision",
    "record_entity_merge",
    "entity_merge_redirect",
    "revert_entity_merge",
    "list_entity_merges",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_entity_merges", _name))

for _name in (
    "list_scheduled_ingest_sources_global",
    "list_http_poll_sources_global",
    "list_ingest_sources",
    "create_ingest_source",
    "get_ingest_source",
    "get_ingest_source_secret",
    "update_ingest_source",
    "delete_ingest_source",
    "rotate_ingest_source_token",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_ingest_sources", _name))

for _name in (
    "list_reasoning_rules",
    "create_reasoning_rule",
    "get_reasoning_rule",
    "update_reasoning_rule",
    "delete_reasoning_rule",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_reasoning_rules", _name))

for _name in (
    "create_workspace_alert",
    "get_workspace_alert",
    "list_alerts",
    "count_alerts",
    "count_workspace_unread_alerts",
    "list_alerts_since",
    "dismiss_workspace_alert",
    "dismiss_all_alerts",
    "mark_all_alerts_read",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_alerts", _name))

for _name in (
    "get_governance_config",
    "update_governance_config",
    "save_governance_shacl",
    "touch_governor_last_run",
    "list_governor_enabled_workspace_ids",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_governance", _name))

for _name in (
    "get_search_config",
    "update_search_config",
    "search_chunks_keyword",
    "search_chunks",
    "get_chunks_by_ids",
    "list_chunks_for_indexing",
    "chunk_ids_matching_filters",
    "get_embedding_record",
    "upsert_embedding_record",
    "delete_all_embedding_records",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_search", _name))

for _name in (
    "list_document_timeline_events",
    "list_active_statements",
    "list_active_entity_id_labels",
    "list_active_statements_below_confidence",
    "workspace_mcp_stats",
    "list_statements_for_chunk",
    "get_chunk",
    "count_browse_entities",
    "list_recent_entities",
    "find_entities",
    "list_entity_facts",
    "get_statement_browse",
):
    setattr(KnowledgeStore, _name, _workspace_access_delegate("_ledger", _name))
