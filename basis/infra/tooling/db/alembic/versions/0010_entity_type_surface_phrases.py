"""Add governance_configs.entity_type_surface_phrases_json for entity class mapping.

Revision ID: 0010_entity_type_surface_phrases
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.tooling.db.connector_vault_migrations import _table_has_column

revision = "0010_entity_type_surface_phrases"
down_revision = "0009_governance_shacl_turtle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "governance_configs", "entity_type_surface_phrases_json"):
        return
    if bind.dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE governance_configs ADD COLUMN entity_type_surface_phrases_json TEXT"
        )
    else:
        bind.execute(
            text(
                "ALTER TABLE governance_configs ADD COLUMN entity_type_surface_phrases_json TEXT"
            )
        )


def downgrade() -> None:
    raise RuntimeError(
        "governance_configs.entity_type_surface_phrases_json cannot be downgraded safely"
    )
