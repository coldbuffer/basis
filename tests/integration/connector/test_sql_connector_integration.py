"""BOCP SQL connector against real PostgreSQL (not SQLite stand-ins).

Requires Postgres per ``tests/test.yaml``. Variables:

  - ``postgres.admin_url`` / ``BASIS_TEST_POSTGRES_URL`` — CI uses ephemeral DB per test; locally, CREATEDB may be
    denied and tests reuse the URL database (unique table names).
  - ``postgres.sql_target_url`` / ``BASIS_TEST_POSTGRES_EXTERNAL_URL`` — optional fixed writable target.
"""

from __future__ import annotations

import uuid
from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from basis.services.connector import ConnectorRuntime
from basis.infra.db.sqlite_migrations import run_migrations


def _setup_workspace_db(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "bocp_sql_integration.db"
    conn = sqlite3.connect(str(db))
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
        VALUES ('kb1', 'KB 1', '', 'private', 'u1', '2026-01-01T00:00:00Z')
        """
    )
    conn.commit()
    return conn


def _connection_fields_from_url(database_url: str) -> tuple[dict, dict]:
    url = make_url(database_url)
    host = url.host or "localhost"
    config: dict = {
        "host": host,
        "database": url.database or "",
    }
    creds = {
        "username": url.username or "",
        "password": url.password or "",
    }
    if url.port is not None:
        config["port"] = int(url.port)
    return config, creds


def _seed_customers_table(database_url: str, *, table_name: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    timestamps = (
        "'2026-01-01 00:00:00+00'",
        "'2026-01-02 00:00:00+00'",
        "'2026-01-03 00:00:00+00'",
    )
    ddl = f"""
        CREATE TABLE {table_name} (
            customer_id VARCHAR(32) PRIMARY KEY,
            company_name TEXT NOT NULL,
            tier VARCHAR(32),
            annual_revenue DOUBLE PRECISION,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """

    with engine.begin() as conn:
        conn.execute(text(ddl))
        conn.execute(
            text(
                f"""
                INSERT INTO {table_name}
                    (customer_id, company_name, tier, annual_revenue, updated_at)
                VALUES
                    ('c1', 'Alpha Inc', 'silver', 100000.0, {timestamps[0]}),
                    ('c2', 'Beta LLC', 'gold', 250000.0, {timestamps[1]}),
                    ('c3', 'Gamma Corp', 'platinum', 900000.0, {timestamps[2]})
                """
            )
        )
    engine.dispose()


def _drop_table(database_url: str, table_name: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
    engine.dispose()


@pytest.mark.integration
def test_sql_connector_postgres_check_discover_read_mutate(
    tmp_path: Path, postgres_sql_target_url: str
) -> None:
    table = f"bocp_customers_{uuid.uuid4().hex[:12]}"
    _seed_customers_table(postgres_sql_target_url, table_name=table)
    conn_cfg, creds = _connection_fields_from_url(postgres_sql_target_url)
    conn_cfg["schema"] = "public"

    conn = _setup_workspace_db(tmp_path)
    try:
        runtime = ConnectorRuntime(conn, vault_secret="test-secret")
        runtime.vault.upsert_connection(
            "kb1",
            "postgres",
            auth_type="database_dsn",
            connection_config=conn_cfg,
            credentials=creds,
        )

        chk = runtime.check_connection("kb1", "postgres")
        assert chk["ok"] is True
        assert chk["dialect"] == "postgresql"

        schema = runtime.discover_schema(
            "kb1",
            "postgres",
            external_table=table,
        )
        assert schema.primary_key == ["customer_id"]
        col_types = {f.name: f.data_type for f in schema.fields}
        assert col_types["customer_id"] == "string"
        assert col_types["annual_revenue"] == "number"

        read_res = runtime.read_stream(
            "kb1",
            "postgres",
            external_table=table,
            primary_key_column="customer_id",
            cursor_column="updated_at",
            cursor_watermark="2026-01-02T00:00:00Z",
        )
        ids = [r["customer_id"] for r in read_res.records]
        assert ids == ["c2", "c3"]

        updated = runtime.mutate_stream(
            "kb1",
            "postgres",
            external_table=table,
            operation="update",
            primary_key_column="customer_id",
            external_pk="c1",
            changes={"tier": "gold", "annual_revenue": 180000.0},
        )
        assert updated["tier"] == "gold"
        assert float(updated["annual_revenue"]) == 180000.0
    finally:
        conn.close()
        _drop_table(postgres_sql_target_url, table)
