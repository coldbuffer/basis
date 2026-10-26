"""Reset workspace ledger data while keeping the workspace admin row."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.persistence.sql_workspace_reset_purge import purge_workspace_reset_data
from basis.domain.knowledge.persistence.sql_workspace_reset import workspace_reset_preview


class WorkspaceResetAccess:
    def __init__(self, store: Any) -> None:
        self._store = store

    def preview_workspace_reset(self, workspace_id: str) -> dict[str, int]:
        self._store._assert_workspace_exists(workspace_id)
        with self._store._lock:
            return workspace_reset_preview(self._store._conn, workspace_id)

    def execute_workspace_reset(
        self,
        workspace_id: str,
        scopes: frozenset[str],
        *,
        retain_job_ids: tuple[str, ...] = (),
    ) -> dict[str, int]:
        self._store._assert_workspace_exists(workspace_id)
        with self._store._lock:
            before = workspace_reset_preview(self._store._conn, workspace_id)
            purge_workspace_reset_data(
                self._store._conn,
                workspace_id,
                scopes,
                retain_job_ids=retain_job_ids,
            )
            self._store._conn.commit()
        if scopes and "knowledge" in scopes:
            blob_store: BlobStore = self._store._blob_store
            blob_store.delete_workspace(workspace_id)
        return before
