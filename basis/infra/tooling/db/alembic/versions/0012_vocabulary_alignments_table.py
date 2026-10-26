"""Persist vocabulary alignments in SQL (workspace-scoped).

Revision ID: 0012_vocabulary_alignments_table
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0012_vocabulary_alignments_table"
down_revision = "0011_vocabulary_alignment_requires_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary_alignments (
                workspace_id TEXT NOT NULL,
                alignment_id TEXT NOT NULL,
                source_uri TEXT NOT NULL,
                target_uri TEXT NOT NULL,
                relation TEXT NOT NULL,
                source_label TEXT,
                target_label TEXT,
                confidence REAL NOT NULL DEFAULT 1.0,
                provenance TEXT,
                source TEXT,
                reviewer TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, alignment_id)
            )
            """
        )
    else:
        bind.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vocabulary_alignments (
                    workspace_id TEXT NOT NULL,
                    alignment_id TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    target_uri TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    source_label TEXT,
                    target_label TEXT,
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                    provenance TEXT,
                    source TEXT,
                    reviewer TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (workspace_id, alignment_id)
                )
                """
            )
        )


def downgrade() -> None:
    raise RuntimeError("vocabulary_alignments table cannot be downgraded safely")
