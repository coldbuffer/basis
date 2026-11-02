"""Add api_tokens.allowed_operations_json for per-operation grants.

Revision ID: 0005_api_token_allowed_ops
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.db.connector_vault_migrations import _table_has_column

revision = "0005_api_token_allowed_ops"
down_revision = "0004_drop_connection_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "api_tokens", "allowed_operations_json"):
        return
    if bind.dialect.name == "sqlite":
        op.execute("ALTER TABLE api_tokens ADD COLUMN allowed_operations_json TEXT")
    else:
        bind.execute(
            text("ALTER TABLE api_tokens ADD COLUMN allowed_operations_json TEXT")
        )


def downgrade() -> None:
    raise RuntimeError("api_tokens.allowed_operations_json cannot be downgraded safely")
