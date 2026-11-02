"""Workspace scope guards — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any

from basis.services.errors import AdminError

_ROW_TABLES = frozenset({"entities", "chunks", "documents", "document_versions"})


def assert_workspace_exists(conn: Any, workspace_id: str) -> None:
    row = conn.execute(
        "SELECT id FROM workspaces WHERE id = ?", (workspace_id,)
    ).fetchone()
    if row is None:
        raise AdminError(404, "not_found", "工作区不存在")


def assert_row_in_workspace(conn: Any, table: str, row_id: str, workspace_id: str) -> None:
    if table not in _ROW_TABLES:
        raise ValueError(f"unsupported table guard: {table}")
    row = conn.execute(f"SELECT workspace_id FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise AdminError(404, "not_found", "记录不存在")
    if row["workspace_id"] != workspace_id:
        raise AdminError(403, "forbidden", "记录不属于该工作区")
