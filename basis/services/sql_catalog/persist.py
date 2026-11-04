"""SQL for workspace catalog sources and their latest schema snapshot."""

from __future__ import annotations

import json
from typing import Any


def list_source_rows(conn: Any, workspace_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT
            s.source_id,
            s.display_name,
            s.connection_uri,
            s.config_json,
            s.created_at,
            s.updated_at,
            snap.extracted_at,
            snap.payload_json
        FROM sql_catalog_sources AS s
        LEFT JOIN sql_catalog_snapshots AS snap
          ON snap.workspace_id = s.workspace_id
         AND snap.source_id = s.source_id
        WHERE s.workspace_id = ?
        ORDER BY s.display_name, s.source_id
        """,
        (workspace_id,),
    ).fetchall()


def fetch_source_row(conn: Any, workspace_id: str, source_id: str) -> Any:
    return conn.execute(
        """
        SELECT source_id, display_name, connection_uri, config_json, created_at, updated_at
        FROM sql_catalog_sources
        WHERE workspace_id = ? AND source_id = ?
        """,
        (workspace_id, source_id),
    ).fetchone()


def upsert_source_row(
    conn: Any,
    *,
    workspace_id: str,
    source_id: str,
    display_name: str,
    connection_uri: str,
    config_json: str,
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO sql_catalog_sources (
            workspace_id, source_id, display_name, connection_uri, config_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, source_id) DO UPDATE SET
            display_name = excluded.display_name,
            connection_uri = excluded.connection_uri,
            config_json = excluded.config_json,
            updated_at = excluded.updated_at
        """,
        (
            workspace_id,
            source_id,
            display_name,
            connection_uri,
            config_json,
            created_at,
            updated_at,
        ),
    )


def delete_source_row(conn: Any, workspace_id: str, source_id: str) -> None:
    conn.execute(
        "DELETE FROM sql_catalog_snapshots WHERE workspace_id = ? AND source_id = ?",
        (workspace_id, source_id),
    )
    conn.execute(
        "DELETE FROM sql_catalog_sources WHERE workspace_id = ? AND source_id = ?",
        (workspace_id, source_id),
    )


def upsert_snapshot_row(
    conn: Any,
    *,
    workspace_id: str,
    source_id: str,
    extracted_at: str,
    database_name: str,
    dialect: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO sql_catalog_snapshots (
            workspace_id, source_id, extracted_at, database_name, dialect, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, source_id) DO UPDATE SET
            extracted_at = excluded.extracted_at,
            database_name = excluded.database_name,
            dialect = excluded.dialect,
            payload_json = excluded.payload_json
        """,
        (
            workspace_id,
            source_id,
            extracted_at,
            database_name,
            dialect,
            json.dumps(payload, ensure_ascii=False),
        ),
    )


def fetch_snapshot_row(conn: Any, workspace_id: str, source_id: str) -> Any:
    return conn.execute(
        """
        SELECT source_id, extracted_at, database_name, dialect, payload_json
        FROM sql_catalog_snapshots
        WHERE workspace_id = ? AND source_id = ?
        """,
        (workspace_id, source_id),
    ).fetchone()
