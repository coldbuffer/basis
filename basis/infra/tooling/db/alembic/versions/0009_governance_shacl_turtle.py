"""Add governance_configs.governance_shacl_turtle for persisted Hub SHACL.

Revision ID: 0009_governance_shacl_turtle
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.tooling.db.connector_vault_migrations import _table_has_column

revision = "0009_governance_shacl_turtle"
down_revision = "0008_drop_conflict_scan_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "governance_configs", "governance_shacl_turtle"):
        return
    if bind.dialect.name == "sqlite":
        op.execute("ALTER TABLE governance_configs ADD COLUMN governance_shacl_turtle TEXT")
    else:
        bind.execute(text("ALTER TABLE governance_configs ADD COLUMN governance_shacl_turtle TEXT"))


def downgrade() -> None:
    raise RuntimeError("governance_configs.governance_shacl_turtle cannot be downgraded safely")
