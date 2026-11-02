"""PostgreSQL schema bootstrap from the canonical SQLite baseline SQL."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ProgrammingError

_logger = logging.getLogger(__name__)

_LEDGER_SENTINEL_TABLE = "documents"


class PostgresSchemaBootstrapError(RuntimeError):
    """PostgreSQL bootstrap failed (often missing extensions or privileges)."""


def reset_postgres_public_schema(engine: Engine) -> None:
    """Drop and recreate ``public`` (dev only — destroys all data)."""
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        conn.exec_driver_sql("CREATE SCHEMA public")
        conn.exec_driver_sql("GRANT ALL ON SCHEMA public TO PUBLIC")


def _migration_root() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _baseline_path() -> Path:
    matches = sorted(_migration_root().glob("0001_*.sql"))
    if not matches:
        raise RuntimeError("No 0001_* schema baseline SQL found")
    return matches[0]


def _strip_line_comments(sql: str) -> str:
    lines: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]


def _postgresize(sql: str) -> str:
    sql = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "BIGSERIAL PRIMARY KEY",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO\s+(.+?)\s*;",
        r"INSERT INTO \1 ON CONFLICT DO NOTHING;",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return sql


def _pg_extension_installed(conn: Any, name: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = :name LIMIT 1"),
        {"name": name},
    ).fetchone()
    return row is not None


def _ensure_pg_extension(conn: Any, name: str) -> None:
    if _pg_extension_installed(conn, name):
        return
    try:
        conn.exec_driver_sql(f"CREATE EXTENSION IF NOT EXISTS {name}")
    except ProgrammingError as exc:
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)
        msg = str(orig or exc).lower()
        if sqlstate == "42501" or "permission denied" in msg:
            raise PostgresSchemaBootstrapError(
                f"Cannot CREATE EXTENSION {name}: the database role is not allowed to "
                "install extensions (PostgreSQL superuser required).\n\n"
                "Fix (pick one):\n"
                f"  1) As superuser on database basis: CREATE EXTENSION IF NOT EXISTS {name};\n"
                "  2) Docker (docker/compose.postgres.yml): docker compose -f docker/compose.postgres.yml "
                f'exec postgres psql -U basis -d basis -c "CREATE EXTENSION IF NOT EXISTS {name};"\n'
                "     (if that fails, recreate the volume: down -v && up -d — init script installs extensions)\n"
                "  3) Use SQLite locally: unset BASIS_DATABASE_URL"
            ) from exc
        raise


def _fts_and_vector_sql() -> list[str]:
    return [
        """
        CREATE INDEX IF NOT EXISTS chunks_text_trgm
        ON chunks USING gin (text gin_trgm_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS chunks_workspace_created
        ON chunks(workspace_id, created_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS vector_manifests (
            workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
            backend TEXT NOT NULL,
            model_ref TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chunk_vectors (
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
            dimension INTEGER NOT NULL,
            embedding vector NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            model_ref TEXT NOT NULL,
            PRIMARY KEY (workspace_id, chunk_id, dimension)
        ) PARTITION BY LIST (dimension)
        """,
    ]


def _postgres_search_v2_sql() -> list[str]:
    return [
        """
        CREATE INDEX IF NOT EXISTS chunks_text_trgm_gist
        ON chunks USING gist (text gist_trgm_ops)
        """
    ]


def _vector_partition_bootstrap_sql() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS chunk_vectors_d384
        PARTITION OF chunk_vectors FOR VALUES IN (384)
        """,
        """
        CREATE INDEX IF NOT EXISTS chunk_vectors_d384_hnsw_cosine
        ON chunk_vectors_d384
        USING hnsw ((embedding::vector(384)) vector_cosine_ops)
        """,
    ]


def _organizations_table_exists(conn: Any) -> bool:
    row = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'organizations'
            )
            """
        )
    ).scalar()
    return bool(row)


def _workspace_registry_table(conn: Any) -> str | None:
    row = conn.execute(
        text(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'workspaces'
            LIMIT 1
            """
        )
    ).fetchone()
    return str(row[0]) if row else None


def _workspace_table_owner(conn: Any) -> str | None:
    table = _workspace_registry_table(conn)
    if not table:
        return None
    row = conn.execute(
        text(
            """
            SELECT tableowner FROM pg_tables
            WHERE schemaname = 'public' AND tablename = :table
            """
        ),
        {"table": table},
    ).fetchone()
    return str(row[0]) if row else None


