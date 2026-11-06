"""Ingest processing jobs — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from basis.services.errors import AdminError
from basis.services.knowledge.models import JobRow

_JOB_SELECT = """
    SELECT id, workspace_id, kind, subject_type, subject_id, status, attempt,
           progress, error_code, error_detail_json, options_json, result_json,
           created_at, started_at, finished_at
"""


def processing_job_from_db_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "kind": row["kind"],
        "subject_type": row["subject_type"],
        "subject_id": row["subject_id"],
        "status": row["status"],
        "attempt": int(row["attempt"] or 1),
        "progress": row["progress"],
        "options": json.loads(row["options_json"]) if row["options_json"] else {},
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "error_code": row["error_code"],
        "error_detail": (
            json.loads(row["error_detail_json"]) if row["error_detail_json"] else None
        ),
    }


def job_row_from_db(row: sqlite3.Row) -> JobRow:
    return JobRow(
        id=row["id"],
        workspace_id=row["workspace_id"],
        kind=row["kind"],
        subject_type=row["subject_type"],
        subject_id=row["subject_id"],
        status=row["status"],
        attempt=int(row["attempt"] or 1),
        progress=row["progress"],
        error_code=row["error_code"],
        error_detail=json.loads(row["error_detail_json"]) if row["error_detail_json"] else None,
        options=json.loads(row["options_json"]) if row["options_json"] else {},
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def find_job_by_idempotency_key(
    conn: Any, workspace_id: str, idempotency_key: str
) -> dict[str, Any] | None:
    row = conn.execute(
        f"""
        {_JOB_SELECT}
        FROM jobs
        WHERE workspace_id = ? AND kind = 'ingest' AND idempotency_key = ?
        LIMIT 1
        """,
        (workspace_id, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    return processing_job_from_db_row(row)


def fetch_active_ingest_job_for_version(conn: Any, workspace_id: str, version_id: str) -> Any:
    return conn.execute(
        """
        SELECT id FROM jobs
        WHERE workspace_id = ? AND kind = 'ingest'
          AND subject_type = 'document_version' AND subject_id = ?
          AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (workspace_id, version_id),
    ).fetchone()


def next_ingest_attempt(conn: Any, workspace_id: str, version_id: str) -> int:
    attempt_row = conn.execute(
        """
        SELECT COALESCE(MAX(attempt), 0) AS value FROM jobs
        WHERE workspace_id = ? AND kind = 'ingest'
          AND subject_type = 'document_version' AND subject_id = ?
        """,
        (workspace_id, version_id),
    ).fetchone()
    return int(attempt_row["value"] or 0) + 1


def insert_ingest_job(
    conn: Any,
    *,
    job_id: str,
    workspace_id: str,
    version_id: str,
    attempt: int,
    normalized_key: str | None,
    now: str,
    options_json: str,
) -> None:
    conn.execute(
        """
        INSERT INTO jobs(
            id, workspace_id, kind, subject_type, subject_id, status, attempt,
            progress, error_code, error_detail_json, idempotency_key,
            created_at, started_at, finished_at, options_json, result_json
        ) VALUES (?, ?, 'ingest', 'document_version', ?, 'queued', ?,
            0, NULL, NULL, ?, ?, NULL, NULL, ?, NULL)
        """,
        (
            job_id,
            workspace_id,
            version_id,
            attempt,
            normalized_key,
            now,
            options_json,
        ),
    )


def fetch_job_by_idempotency_after_conflict(
    conn: Any, workspace_id: str, normalized_key: str
) -> dict[str, Any] | None:
    row = conn.execute(
        f"""
        {_JOB_SELECT}
        FROM jobs
        WHERE workspace_id = ? AND kind = 'ingest' AND idempotency_key = ?
        LIMIT 1
        """,
        (workspace_id, normalized_key),
    ).fetchone()
    if row is None:
        return None
    return processing_job_from_db_row(row)


def fetch_job_row(conn: Any, workspace_id: str, job_id: str) -> JobRow:
    row = conn.execute(
        f"""
        {_JOB_SELECT}
        FROM jobs WHERE id = ? AND workspace_id = ?
        """,
        (job_id, workspace_id),
    ).fetchone()
    if row is None:
        raise AdminError(404, "not_found", "任务不存在")
    return job_row_from_db(row)


