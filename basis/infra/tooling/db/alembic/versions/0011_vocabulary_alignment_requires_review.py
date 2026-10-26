"""Add governance_configs.vocabulary_alignment_requires_review (L1 publish gate).

Revision ID: 0011_vocabulary_alignment_requires_review
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

from basis.infra.tooling.db.connector_vault_migrations import _table_has_column

revision = "0011_vocabulary_alignment_requires_review"
down_revision = "0010_entity_type_surface_phrases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if _table_has_column(bind, "governance_configs", "vocabulary_alignment_requires_review"):
        return
    if bind.dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE governance_configs "
            "ADD COLUMN vocabulary_alignment_requires_review INTEGER NOT NULL DEFAULT 0"
        )
    else:
        bind.execute(
            text(
                "ALTER TABLE governance_configs "
                "ADD COLUMN vocabulary_alignment_requires_review BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )


def downgrade() -> None:
    raise RuntimeError(
        "governance_configs.vocabulary_alignment_requires_review cannot be downgraded safely"
    )
