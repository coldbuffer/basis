"""SQLite schema bootstrap SQL (invoked from Alembic revision ``0001_storage_baseline``)."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

_MIGRATION_NAME = re.compile(r"^(\d+)_.+\.sql$")

_LEDGER_SENTINEL_TABLE = "documents"


class MigrationError(Exception):
    """Schema bootstrap failed."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def package_migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _bootstrap_sql_files() -> list[Path]:
    root = package_migrations_dir()
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.glob("0001_*.sql"):
        if _MIGRATION_NAME.match(path.name):
            files.append(path)
    files.sort(key=lambda p: int(p.name[:4]))
    return files


def sqlite_schema_is_initialized(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (_LEDGER_SENTINEL_TABLE,),
    ).fetchone()
    return row is not None


def assert_desktop_sqlite_compatible(conn: sqlite3.Connection) -> None:
    """Fail fast when ``~/.basis/basis.db`` predates the workspace storage model."""
    profile = os.environ.get("BASIS_DEPLOYMENT_PROFILE", "").strip().lower()
    if profile != "desktop":
        return
    if not sqlite_schema_is_initialized(conn):
        return
    has_workspaces = conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'workspaces'
        LIMIT 1
        """,
    ).fetchone()
    if has_workspaces:
        return
    legacy_kb = conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'knowledge_bases'
        LIMIT 1
        """,
    ).fetchone()
    if legacy_kb:
        raise MigrationError(
            "Desktop cannot open this database: it uses the old knowledge_bases schema. "
            "Quit Basis, back up ~/.basis, remove basis.db (or move the folder aside), "
            "then restart to create a fresh desktop database."
        )
    raise MigrationError(
        "Desktop cannot open this database: the workspaces table is missing "
        "(schema is incomplete or from an incompatible build). "
        "Back up ~/.basis, remove basis.db, and restart."
    )


def ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Run packaged ``*.sql`` once when the ledger tables are absent."""
    conn.execute("PRAGMA foreign_keys = ON")
    if sqlite_schema_is_initialized(conn):
        from basis.infra.db.org_backfill import ensure_organization_backfill

        ensure_organization_backfill(conn)
        return

    files = _bootstrap_sql_files()
    if not files:
        raise MigrationError("No schema SQL files found")

    try:
        for path in files:
            conn.executescript(path.read_text(encoding="utf-8"))
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise MigrationError(f"Failed applying schema ({path.name}): {exc}") from exc

    from basis.infra.db.org_backfill import ensure_organization_backfill

    ensure_organization_backfill(conn)


def run_migrations(conn: sqlite3.Connection) -> list[int]:
    """Test/tooling helper: Alembic head for file DBs; ``:memory:`` uses ``ensure_sqlite_schema``."""
    from basis.infra.db.alembic_upgrade import sqlite_path_from_connection, upgrade_sqlite_file

    db_path = sqlite_path_from_connection(conn)
    if db_path is not None:
        upgrade_sqlite_file(db_path)
        return []
    ensure_sqlite_schema(conn)
    return []


def load_migrations() -> list[Path]:
    """Return ordered bootstrap SQL paths (for tests and tooling)."""
    return _bootstrap_sql_files()