def job_exists(conn: Any, workspace_id: str, job_id: str) -> bool:
    row = conn.execute(
        "SELECT id FROM jobs WHERE id = ? AND workspace_id = ?", (job_id, workspace_id)
    ).fetchone()
    return row is not None


def list_ingest_jobs(
    conn: Any,
    workspace_id: str,
    *,
    status: str | None,
    limit: int,
) -> list[Any]:
    params: list[Any] = [workspace_id]
    status_clause = ""
    if status:
        status_clause = " AND j.status = ?"
        params.append(status)
    params.append(limit)
    return conn.execute(
        f"""
        SELECT j.id, j.kind, j.subject_type, j.subject_id, j.status,
               j.attempt, j.progress, j.error_code, j.error_detail_json,
               j.options_json, j.result_json, j.created_at, j.started_at,
               j.finished_at, d.id AS document_id, d.external_key,
               d.title AS document_title, dv.status AS version_status
        FROM jobs j
        LEFT JOIN document_versions dv
          ON dv.id = j.subject_id AND dv.workspace_id = j.workspace_id
        LEFT JOIN documents d
          ON d.id = dv.document_id AND d.workspace_id = j.workspace_id
        WHERE j.workspace_id = ? AND j.kind = 'ingest'{status_clause}
        ORDER BY j.created_at DESC
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()


def update_job_result(conn: Any, workspace_id: str, job_id: str, result_json: str) -> None:
    conn.execute(
        "UPDATE jobs SET result_json = ?, progress = 1 WHERE id = ? AND workspace_id = ?",
        (result_json, job_id, workspace_id),
    )


def update_job_checkpoint(
    conn: Any,
    workspace_id: str,
    job_id: str,
    result_json: str,
    progress: float,
) -> int:
    """Store resume progress without forcing the job to complete."""
    cursor = conn.execute(
        """
        UPDATE jobs
        SET result_json = ?, progress = ?
        WHERE id = ? AND workspace_id = ?
          AND status IN ('queued', 'running', 'paused')
        """,
        (result_json, progress, job_id, workspace_id),
    )
    return int(cursor.rowcount or 0)


def list_live_ingest_job_keys(conn: Any) -> list[Any]:
    return conn.execute(
        """
        SELECT workspace_id, id, subject_id
        FROM jobs
        WHERE kind = 'ingest' AND subject_type = 'document_version'
          AND status IN ('queued', 'running')
        """
    ).fetchall()


def transition_job_status(
    conn: Any,
    workspace_id: str,
    job_id: str,
    status: str,
    *,
    expect: tuple[str, ...],
    started_at: str | None,
) -> int:
    if not expect:
        return 0
    placeholders = ", ".join("?" for _ in expect)
    if started_at:
        cursor = conn.execute(
            f"""
            UPDATE jobs
            SET status = ?, started_at = COALESCE(started_at, ?)
            WHERE id = ? AND workspace_id = ? AND status IN ({placeholders})
            """,
            (status, started_at, job_id, workspace_id, *expect),
        )
    else:
        cursor = conn.execute(
            f"""
            UPDATE jobs
            SET status = ?
            WHERE id = ? AND workspace_id = ? AND status IN ({placeholders})
            """,
            (status, job_id, workspace_id, *expect),
        )
    return int(cursor.rowcount or 0)


def update_job_status(
    conn: Any,
    workspace_id: str,
    job_id: str,
    status: str,
    *,
    started_at: str | None,
    finished_at: str | None,
) -> None:
    if started_at:
        conn.execute(
            """
            UPDATE jobs SET status = ?, started_at = COALESCE(started_at, ?)
            WHERE id = ? AND workspace_id = ?
            """,
            (status, started_at, job_id, workspace_id),
        )
    elif finished_at:
        conn.execute(
            "UPDATE jobs SET status = ?, finished_at = ? WHERE id = ? AND workspace_id = ?",
            (status, finished_at, job_id, workspace_id),
        )
    else:
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ? AND workspace_id = ?",
            (status, job_id, workspace_id),
        )


def fail_job_row(
    conn: Any,
    workspace_id: str,
    job_id: str,
    code: str,
    error_detail_json: str,
    finished_at: str,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status = 'failed', error_code = ?, error_detail_json = ?, finished_at = ?
        WHERE id = ? AND workspace_id = ?
        """,
        (code, error_detail_json, finished_at, job_id, workspace_id),
    )
