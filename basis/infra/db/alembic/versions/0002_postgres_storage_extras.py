"""PostgreSQL extensions, trigram/vector indexes (no-op on SQLite).

Revision ID: 0002_postgres_storage_extras
"""

from __future__ import annotations

from alembic import op

from basis.infra.db.postgres_migrations import apply_postgres_storage_extras

revision = "0002_postgres_storage_extras"
down_revision = "0001_storage_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    apply_postgres_storage_extras(bind)


def downgrade() -> None:
    raise RuntimeError("Postgres storage extras cannot be downgraded safely")
