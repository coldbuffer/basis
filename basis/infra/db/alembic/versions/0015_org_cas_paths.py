"""Configurable CAS login and ticket-validation paths."""

from __future__ import annotations

from alembic import op

from basis.infra.db.connector_vault_migrations import _table_has_column

revision = "0015_org_cas_paths"
down_revision = "0014_org_cas_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_has_column(bind, "org_cas_configs", "login_path"):
        op.execute(
            "ALTER TABLE org_cas_configs ADD COLUMN login_path TEXT NOT NULL DEFAULT '/login'"
        )
    if not _table_has_column(bind, "org_cas_configs", "validate_path"):
        op.execute(
            "ALTER TABLE org_cas_configs "
            "ADD COLUMN validate_path TEXT NOT NULL DEFAULT '/serviceValidate'"
        )


def downgrade() -> None:
    raise RuntimeError("org_cas_configs login_path cannot be downgraded safely")
