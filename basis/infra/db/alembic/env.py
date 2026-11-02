from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def _load_project_dotenv() -> None:
    """CLI migrations: pick up repo ``.env`` when ``BASIS_DATABASE_URL`` is not exported."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parents[4]
    dotenv_path = root / ".env"
    if dotenv_path.is_file():
        load_dotenv(dotenv_path, override=False)


_load_project_dotenv()

database_url = os.environ.get("BASIS_DATABASE_URL")
if database_url and not config.attributes.get("basis_sqlalchemy_url_locked"):
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Imperative revisions (SQL baseline + PG helpers); no autogenerate metadata.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from basis.infra.db.alembic_compat import prepare_alembic_connection

    injected = config.attributes.get("connection")
    if injected is not None:
        context.configure(connection=injected, target_metadata=target_metadata)
        with context.begin_transaction():
            prepare_alembic_connection(injected)
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            prepare_alembic_connection(connection)
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
