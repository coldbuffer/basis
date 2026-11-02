"""Workspaces and membership persistence."""

from __future__ import annotations

from typing import Any

from basis.services.tenancy.admin.admin_types import utc_now_iso
from basis.services.knowledge.persistence.sql_delete import purge_workspace_ledger_data


def list_workspace_ids(conn: Any) -> list[str]:
    rows = conn.execute("SELECT id FROM workspaces ORDER BY created_at").fetchall()
    return [row["id"] for row in rows]


def fetch_workspace(conn: Any, workspace_id: str) -> Any | None:
    return conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()


def list_all_workspaces(conn: Any) -> list[Any]:
    return conn.execute("SELECT * FROM workspaces ORDER BY created_at").fetchall()


def list_visible_workspaces_for_user(conn: Any, user_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT ws.* FROM workspaces ws
        LEFT JOIN members m ON m.workspace_id = ws.id AND m.user_id = ?
        WHERE ws.visibility = 'open' OR m.user_id IS NOT NULL
        ORDER BY ws.created_at
        """,
        (user_id,),
    ).fetchall()


def insert_workspace(
    conn: Any,
    *,
    workspace_id: str,
    name: str,
    description: str,
    visibility: str,
    created_by: str,
    organization_id: str,
) -> str:
    conn.execute(
        """
        INSERT INTO workspaces(
            id, name, description, visibility, created_by, created_at, organization_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (workspace_id, name, description, visibility, created_by, utc_now_iso(), organization_id),
    )
    return workspace_id


def update_workspace(
    conn: Any,
    workspace_id: str,
    *,
    name: str,
    description: str,
    visibility: str,
) -> None:
    conn.execute(
        """
        UPDATE workspaces
        SET name = ?, description = ?, visibility = ?
        WHERE id = ?
        """,
        (name, description, visibility, workspace_id),
    )


def delete_workspace(conn: Any, workspace_id: str) -> None:
    purge_workspace_ledger_data(conn, workspace_id)
    conn.execute("DELETE FROM members WHERE workspace_id = ?", (workspace_id,))
    conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))


def set_member(
    conn: Any,
    workspace_id: str,
    user_id: str,
    role: str,
    added_by: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO members(workspace_id, user_id, role, added_by, joined_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, user_id) DO UPDATE SET role = excluded.role
        """,
        (workspace_id, user_id, role, added_by, utc_now_iso()),
    )


def member_role(conn: Any, workspace_id: str, user_id: str) -> str | None:
    row = conn.execute(
        "SELECT role FROM members WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, user_id),
    ).fetchone()
    return row["role"] if row else None


def owner_count(conn: Any, workspace_id: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM members WHERE workspace_id = ? AND role = 'owner'",
        (workspace_id,),
    ).fetchone()["n"]


def list_members(conn: Any, workspace_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT m.role, m.joined_at, u.id, u.email, u.display_name
        FROM members m
        JOIN users u ON u.id = m.user_id
        WHERE m.workspace_id = ? AND u.deactivated_at IS NULL
        ORDER BY m.joined_at
        """,
        (workspace_id,),
    ).fetchall()


def remove_member(conn: Any, workspace_id: str, user_id: str) -> None:
    conn.execute(
        "DELETE FROM members WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, user_id),
    )


def workspace_count(conn: Any) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM workspaces").fetchone()
    return int(row["n"]) if row else 0
