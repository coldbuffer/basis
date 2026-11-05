"""Organization CAS server URL for ticket-based SSO."""

from __future__ import annotations

from alembic import op

revision = "0014_org_cas_config"
down_revision = "0013_sql_catalog_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_cas_configs (
            organization_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
            server_url TEXT NOT NULL,
            email_attribute TEXT NOT NULL DEFAULT 'email',
            email_domains_json TEXT NOT NULL DEFAULT '[]',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    raise RuntimeError("org_cas_configs cannot be downgraded safely")
