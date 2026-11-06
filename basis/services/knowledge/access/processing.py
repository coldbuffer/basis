"""Document version ingest jobs — KnowledgeStore API."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.knowledge.models import DocumentVersionRow, JobRow
from basis.services.knowledge.persistence import sql_document_versions as dv_persist
from basis.services.knowledge.persistence import sql_processing_jobs as job_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProcessingJobsAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def has_active_ingest_job(self, workspace_id: str, version_id: str) -> bool:
        return dv_persist.has_active_ingest_job(self._store._conn, workspace_id, version_id)

    def supersede_version(self, workspace_id: str, version_id: str) -> None:
        dv_persist.supersede_version(self._store._conn, workspace_id, version_id)

    @staticmethod
    def _processing_job_dict(
        *,
        job_id: str,
        workspace_id: str,
        version_id: str,
        attempt: int,
        now: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": job_id,
            "workspace_id": workspace_id,
            "kind": "ingest",
            "subject_type": "document_version",
            "subject_id": version_id,
            "status": "queued",
            "attempt": attempt,
            "progress": 0,
            "options": dict(options),
            "result": None,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "error_code": None,
            "error_detail": None,
        }

    def find_processing_job_by_idempotency_key(
        self,
        workspace_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        key = idempotency_key.strip()
        if not key:
            return None
        with self._store._lock:
            return job_persist.find_job_by_idempotency_key(self._store._conn, workspace_id, key)

    def create_processing_job(
        self,
        workspace_id: str,
        *,
        version_id: str,
        options: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        normalized_key = (idempotency_key or "").strip() or None
        if normalized_key:
            existing = self.find_processing_job_by_idempotency_key(workspace_id, normalized_key)
            if existing is not None:
                return existing, False

        job_id = str(uuid.uuid4())
        now = _now()
        with self._store._lock:
            self._store._assert_row_in_workspace("document_versions", version_id, workspace_id)
            conn = self._store._conn
            if job_persist.fetch_active_ingest_job_for_version(conn, workspace_id, version_id):
                raise AdminError(409, "processing_active", "该文档版本已有处理任务")
            attempt = job_persist.next_ingest_attempt(conn, workspace_id, version_id)
            try:
                job_persist.insert_ingest_job(
                    conn,
                    job_id=job_id,
                    workspace_id=workspace_id,
                    version_id=version_id,
                    attempt=attempt,
                    normalized_key=normalized_key,
                    now=now,
                    options_json=json.dumps(options, ensure_ascii=False, sort_keys=True),
                )
            except sqlite3.IntegrityError:
                if normalized_key:
                    row = job_persist.fetch_job_by_idempotency_after_conflict(
                        conn, workspace_id, normalized_key
                    )
                    if row is not None:
                        return row, False
                raise
            dv_persist.queue_version_after_job_create(conn, workspace_id, version_id)
            conn.commit()
        return (
            self._processing_job_dict(
                job_id=job_id,
                workspace_id=workspace_id,
                version_id=version_id,
                attempt=attempt,
                now=now,
                options=options,
            ),
            True,
        )

    def get_version(self, workspace_id: str, version_id: str) -> DocumentVersionRow:
        with self._store._lock:
            return dv_persist.fetch_version_row(self._store._conn, workspace_id, version_id)

    def get_processing_context(self, workspace_id: str, version_id: str) -> dict[str, Any]:
        with self._store._lock:
            row = dv_persist.fetch_processing_context_row(
                self._store._conn, workspace_id, version_id
            )
        if row is None:
            raise AdminError(404, "not_found", "文档版本不存在")
        return {
            "version_id": row["version_id"],
            "version_status": row["version_status"],
            "document_id": row["document_id"],
            "doc_id": row["external_key"] or row["document_id"],
            "filename": row["title"],
            "mime_type": row["mime_type"],
        }

    def get_job(self, workspace_id: str, job_id: str) -> JobRow:
        with self._store._lock:
            return job_persist.fetch_job_row(self._store._conn, workspace_id, job_id)

    def list_processing_jobs(
        self,
        workspace_id: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = job_persist.list_ingest_jobs(
                self._store._conn, workspace_id, status=status, limit=limit
            )
        return [
            {
                "id": row["id"],
                "kind": row["kind"],
                "subject_type": row["subject_type"],
                "version_id": row["subject_id"],
                "status": row["status"],
                "attempt": int(row["attempt"] or 1),
                "progress": row["progress"],
                "error_code": row["error_code"],
                "error_detail": (
                    json.loads(row["error_detail_json"])
                    if row["error_detail_json"]
                    else None
                ),
                "options": json.loads(row["options_json"]) if row["options_json"] else {},
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "document_id": row["document_id"],
                "doc_id": row["external_key"] or row["document_id"],
                "document_title": row["document_title"] or "",
                "version_status": row["version_status"],
            }
            for row in rows
        ]

    def set_job_result(self, workspace_id: str, job_id: str, result: dict[str, Any]) -> None:
        with self._store._lock:
            conn = self._store._conn
            if not job_persist.job_exists(conn, workspace_id, job_id):
                raise AdminError(404, "not_found", "任务不存在")
            job_persist.update_job_result(
                conn,
                workspace_id,
                job_id,
                json.dumps(result, ensure_ascii=False, default=str),
            )
            conn.commit()

    def set_version_status(self, workspace_id: str, version_id: str, status: str) -> None:
        allowed = {
            "uploaded",
            "queued",
            "parsing",
            "chunking",
            "embedding",
            "extracting",
            "ready",
            "failed",
            "stale",
            "paused",
        }
        if status not in allowed:
            raise AdminError(422, "bad_status", "版本状态无效")
        with self._store._lock:
            self._store._assert_row_in_workspace("document_versions", version_id, workspace_id)
            ready_at = _now() if status == "ready" else None
            dv_persist.set_version_status(
                self._store._conn, workspace_id, version_id, status, ready_at=ready_at
            )
            self._store._conn.commit()

    def set_job_checkpoint(
        self,
        workspace_id: str,
        job_id: str,
        checkpoint: dict[str, Any],
        progress: float,
    ) -> None:
        with self._store._lock:
            conn = self._store._conn
            if not job_persist.job_exists(conn, workspace_id, job_id):
                raise AdminError(404, "not_found", "任务不存在")
            current = job_persist.fetch_job_row(conn, workspace_id, job_id)
            result = dict(current.result or {})
            result["checkpoint"] = checkpoint
            job_persist.update_job_checkpoint(
                conn,
                workspace_id,
                job_id,
                json.dumps(result, ensure_ascii=False, default=str),
                max(0.0, min(1.0, float(progress))),
            )
            conn.commit()

    def try_transition_job_status(
        self,
        workspace_id: str,
        job_id: str,
        status: str,
        *,
        expect: set[str],
    ) -> bool:
        if status not in {"queued", "running", "succeeded", "failed", "cancelled", "paused"}:
            raise AdminError(422, "bad_status", "任务状态无效")
        if not expect:
            return False
        with self._store._lock:
            conn = self._store._conn
            if not job_persist.job_exists(conn, workspace_id, job_id):
                raise AdminError(404, "not_found", "任务不存在")
            started = _now() if status == "running" else None
            changed = job_persist.transition_job_status(
                conn,
                workspace_id,
                job_id,
                status,
                expect=tuple(sorted(expect)),
                started_at=started,
            )
            conn.commit()
            return changed == 1

    def list_live_ingest_jobs(self) -> list[tuple[str, str, str]]:
        with self._store._lock:
            rows = job_persist.list_live_ingest_job_keys(self._store._conn)
        return [(row["workspace_id"], row["id"], row["subject_id"]) for row in rows]

    def set_job_status(self, workspace_id: str, job_id: str, status: str) -> None:
        if status not in {"queued", "running", "succeeded", "failed", "cancelled", "paused"}:
            raise AdminError(422, "bad_status", "任务状态无效")
        with self._store._lock:
            conn = self._store._conn
            if not job_persist.job_exists(conn, workspace_id, job_id):
                raise AdminError(404, "not_found", "任务不存在")
            started = _now() if status == "running" else None
            finished = _now() if status in {"succeeded", "failed", "cancelled"} else None
            job_persist.update_job_status(
                conn, workspace_id, job_id, status, started_at=started, finished_at=finished
            )
            conn.commit()

    def fail_version(self, workspace_id: str, version_id: str, code: str, message: str) -> None:
        with self._store._lock:
            dv_persist.fail_version(self._store._conn, workspace_id, version_id, code, message)
            self._store._conn.commit()

    def fail_job(self, workspace_id: str, job_id: str, code: str, message: str) -> None:
        with self._store._lock:
            job_persist.fail_job_row(
                self._store._conn,
                workspace_id,
                job_id,
                code,
                json.dumps({"message": message}, ensure_ascii=False),
                _now(),
            )
            self._store._conn.commit()
        try:
            from basis.services.knowledge.services.alerts_emit import emit_processing_failed_alert

            emit_processing_failed_alert(self._store, workspace_id, job_id, code, message)
        except Exception:
            logger.exception(
                "processing.failed alert not recorded workspace_id=%s job_id=%s",
                workspace_id,
                job_id,
            )
