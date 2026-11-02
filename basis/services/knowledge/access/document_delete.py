"""Document hard-delete API on KnowledgeStore."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.services.knowledge.persistence.sql_document_delete import execute_hard_delete_document

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


class DocumentDeleteAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def execute_hard_delete_document(self, workspace_id: str, document_id: str) -> dict:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return execute_hard_delete_document(self._store, workspace_id, document_id)
