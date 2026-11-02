"""Alembic version table repairs (revision id renames, PostgreSQL column width)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

# Alembic defaults to ``version_num VARCHAR(32)``; keep revision ids ≤32 or widen below.
_LEGACY_REVISION_IDS: dict[str, str] = {
    "0003_postgres_workspace_org_column": "0003_pg_workspace_org_id",
}


def prepare_alembic_connection(conn: Any) -> None:
    _repair_legacy_revision_ids(conn)
    if conn.dialect.name == "postgresql":
        _ensure_alembic_version_num_width(conn)


def _repair_legacy_revision_ids(conn: Any) -> None:
    if not _table_exists(conn, "alembic_version"):
        return
    row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
    if not row:
        return
    current = row[0]
    replacement = _LEGACY_REVISION_IDS.get(current)
    if not replacement:
        return
    conn.execute(
        text(
            "UPDATE alembic_version SET version_num = :new WHERE version_num = :old"
        ),
        {"new": replacement, "old": current},
    )


def _ensure_alembic_version_num_width(conn: Any, *, min_chars: int = 64) -> None:
    if not _table_exists(conn, "alembic_version"):
        return
    row = conn.execute(
        text(
            """
            SELECT character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'alembic_version'
              AND column_name = 'version_num'
            """
        )
    ).fetchone()
    if not row:
        return
    max_len = row[0]
    if max_len is not None and max_len >= min_chars:
        return
    conn.execute(
        text(
            f"ALTER TABLE alembic_version "
            f"ALTER COLUMN version_num TYPE VARCHAR({min_chars})"
        )
    )


def _table_exists(conn: Any, name: str) -> bool:
    if conn.dialect.name == "postgresql":
        row = conn.execute(
            text("SELECT to_regclass(:q) IS NOT NULL"),
            {"q": f"public.{name}"},
        ).scalar()
        return bool(row)
    row = conn.execute(
        text(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :name LIMIT 1"
        ),
        {"name": name},
    ).fetchone()
    return row is not None
