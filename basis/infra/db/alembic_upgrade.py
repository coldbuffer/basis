"""Apply schema revisions via Alembic (canonical entry for runtime and CLI)."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.engine import Engine

_DB_ROOT = Path(__file__).resolve().parent
_ALEMBIC_SCRIPTS = _DB_ROOT / "alembic"
_REPO_ROOT = _DB_ROOT.parents[3]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


def _alembic_config(sqlalchemy_url: str):
    from alembic.config import Config

    root = str(_REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    if _ALEMBIC_INI.is_file():
        cfg = Config(str(_ALEMBIC_INI))
    else:
        cfg = Config()
        cfg.set_main_option("script_location", str(_ALEMBIC_SCRIPTS))
    cfg.set_main_option("sqlalchemy.url", sqlalchemy_url.replace("%", "%%"))
    # Tells ``alembic/env.py`` not to replace this URL with ``BASIS_DATABASE_URL``.
    cfg.attributes["basis_sqlalchemy_url_locked"] = True
    return cfg


def upgrade_head(*, sqlalchemy_url: str | None = None, engine: Engine | None = None) -> None:
    """Run ``alembic upgrade head`` for the given URL or engine."""
    from alembic import command

    if engine is not None:
        sqlalchemy_url = str(engine.url)
    if not sqlalchemy_url:
        raise ValueError("sqlalchemy_url or engine is required")
    cfg = _alembic_config(sqlalchemy_url)
    if engine is not None:
        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
        return
    command.upgrade(cfg, "head")


def upgrade_sqlite_file(db_path: Path) -> None:
    path = db_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    upgrade_head(sqlalchemy_url=f"sqlite:///{path}")


def alembic_head_revision() -> str:
    """Current head revision id (for tests and tooling)."""
    from alembic.script import ScriptDirectory

    cfg = _alembic_config("sqlite:///:memory:")
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if not head:
        raise RuntimeError("Alembic script directory has no head revision")
    return head


def upgrade_postgres_engine(engine: Engine) -> None:
    from basis.infra.db.postgres_migrations import repair_workspace_organization_id_column

    upgrade_head(engine=engine)
    # Best-effort when migration user is not table owner (see revision 0003).
    repair_workspace_organization_id_column(engine)


def sqlite_path_from_connection(conn) -> Path | None:
    """Best-effort file path for a SQLite connection (``None`` for ``:memory:``)."""
    import sqlite3

    if not isinstance(conn, sqlite3.Connection):
        return None
    row = conn.execute("PRAGMA database_list").fetchone()
    if not row:
        return None
    file_path = row[2]
    if not file_path:
        return None
    return Path(file_path)
