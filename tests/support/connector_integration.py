"""Shared helpers for real-service connector integration tests."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from basis.infra.db.sqlite_migrations import run_migrations


def setup_workspace_sqlite(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "basis.db"))
    run_migrations(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        INSERT INTO users (id, email, display_name, password_hash, is_admin, created_at)
        VALUES ('u1', 'u1@example.com', 'User 1', 'hash', 1, '2026-01-01T00:00:00Z')
        """
    )
    conn.execute(
        """
        INSERT INTO workspaces (id, name, description, visibility, created_by, created_at)
        VALUES ('ws1', 'Workspace 1', '', 'private', 'u1', '2026-01-01T00:00:00Z')
        """
    )
    conn.commit()
    return conn


def postgres_connection_payload(database_url: str) -> dict:
    """Workspace connection PUT body for ``postgres`` provider ``database_dsn`` auth."""
    url = make_url(database_url)
    connection_config: dict = {
        "host": url.host or "localhost",
        "database": url.database or "",
        "schema": "public",
    }
    if url.port is not None:
        connection_config["port"] = int(url.port)
    return {
        "auth_type": "database_dsn",
        "connection_config": connection_config,
        "credentials": {
            "username": url.username or "",
            "password": url.password or "",
        },
    }


def seed_postgres_items_table(database_url: str, *, table_name: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE {table_name} (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                f"""
                INSERT INTO {table_name} (id, name, updated_at)
                VALUES ('i1', 'One', '2026-01-01T00:00:00+00')
                """
            )
        )
    engine.dispose()


def drop_postgres_table(database_url: str, table_name: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
    engine.dispose()


def unique_pg_table_name(prefix: str = "bocp_items") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
