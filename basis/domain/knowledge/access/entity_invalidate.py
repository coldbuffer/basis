"""Entity soft-invalidate API on KnowledgeStore."""

from __future__ import annotations

from typing import TYPE_CHECKING

from basis.domain.knowledge.persistence.sql_entity_invalidate import execute_invalidate_entity

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore


class EntityInvalidateAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def invalidate_entity(self, workspace_id: str, entity_id: str, *, invalidated_at: str) -> dict:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            outcome = execute_invalidate_entity(
                self._store._conn, workspace_id, entity_id, invalidated_at
            )
            self._store._conn.commit()
            return outcome
