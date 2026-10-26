"""Hard-delete all ledger rows for one workspace (`workspace_id`) before removing the admin row."""

from __future__ import annotations

from typing import Any


def _delete_workspace_rows(conn: Any, table: str, workspace_id: str) -> None:
    conn.execute(f"DELETE FROM {table} WHERE workspace_id = ?", (workspace_id,))


def _null_workspace_supersedes(conn: Any, table: str, workspace_id: str) -> None:
    conn.execute(f"UPDATE {table} SET supersedes_id = NULL WHERE workspace_id = ?", (workspace_id,))


def purge_workspace_ledger_data(
    conn: Any,
    workspace_id: str,
    *,
    retain_job_ids: tuple[str, ...] = (),
) -> None:
    """Remove workspace-scoped ledger rows so ``workspaces`` can be deleted."""
    from basis.domain.knowledge.persistence.sql_workspace_reset_purge import (
        purge_workspace_reset_data,
    )
    from basis.domain.knowledge.services.workspace_reset_scopes import ALL_RESET_SCOPES

    purge_workspace_reset_data(
        conn,
        workspace_id,
        ALL_RESET_SCOPES,
        retain_job_ids=retain_job_ids,
    )
