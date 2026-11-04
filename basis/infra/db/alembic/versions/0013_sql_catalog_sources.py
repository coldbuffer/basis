"""Persist SQL catalog sources and the latest schema snapshot."""

from __future__ import annotations

from alembic import op

revision = "0013_sql_catalog_sources"
down_revision = "0012_vocabulary_alignments_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sql_catalog_sources (
            workspace_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            connection_uri TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, source_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sql_catalog_snapshots (
            workspace_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            database_name TEXT NOT NULL,
            dialect TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (workspace_id, source_id)
        )
        """
    )


def downgrade() -> None:
    raise RuntimeError("sql catalog tables cannot be downgraded safely")
