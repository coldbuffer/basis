# `basis.infra.db`

Storage schema and migration tooling (not domain business logic).

| Path | Role |
| --- | --- |
| `migrations/0001_schema_baseline.sql` | Greenfield baseline DDL (wired into Alembic `0001`) |
| `alembic/versions/` | Revision chain (`0001` … `head`) |
| `alembic_upgrade.py` | Runtime entry: `alembic upgrade head` |
| `sqlite_migrations.py` | SQLite bootstrap helpers (`0001`) |
| `postgres_migrations.py` | PostgreSQL DDL helpers + PG-only steps (`0002`/`0003`) |
| `org_backfill.py` | Idempotent org rows for legacy KBs |

### Revision chain

| Revision | SQLite | PostgreSQL |
| --- | --- | --- |
| `0001_storage_baseline` | Full schema from packaged SQL | Baseline SQL + org backfill |
| `0002_postgres_storage_extras` | no-op | `pg_trgm`, `vector`, search indexes |
| `0003_pg_workspace_org_id` | no-op | `workspaces.organization_id` repair |

New changes: add **`0004_*.py`** (and update `down_revision`). Keep each revision id **≤ 32 characters** (Alembic default `alembic_version.version_num` width; Postgres installs widen to 64 on migrate). Avoid editing `0001_schema_baseline.sql` except for greenfield baseline resets.

**Config (single source of truth)**

| Priority | Source | SQLite default |
| --- | --- | --- |
| 1 | `BASIS_DATABASE_URL` | `sqlite:///…` or `postgresql://…` |
| 2 | `BASIS_DATA_DIR` + `basis.db` | `./data/basis.db` when env unset |

`alembic.ini` → `sqlalchemy.url` is only the CLI fallback when `BASIS_DATABASE_URL` is unset and you run from repo root with `BASIS_DATA_DIR=data`.

**Apply schema**

Runtime: `basis.infra.runtime.database` calls `upgrade_sqlite_file` / `upgrade_postgres_engine` on open.

Manual (load `.env` so `BASIS_DATABASE_URL` is visible to `alembic/env.py`). Use `python -m alembic` — `uv run alembic` does not resolve the venv console script in this project:

```bash
uv run python -m alembic -c alembic.ini upgrade head
uv run python -m alembic -c alembic.ini current
```

**Add a revision**

```bash
uv run python -m alembic -c alembic.ini revision -m "short_description"
# edit basis/infra/db/alembic/versions/<rev>_short_description.py
uv run pytest -q tests/integration/test_migrations.py
```

Postgres-only steps: return early when `op.get_bind().dialect.name != "postgresql"` (see `0002` / `0003`).