def _workspace_organization_id_column_exists(conn: Any) -> bool:
    table = _workspace_registry_table(conn)
    if not table:
        return False
    row = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                  AND column_name = 'organization_id'
            )
            """
        ),
        {"table": table},
    ).scalar()
    return bool(row)


def ensure_workspace_organization_id_column(conn: Any) -> bool:
    if not _organizations_table_exists(conn):
        return True
    if _workspace_organization_id_column_exists(conn):
        return True
    table = _workspace_registry_table(conn)
    if not table:
        return True
    nested = getattr(conn, "begin_nested", None)
    for statement in (
        f"""
        ALTER TABLE {table}
        ADD COLUMN IF NOT EXISTS organization_id TEXT
        REFERENCES organizations(id)
        """,
        f"""
        ALTER TABLE {table}
        ADD COLUMN IF NOT EXISTS organization_id TEXT
        """,
    ):
        try:
            if nested is not None:
                with conn.begin_nested():
                    conn.exec_driver_sql(statement)
            else:
                conn.exec_driver_sql(statement)
        except ProgrammingError:
            continue
        if _workspace_organization_id_column_exists(conn):
            return True
    return _workspace_organization_id_column_exists(conn)


def repair_workspace_organization_id_column(engine: Engine) -> None:
    log = logging.getLogger(__name__)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if ensure_workspace_organization_id_column(conn):
            return
        owner = _workspace_table_owner(conn)
        log.warning(
            "PostgreSQL schema: workspaces.organization_id is still missing "
            "(table owner=%s, connected as migration user). "
            "Run as owner or superuser: "
            "ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS organization_id TEXT;",
            owner or "unknown",
        )


def _exec_sql_best_effort(conn: Any, statement: str, *, skip_owner_errors: bool) -> None:
    try:
        with conn.begin_nested():
            conn.exec_driver_sql(statement)
    except ProgrammingError as exc:
        if not skip_owner_errors:
            raise
        orig = getattr(exc, "orig", None)
        msg = str(orig or exc).lower()
        if "must be owner" in msg or getattr(orig, "sqlstate", None) == "42501":
            return
        raise


def _apply_baseline_sql_to_postgres(conn: Any, source: str) -> None:
    ddl = _postgresize(_strip_line_comments(source))
    for statement in _statements(ddl):
        upper = statement.upper().lstrip()
        if not upper:
            continue
        if "PRAGMA" in upper:
            continue
        if "CHUNKS_FTS" in upper or "USING FTS5" in upper:
            continue
        if upper.startswith("CREATE TRIGGER") and "CHUNKS_FTS" in upper:
            continue
        if upper.startswith("DROP TRIGGER") and "CHUNKS_FTS" in upper:
            continue
        if upper.startswith("INSERT INTO CHUNKS_FTS"):
            continue
        if upper.startswith("ALTER TABLE WORKSPACES ADD COLUMN"):
            _exec_sql_best_effort(
                conn,
                """
                ALTER TABLE workspaces
                ADD COLUMN IF NOT EXISTS organization_id TEXT
                REFERENCES organizations(id)
                """,
                skip_owner_errors=True,
            )
            continue
        conn.exec_driver_sql(statement)


def apply_postgres_storage_extras(conn: Any) -> None:
    _ensure_pg_extension(conn, "pg_trgm")
    _ensure_pg_extension(conn, "vector")
    for statement in _fts_and_vector_sql():
        conn.exec_driver_sql(statement)
    for statement in _postgres_search_v2_sql():
        conn.exec_driver_sql(statement)
    bootstrap = _vector_partition_bootstrap_sql()
    conn.exec_driver_sql(bootstrap[0])
    _exec_sql_best_effort(conn, bootstrap[1], skip_owner_errors=True)


def bootstrap_postgres_ledger_baseline(conn: Any) -> None:
    """Canonical ledger DDL + org backfill (Alembic ``0001``).

    When ``documents`` already exists (legacy installs predating Alembic), skip replaying
    baseline SQL — same guard as ``ensure_sqlite_schema``.
    """
    from basis.infra.db.org_backfill import ensure_organization_backfill_postgres

    if postgres_schema_is_initialized(conn):
        ensure_organization_backfill_postgres(conn)
        return

    baseline_source = _baseline_path().read_text(encoding="utf-8")
    _apply_baseline_sql_to_postgres(conn, baseline_source)
    ensure_organization_backfill_postgres(conn)


def postgres_schema_is_initialized(conn: Any) -> bool:
    row = conn.execute(
        text("SELECT to_regclass('public.documents') IS NOT NULL")
    ).scalar()
    return bool(row)


def run_postgres_migrations(engine: Engine) -> list[int]:
    """Deprecated: use ``alembic_upgrade.upgrade_postgres_engine``. Kept for tooling imports."""
    from basis.infra.db.alembic_upgrade import upgrade_postgres_engine

    upgrade_postgres_engine(engine)
    return []
