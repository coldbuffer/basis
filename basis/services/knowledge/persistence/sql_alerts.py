"""Workspace alert rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

_ALERT_SELECT = """
    SELECT id, workspace_id, kind, severity, message, detail_json,
           created_at, read_at, dismissed_at
"""


def alert_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    detail_raw = row["detail_json"]
    try:
        detail = json.loads(detail_raw) if detail_raw else {}
    except json.JSONDecodeError:
        detail = {}
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "kind": row["kind"],
        "severity": row["severity"],
        "message": row["message"],
        "detail": detail,
        "created_at": row["created_at"],
        "read_at": row["read_at"],
        "dismissed_at": row["dismissed_at"],
    }


def insert_workspace_alert(
    conn: Any,
    *,
    alert_id: str,
    workspace_id: str,
    kind: str,
    severity: str,
    message: str,
    detail_json: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO alerts (
            id, workspace_id, kind, severity, message, detail_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (alert_id, workspace_id, kind, severity, message, detail_json, created_at),
    )


def fetch_workspace_alert(conn: Any, workspace_id: str, alert_id: str) -> Any:
    return conn.execute(
        f"""
        {_ALERT_SELECT}
        FROM alerts
        WHERE workspace_id = ? AND id = ?
        """,
        (workspace_id, alert_id),
    ).fetchone()


def list_workspace_alert_rows(
    conn: Any,
    workspace_id: str,
    *,
    include_dismissed: bool,
    limit: int,
) -> list[Any]:
    clauses = ["workspace_id = ?"]
    params: list[Any] = [workspace_id]
    if not include_dismissed:
        clauses.append("dismissed_at IS NULL")
    return conn.execute(
        f"""
        {_ALERT_SELECT}
        FROM alerts
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()


def count_alerts(conn: Any, workspace_id: str, *, include_dismissed: bool) -> int:
    clauses = ["workspace_id = ?"]
    params: list[Any] = [workspace_id]
    if not include_dismissed:
        clauses.append("dismissed_at IS NULL")
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM alerts WHERE {' AND '.join(clauses)}",
        params,
    ).fetchone()
    return int(row["n"])


def count_workspace_unread_alerts(conn: Any, workspace_id: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM alerts
        WHERE workspace_id = ? AND dismissed_at IS NULL AND read_at IS NULL
        """,
        (workspace_id,),
    ).fetchone()
    return int(row["n"])


def list_alerts_since_rows(
    conn: Any, workspace_id: str, *, since_created_at: str | None, limit: int
) -> list[Any]:
    if since_created_at:
        return conn.execute(
            f"""
            {_ALERT_SELECT}
            FROM alerts
            WHERE workspace_id = ? AND dismissed_at IS NULL AND created_at > ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (workspace_id, since_created_at, limit),
        ).fetchall()
    return conn.execute(
        f"""
        {_ALERT_SELECT}
        FROM alerts
        WHERE workspace_id = ? AND dismissed_at IS NULL
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()


def dismiss_workspace_alert_row(
    conn: Any, workspace_id: str, alert_id: str, *, dismissed_at: str, read_at: str
) -> None:
    conn.execute(
        """
        UPDATE alerts
        SET dismissed_at = ?, read_at = COALESCE(read_at, ?)
        WHERE workspace_id = ? AND id = ?
        """,
        (dismissed_at, read_at, workspace_id, alert_id),
    )


def dismiss_all_alerts(conn: Any, workspace_id: str, *, dismissed_at: str, read_at: str) -> int:
    cur = conn.execute(
        """
        UPDATE alerts
        SET dismissed_at = ?, read_at = COALESCE(read_at, ?)
        WHERE workspace_id = ? AND dismissed_at IS NULL
        """,
        (dismissed_at, read_at, workspace_id),
    )
    return int(cur.rowcount)


def mark_all_alerts_read(conn: Any, workspace_id: str, *, read_at: str) -> int:
    cur = conn.execute(
        """
        UPDATE alerts
        SET read_at = ?
        WHERE workspace_id = ? AND dismissed_at IS NULL AND read_at IS NULL
        """,
        (read_at, workspace_id),
    )
    return int(cur.rowcount)
