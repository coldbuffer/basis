"""One-off migrations for connector vault schema (connection_name removal)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def _pick_connection_winner(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Prefer connection_name=default, else highest revision."""
    defaults = [r for r in rows if r.get("connection_name") == "default"]
    pool = defaults if defaults else rows
    return max(pool, key=lambda r: int(r.get("revision") or 0))


def _table_exists(conn: Connection, table: str) -> bool:
    dialect = conn.dialect.name
    if dialect == "sqlite":
        row = conn.execute(
            text(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = :table
                LIMIT 1
                """
            ),
            {"table": table},
        ).fetchone()
        return row is not None
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = :table
            LIMIT 1
            """
        ),
        {"table": table},
    ).fetchone()
    return row is not None


def _table_has_column(conn: Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    dialect = conn.dialect.name
    if dialect == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(r[1] == column for r in rows)
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = :table AND column_name = :column
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return row is not None


def drop_connector_connection_name(conn: Connection) -> None:
    """Rebuild connector_connections without connection_name; dedupe legacy rows."""
    if not _table_has_column(conn, "connector_connections", "connection_name"):
        _drop_connector_runs_connection_name(conn)
        _strip_connection_name_from_ingest_sources(conn)
        return

    select_sql = """
        SELECT workspace_id, service, connection_name, connection_scope, subject_id,
               auth_type, connection_config_json, value_encrypted, account_profile_json,
               revision, updated_at
        FROM connector_connections
    """
    raw_rows = conn.execute(text(select_sql)).fetchall()
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        item = {
            "workspace_id": row[0],
            "service": row[1],
            "connection_name": row[2],
            "connection_scope": row[3],
            "subject_id": row[4],
            "auth_type": row[5],
            "connection_config_json": row[6],
            "value_encrypted": row[7],
            "account_profile_json": row[8],
            "revision": row[9],
            "updated_at": row[10],
        }
        key = (item["workspace_id"], item["service"], item["connection_scope"], item["subject_id"])
        grouped[key].append(item)

    winners = [_pick_connection_winner(rows) for rows in grouped.values()]

    conn.execute(text("DROP TABLE IF EXISTS connector_connections_new"))
    conn.execute(
        text(
            """
            CREATE TABLE connector_connections_new (
                workspace_id TEXT NOT NULL,
                service TEXT NOT NULL,
                connection_scope TEXT NOT NULL DEFAULT 'workspace',
                subject_id TEXT NOT NULL DEFAULT '',
                auth_type TEXT NOT NULL,
                connection_config_json TEXT NOT NULL DEFAULT '{}',
                value_encrypted TEXT NOT NULL,
                account_profile_json TEXT NOT NULL DEFAULT '{}',
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, service, connection_scope, subject_id)
            )
            """
        )
    )
    for w in winners:
        conn.execute(
            text(
                """
                INSERT INTO connector_connections_new (
                    workspace_id, service, connection_scope, subject_id,
                    auth_type, connection_config_json, value_encrypted,
                    account_profile_json, revision, updated_at
                ) VALUES (
                    :workspace_id, :service, :connection_scope, :subject_id,
                    :auth_type, :connection_config_json, :value_encrypted,
                    :account_profile_json, :revision, :updated_at
                )
                """
            ),
            {
                "workspace_id": w["workspace_id"],
                "service": w["service"],
                "connection_scope": w["connection_scope"],
                "subject_id": w["subject_id"],
                "auth_type": w["auth_type"],
                "connection_config_json": w["connection_config_json"],
                "value_encrypted": w["value_encrypted"],
                "account_profile_json": w["account_profile_json"],
                "revision": w["revision"],
                "updated_at": w["updated_at"],
            },
        )

    conn.execute(text("DROP TABLE connector_connections"))
    if conn.dialect.name == "sqlite":
        conn.execute(text("ALTER TABLE connector_connections_new RENAME TO connector_connections"))
    else:
        conn.execute(text("ALTER TABLE connector_connections_new RENAME TO connector_connections"))

    _drop_connector_runs_connection_name(conn)
    _strip_connection_name_from_ingest_sources(conn)


def _drop_connector_runs_connection_name(conn: Connection) -> None:
    if not _table_has_column(conn, "connector_runs", "connection_name"):
        return
    conn.execute(text("DROP TABLE IF EXISTS connector_runs_new"))
    conn.execute(
        text(
            """
            CREATE TABLE connector_runs_new (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                service TEXT NOT NULL,
                operation_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                ok INTEGER NOT NULL,
                value_json TEXT NOT NULL
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO connector_runs_new (
                id, workspace_id, service, operation_kind, target_id,
                started_at, completed_at, ok, value_json
            )
            SELECT id, workspace_id, service, operation_kind, target_id,
                   started_at, completed_at, ok, value_json
            FROM connector_runs
            """
        )
    )
    conn.execute(text("DROP INDEX IF EXISTS idx_connector_runs_started"))
    conn.execute(text("DROP TABLE connector_runs"))
    if conn.dialect.name == "sqlite":
        conn.execute(text("ALTER TABLE connector_runs_new RENAME TO connector_runs"))
    else:
        conn.execute(text("ALTER TABLE connector_runs_new RENAME TO connector_runs"))
    conn.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_connector_runs_started
            ON connector_runs(workspace_id, started_at DESC)
            """
        )
    )


def _strip_connection_name_from_ingest_sources(conn: Connection) -> None:
    if not _table_exists(conn, "ingest_sources"):
        return
    if not _table_has_column(conn, "ingest_sources", "config_json"):
        return

    has_workspace_id = _table_has_column(conn, "ingest_sources", "workspace_id")
    has_kind = _table_has_column(conn, "ingest_sources", "kind")
    has_deleted_at = _table_has_column(conn, "ingest_sources", "deleted_at")

    select_cols = ["id", "config_json"]
    if has_workspace_id:
        select_cols = ["id", "workspace_id", "config_json"]

    where_parts: list[str] = []
    if has_kind:
        where_parts.append("kind = 'connector'")
    if has_deleted_at:
        where_parts.append("deleted_at IS NULL")
    where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""

    rows = conn.execute(
        text(f"SELECT {', '.join(select_cols)} FROM ingest_sources{where_sql}")
    ).fetchall()
    for row in rows:
        if has_workspace_id:
            source_id, workspace_id, config_raw = row[0], row[1], row[2]
        else:
            source_id, config_raw = row[0], row[1]
            workspace_id = None
        try:
            cfg = json.loads(config_raw) if config_raw else {}
        except json.JSONDecodeError:
            continue
        if not isinstance(cfg, dict) or "connection_name" not in cfg:
            continue
        cfg.pop("connection_name", None)
        payload = {
            "config_json": json.dumps(cfg, ensure_ascii=False),
            "source_id": source_id,
        }
        if has_workspace_id and workspace_id is not None:
            conn.execute(
                text(
                    """
                    UPDATE ingest_sources
                    SET config_json = :config_json
                    WHERE workspace_id = :workspace_id AND id = :source_id
                    """
                ),
                {**payload, "workspace_id": workspace_id},
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE ingest_sources
                    SET config_json = :config_json
                    WHERE id = :source_id
                    """
                ),
                payload,
            )
