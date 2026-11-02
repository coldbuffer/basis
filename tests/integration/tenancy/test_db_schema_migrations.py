import sqlite3
from pathlib import Path

import pytest

from basis.services.tenancy.admin.store import AdminStore
from basis.infra.db.alembic_upgrade import alembic_head_revision, upgrade_sqlite_file
from basis.infra.db.sqlite_migrations import (
    MigrationError,
    assert_desktop_sqlite_compatible,
    ensure_sqlite_schema,
    load_migrations,
    run_migrations,
    sqlite_schema_is_initialized,
)


def _legacy_baseline_only(db_path: Path) -> None:
    """Minimal admin tables without the knowledge ledger."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            deactivated_at TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE tokens (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            visibility TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO settings(key, value) VALUES ('open_registration', 'true');
        """
    )
    conn.commit()
    conn.close()


def test_fresh_database_applies_baseline_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "basis.db"
    store = AdminStore(db_path)
    assert sqlite_schema_is_initialized(store._conn)
    store.close()

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    }
    conn.close()
    assert "alembic_version" in tables
    assert "documents" in tables
    assert "statements" in tables
    assert "projection_state" in tables
    assert "search_configs" in tables
    assert "chunks_fts" in tables
    assert "connector_policies" in tables
    assert "governance_configs" in tables


def test_schema_bootstrap_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "basis.db"
    conn = sqlite3.connect(db_path)
    ensure_sqlite_schema(conn)
    ensure_sqlite_schema(conn)
    conn.close()
    assert sqlite_schema_is_initialized(sqlite3.connect(db_path))


def test_alembic_upgrade_creates_parent_dir_and_version(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "dir" / "basis.db"
    upgrade_sqlite_file(db_path)
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT version_num FROM alembic_version LIMIT 1"
    ).fetchone()[0] == alembic_head_revision()
    assert sqlite_schema_is_initialized(conn)
    conn.close()


def test_run_migrations_applies_alembic_head(tmp_path: Path) -> None:
    db_path = tmp_path / "basis.db"
    conn = sqlite3.connect(db_path)
    assert run_migrations(conn) == []
    conn.close()
    verify = sqlite3.connect(db_path)
    row = verify.execute(
        "SELECT version_num FROM alembic_version LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == alembic_head_revision()
    verify.close()


def test_partial_admin_database_gets_ledger(tmp_path: Path) -> None:
    db_path = tmp_path / "basis.db"
    _legacy_baseline_only(db_path)

    store = AdminStore(db_path)
    row = store._conn.execute(
        "SELECT value FROM settings WHERE key = 'open_registration'"
    ).fetchone()
    assert row is not None
    assert row[0] == "true"
    assert sqlite_schema_is_initialized(store._conn)
    store.close()


def test_desktop_rejects_legacy_knowledge_bases_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "basis.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE documents (id TEXT PRIMARY KEY);
        CREATE TABLE knowledge_bases (id TEXT PRIMARY KEY);
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("BASIS_DEPLOYMENT_PROFILE", "desktop")
    conn = sqlite3.connect(db_path)
    with pytest.raises(MigrationError, match="knowledge_bases"):
        assert_desktop_sqlite_compatible(conn)
    conn.close()


def test_bootstrap_sql_files_sorted() -> None:
    paths = load_migrations()
    versions = [int(p.name[:4]) for p in paths]
    assert versions == sorted(versions)
    assert versions and versions[0] == 1
    assert paths[0].name == "0001_schema_baseline.sql"


@pytest.mark.integration
def test_postgres_bootstrap_is_idempotent(postgres_url: str) -> None:
    from sqlalchemy import create_engine

    from basis.infra.db.postgres_migrations import bootstrap_postgres_ledger_baseline

    engine = create_engine(postgres_url)
    with engine.begin() as conn:
        bootstrap_postgres_ledger_baseline(conn)
        bootstrap_postgres_ledger_baseline(conn)
