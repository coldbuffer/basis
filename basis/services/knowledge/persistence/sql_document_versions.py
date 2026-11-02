"""Document version rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import json
from typing import Any

from basis.services.errors import AdminError
from basis.services.knowledge.models import DocumentVersionRow


def has_active_ingest_job(conn: Any, workspace_id: str, version_id: str) -> bool:
    row = conn.execute(
        """
        SELECT id FROM jobs
        WHERE workspace_id = ? AND kind = 'ingest'
          AND subject_type = 'document_version' AND subject_id = ?
          AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (workspace_id, version_id),
    ).fetchone()
    return row is not None


def supersede_version(conn: Any, workspace_id: str, version_id: str) -> None:
    conn.execute(
        """
        UPDATE document_versions
        SET status = 'stale'
        WHERE id = ? AND workspace_id = ? AND status NOT IN ('failed', 'stale')
        """,
        (version_id, workspace_id),
    )


def fetch_version_row(conn: Any, workspace_id: str, version_id: str) -> DocumentVersionRow:
    row = conn.execute(
        """
        SELECT id, document_id, workspace_id, version_no, sha256, blob_key, byte_size, status
        FROM document_versions
        WHERE id = ? AND workspace_id = ?
        """,
        (version_id, workspace_id),
    ).fetchone()
    if row is None:
        raise AdminError(404, "not_found", "文档版本不存在")
    return DocumentVersionRow(
        id=row["id"],
        document_id=row["document_id"],
        workspace_id=row["workspace_id"],
        version_no=row["version_no"],
        sha256=row["sha256"],
        blob_key=row["blob_key"],
        byte_size=row["byte_size"],
        status=row["status"],
    )


def fetch_processing_context_row(conn: Any, workspace_id: str, version_id: str) -> Any:
    return conn.execute(
        """
        SELECT dv.id AS version_id, dv.status AS version_status,
               d.id AS document_id, d.external_key, d.title, d.mime_type
        FROM document_versions dv
        INNER JOIN documents d
          ON d.id = dv.document_id AND d.workspace_id = dv.workspace_id
        WHERE dv.id = ? AND dv.workspace_id = ? AND d.deleted_at IS NULL
        """,
        (version_id, workspace_id),
    ).fetchone()


def set_version_status(
    conn: Any,
    workspace_id: str,
    version_id: str,
    status: str,
    *,
    ready_at: str | None,
) -> None:
    if ready_at:
        conn.execute(
            """
            UPDATE document_versions
            SET status = ?, ready_at = ?
            WHERE id = ? AND workspace_id = ?
            """,
            (status, ready_at, version_id, workspace_id),
        )
    else:
        conn.execute(
            "UPDATE document_versions SET status = ? WHERE id = ? AND workspace_id = ?",
            (status, version_id, workspace_id),
        )


def queue_version_after_job_create(conn: Any, workspace_id: str, version_id: str) -> None:
    conn.execute(
        """
        UPDATE document_versions
        SET status = 'queued', error_code = NULL, error_detail_json = NULL
        WHERE id = ? AND workspace_id = ?
        """,
        (version_id, workspace_id),
    )


def fail_version(conn: Any, workspace_id: str, version_id: str, code: str, message: str) -> None:
    conn.execute(
        """
        UPDATE document_versions
        SET status = 'failed', error_code = ?, error_detail_json = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (code, json.dumps({"message": message}, ensure_ascii=False), version_id, workspace_id),
    )
