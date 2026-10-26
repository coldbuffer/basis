"""Reset workspace ledger data while keeping the workspace admin row."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.persistence.sql_workspace_reset_job import (
    fetch_active_workspace_reset_job,
    insert_workspace_reset_job,
    mark_workspace_reset_failed,
    mark_workspace_reset_running,
    mark_workspace_reset_succeeded,
)
from basis.domain.knowledge.persistence.sql_workspace_reset_purge import purge_workspace_reset_data
from basis.domain.knowledge.persistence.sql_workspace_reset import workspace_reset_preview
from basis.domain.knowledge.services.workspace_reset_scopes import (
    DEFAULT_RESET_SCOPES,
    normalize_reset_scopes,
    scopes_for_api,
)

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def fetch_active_workspace_reset_job(self, workspace_id: str) -> dict[str, Any] | None:
        self._store._assert_workspace_exists(workspace_id)
        with self._store._lock:
            return fetch_active_workspace_reset_job(self._store._conn, workspace_id)

    def enqueue_workspace_reset_job(
        self,
        workspace_id: str,
        *,
        actor_id: str,
        scopes: frozenset[str],
    ) -> dict[str, Any]:
        self._store._assert_workspace_exists(workspace_id)
        with self._store._lock:
            conn = self._store._conn
            active = fetch_active_workspace_reset_job(conn, workspace_id)
            if active is not None:
                return {
                    "accepted": True,
                    "job_id": active["id"],
                    "status": active["status"],
                    "duplicate": True,
                }
            job_id = str(uuid.uuid4())
            now = _utc_now_iso()
            insert_workspace_reset_job(
                conn,
                job_id=job_id,
                workspace_id=workspace_id,
                now=now,
                actor_id=actor_id,
                scopes=scopes_for_api(scopes),
            )
            conn.commit()
        return {"accepted": True, "job_id": job_id, "status": "queued", "duplicate": False}

    def mark_workspace_reset_running(
        self,
        workspace_id: str,
        job_id: str,
        started_at: str,
    ) -> None:
        with self._store._lock:
            mark_workspace_reset_running(self._store._conn, workspace_id, job_id, started_at)
            self._store._conn.commit()

    def mark_workspace_reset_succeeded(
        self,
        workspace_id: str,
        job_id: str,
        *,
        finished_at: str,
        result: dict[str, Any],
    ) -> None:
        with self._store._lock:
            mark_workspace_reset_succeeded(
                self._store._conn,
                workspace_id,
                job_id,
                finished_at=finished_at,
                result=result,
            )
            self._store._conn.commit()

    def mark_workspace_reset_failed(
        self,
        workspace_id: str,
        job_id: str,
        *,
        code: str,
        message: str,
        finished_at: str,
    ) -> None:
        with self._store._lock:
            mark_workspace_reset_failed(
                self._store._conn,
                workspace_id,
                job_id,
                code=code,
                message=message,
                finished_at=finished_at,
            )
            self._store._conn.commit()

    def workspace_reset_job_scopes(self, workspace_id: str, job_id: str) -> frozenset[str]:
        row = self._store._processing.get_job(workspace_id, job_id)
        opts = row.options if isinstance(row.options, dict) else {}
        raw = opts.get("scopes")
        scopes = normalize_reset_scopes(raw)
        return scopes if scopes is not None else DEFAULT_RESET_SCOPES
