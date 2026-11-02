"""Audit log persistence."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from basis.services.tenancy.admin.admin_types import utc_now_iso


def insert_audit(
    conn: Any,
    *,
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str | None,
    detail: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log(actor_id, action, target_type, target_id, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            actor_id,
            action,
            target_type,
            target_id,
            json.dumps(detail, ensure_ascii=False),
            utc_now_iso(),
        ),
    )


def audit_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "actor_id": row["actor_id"],
        "action": row["action"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "detail": json.loads(row["detail"]),
        "created_at": row["created_at"],
    }


def list_audit(
    conn: Any,
    limit: int,
    *,
    action_prefix: str | None = None,
) -> list[Any]:
    clauses: list[str] = []
    params: list[Any] = []
    if action_prefix:
        clauses.append("action LIKE ?")
        params.append(f"{action_prefix}%")
    where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
    params.append(limit)
    return conn.execute(
        f"SELECT * FROM audit_log {where}ORDER BY id DESC LIMIT ?",
        tuple(params),
    ).fetchall()


def list_audit_for_workspace(
    conn: Any,
    workspace_id: str,
    limit: int,
    *,
    action_prefix: str | None = None,
    backend: str = "sqlite",
) -> list[Any]:
    workspace_detail_expr = (
        "(detail::jsonb ->> 'workspace_id') = ?"
        if backend == "postgres"
        else "json_extract(detail, '$.workspace_id') = ?"
    )
    clauses = [workspace_detail_expr]
    params: list[Any] = [workspace_id]
    if action_prefix:
        clauses.append("action LIKE ?")
        params.append(f"{action_prefix}%")
    params.append(limit)
    sql = f"""
        SELECT * FROM audit_log
        WHERE {' AND '.join(clauses)}
        ORDER BY id DESC
        LIMIT ?
    """
    return conn.execute(sql, tuple(params)).fetchall()
