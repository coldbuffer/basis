"""Add governance_configs.governance_ontology_uri for Hub SHACL scans.

Revision ID: 0006_governance_ontology_uri
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.tooling.db.connector_vault_migrations import _table_has_column

revision = "0006_governance_ontology_uri"
down_revision = "0005_api_token_allowed_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "governance_configs", "governance_ontology_uri"):
        return
    if bind.dialect.name == "sqlite":
        op.execute("ALTER TABLE governance_configs ADD COLUMN governance_ontology_uri TEXT")
    else:
        bind.execute(text("ALTER TABLE governance_configs ADD COLUMN governance_ontology_uri TEXT"))


def downgrade() -> None:
    raise RuntimeError("governance_configs.governance_ontology_uri cannot be downgraded safely")
