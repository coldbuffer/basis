"""Drop connector_connections.connection_name; PK is (workspace, service, scope, subject).

Revision ID: 0004_drop_connection_name
"""

from __future__ import annotations

from alembic import op

from basis.infra.db.connector_vault_migrations import drop_connector_connection_name

revision = "0004_drop_connection_name"
down_revision = "0003_pg_workspace_org_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    drop_connector_connection_name(bind)


def downgrade() -> None:
    raise RuntimeError("connector connection_name removal cannot be downgraded")
