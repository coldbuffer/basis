"""Basis storage baseline for SQLite and PostgreSQL.

Revision ID: 0001_storage_baseline
"""

from alembic import op

from basis.infra.db.postgres_migrations import bootstrap_postgres_ledger_baseline
from basis.infra.db.sqlite_migrations import ensure_sqlite_schema

revision = "0001_storage_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        raw = bind.connection.driver_connection
        ensure_sqlite_schema(raw)
    else:
        bootstrap_postgres_ledger_baseline(bind)


def downgrade() -> None:
    raise RuntimeError("The canonical Basis baseline cannot be downgraded destructively")
