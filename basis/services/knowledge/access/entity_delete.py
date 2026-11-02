"""Entity delete API on KnowledgeStore."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.services.knowledge.persistence.sql_entity_delete import (
    execute_delete_entity as _execute_delete_entity,
    preview_entity_deletion as _preview_entity_deletion,
)

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


class EntityDeleteAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def preview_entity_deletion(self, workspace_id: str, entity_id: str) -> dict:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return _preview_entity_deletion(self._store._conn, workspace_id, entity_id)

    def execute_delete_entity(self, workspace_id: str, entity_id: str) -> dict:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return _execute_delete_entity(self._store._conn, workspace_id, entity_id)
