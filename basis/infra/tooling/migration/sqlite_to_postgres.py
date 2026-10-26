"""Offline canonical-data migration from SQLite to PostgreSQL."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.engine import Engine

from basis.infra.tooling.db.alembic_upgrade import upgrade_postgres_engine

_EXCLUDED_PREFIXES = ("chunks_fts", "sqlite_", "alembic_")
_EXCLUDED_TABLES = {
    "schema_migrations",
    "chunk_vectors",
    "vector_manifests",
}


def _canonical_tables(source: Engine, target: Engine) -> tuple[MetaData, list[str]]:
    source_meta = MetaData()
    target_meta = MetaData()
    source_meta.reflect(bind=source)
    target_meta.reflect(bind=target)
    names = sorted(
        name
        for name in source_meta.tables
        if name in target_meta.tables
        and name not in _EXCLUDED_TABLES
        and not name.startswith(_EXCLUDED_PREFIXES)
    )
    return target_meta, names


def _chunk_hash(engine: Engine) -> str:
    digest = hashlib.sha256()
    with engine.connect() as conn:
        result = conn.exec_driver_sql(
            "SELECT id, text FROM chunks ORDER BY id",
            execution_options={"stream_results": True},
        )
        for chunk_id, chunk_text in result:
            digest.update(str(chunk_id).encode())
            digest.update(b"\0")
            digest.update(str(chunk_text).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def migrate_sqlite_to_postgres(
    sqlite_path: Path,
    postgres_url: str,
    *,
    batch_size: int = 1000,
    replace: bool = False,
) -> dict[str, Any]:
    source = create_engine(f"sqlite:///{sqlite_path.resolve()}")
    target_url = postgres_url.replace("postgresql://", "postgresql+psycopg://", 1)
    target = create_engine(target_url, pool_pre_ping=True)
    try:
        upgrade_postgres_engine(target)
        target_meta, table_names = _canonical_tables(source, target)
        with target.connect() as conn:
            existing = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        if existing and not replace:
            raise RuntimeError(
                "PostgreSQL already contains users; pass --replace to overwrite canonical data"
            )

        counts: dict[str, int] = {}
        quoted = ", ".join(f'"{name}"' for name in table_names)
        with target.begin() as dest:
            # Migration is an administrative operation. Disabling triggers
            # handles cyclic ledger references while the complete snapshot is copied.
            dest.exec_driver_sql("SET LOCAL session_replication_role = replica")
            if quoted:
                dest.exec_driver_sql(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
            with source.connect() as src:
                for name in table_names:
                    src_table = MetaData()
                    src_table.reflect(bind=source, only=[name])
                    table = src_table.tables[name]
                    target_table = target_meta.tables[name]
                    result = src.execute(select(table)).mappings()
                    total = 0
                    while True:
                        rows = [dict(row) for row in result.fetchmany(batch_size)]
                        if not rows:
                            break
                        dest.execute(target_table.insert(), rows)
                        total += len(rows)
                    counts[name] = total
            dest.exec_driver_sql(
                """
                UPDATE search_configs
                SET chunk_backend = 'postgres_ledger',
                    vector_backend = 'pgvector',
                    updated_at = CURRENT_TIMESTAMP::text
                """
            )
            dest.exec_driver_sql(
                """
                SELECT setval(
                    pg_get_serial_sequence('audit_log', 'id'),
                    COALESCE((SELECT MAX(id) FROM audit_log), 1),
                    EXISTS (SELECT 1 FROM audit_log)
                )
                """
            )

        source_hash = _chunk_hash(source)
        target_hash = _chunk_hash(target)
        if source_hash != target_hash:
            raise RuntimeError("Chunk hash verification failed after migration")
        with target.connect() as conn:
            for name, expected in counts.items():
                actual = int(
                    conn.execute(
                        text(f'SELECT COUNT(*) FROM "{name}"')
                    ).scalar_one()
                )
                if actual != expected:
                    raise RuntimeError(
                        f"Row-count verification failed for {name}: "
                        f"expected {expected}, got {actual}"
                    )
        return {
            "tables": counts,
            "chunk_hash": source_hash,
            "requires_vector_reindex": True,
        }
    finally:
        source.dispose()
        target.dispose()
