"""Workspace reset jobs (`jobs.kind = workspace_reset`)."""

from __future__ import annotations

import json
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.persistence.sql_processing_jobs import (
    fail_job_row,
    fetch_job_row,
    processing_job_from_db_row,
    update_job_result,
    update_job_status,
)


WORKSPACE_RESET_KIND = "workspace_reset"
WORKSPACE_RESET_SUBJECT_TYPE = "workspace"


def fetch_active_workspace_reset_job(conn: Any, workspace_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, workspace_id, kind, subject_type, subject_id, status, attempt,
               progress, error_code, error_detail_json, options_json, result_json,
               created_at, started_at, finished_at
        FROM jobs
        WHERE workspace_id = ? AND kind = ?
          AND status IN ('queued', 'running')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (workspace_id, WORKSPACE_RESET_KIND),
    ).fetchone()
    if row is None:
        return None
    return processing_job_from_db_row(row)


def insert_workspace_reset_job(
    conn: Any,
    *,
    job_id: str,
    workspace_id: str,
    now: str,
    actor_id: str,
    scopes: list[str],
) -> None:
    conn.execute(
        """
        INSERT INTO jobs(
            id, workspace_id, kind, subject_type, subject_id, status, attempt,
            progress, error_code, error_detail_json, idempotency_key,
            created_at, started_at, finished_at, options_json, result_json
        ) VALUES (?, ?, ?, ?, ?, 'queued', 1,
            0, NULL, NULL, NULL, ?, NULL, NULL, ?, NULL)
        """,
        (
            job_id,
            workspace_id,
            WORKSPACE_RESET_KIND,
            WORKSPACE_RESET_SUBJECT_TYPE,
            workspace_id,
            now,
            json.dumps({"actor_id": actor_id, "scopes": scopes}, ensure_ascii=False),
        ),
    )


def mark_workspace_reset_running(conn: Any, workspace_id: str, job_id: str, started_at: str) -> None:
    update_job_status(conn, workspace_id, job_id, "running", started_at=started_at, finished_at=None)


def mark_workspace_reset_succeeded(
    conn: Any,
    workspace_id: str,
    job_id: str,
    *,
    finished_at: str,
    result: dict[str, Any],
) -> None:
    update_job_result(conn, workspace_id, job_id, json.dumps(result, ensure_ascii=False))
    update_job_status(conn, workspace_id, job_id, "succeeded", started_at=None, finished_at=finished_at)


def mark_workspace_reset_failed(
    conn: Any,
    workspace_id: str,
    job_id: str,
    *,
    code: str,
    message: str,
    finished_at: str,
) -> None:
    fail_job_row(
        conn,
        workspace_id,
        job_id,
        code,
        json.dumps({"message": message}, ensure_ascii=False),
        finished_at,
    )


def assert_workspace_reset_job(conn: Any, workspace_id: str, job_id: str) -> None:
    row = fetch_job_row(conn, workspace_id, job_id)
    if row.kind != WORKSPACE_RESET_KIND:
        raise AdminError(404, "not_found", "任务不存在")
