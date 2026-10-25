"""Drop governance_configs.conflict_scan_mode; retire legacy conflict artifacts.

Revision ID: 0008_drop_conflict_scan_mode
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.tooling.db.connector_vault_migrations import _table_has_column

revision = "0008_drop_conflict_scan_mode"
down_revision = "0007_conflict_scan_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "governance_configs", "conflict_scan_mode"):
        if bind.dialect.name == "sqlite":
            op.execute("ALTER TABLE governance_configs DROP COLUMN conflict_scan_mode")
        else:
            bind.execute(
                text("ALTER TABLE governance_configs DROP COLUMN conflict_scan_mode")
            )

    bind.execute(
        text(
            """
            UPDATE review_items
            SET kind = 'shacl_violation'
            WHERE kind = 'statement_conflict'
            """
        )
    )
    bind.execute(
        text("DELETE FROM alerts WHERE kind = 'governance.statement_conflict'")
    )


def downgrade() -> None:
    raise RuntimeError("0008_drop_conflict_scan_mode cannot be downgraded safely")
