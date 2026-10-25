"""Add governance_configs.conflict_scan_mode (shacl_only | hybrid).

Revision ID: 0007_conflict_scan_mode
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.tooling.db.connector_vault_migrations import _table_has_column

revision = "0007_conflict_scan_mode"
down_revision = "0006_governance_ontology_uri"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "governance_configs", "conflict_scan_mode"):
        return
    if bind.dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE governance_configs "
            "ADD COLUMN conflict_scan_mode TEXT NOT NULL DEFAULT 'shacl_only'"
        )
    else:
        bind.execute(
            text(
                "ALTER TABLE governance_configs "
                "ADD COLUMN conflict_scan_mode TEXT NOT NULL DEFAULT 'shacl_only'"
            )
        )


def downgrade() -> None:
    raise RuntimeError("governance_configs.conflict_scan_mode cannot be downgraded safely")
