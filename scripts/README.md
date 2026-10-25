# Repository scripts (`scripts/`)

Python/Node/shell automation for **CI**, **OpenAPI**, **connectors**, **ops**, and **local dev**.  
**Web** and **desktop** have their own trees: `web/scripts/`, `desktop/scripts/`.

## Layout

| Directory | Purpose | Required for CI / release |
|-----------|---------|---------------------------|
| [`audit/`](./audit/) | Import/layout/MCP–HTTP guards (`audit-*.py`, `audit-web-openapi-paths.mjs`) | **Yes** — `.github/workflows/ci.yml` |
| [`openapi/`](./openapi/) | OpenAPI snapshot + web operationId audit + typegen wrapper | **Yes** — CI `openapi`, `client-types`, contract tests |
| [`connectors/`](./connectors/) | BOCP manifest build + provider validation | **Yes** when changing connector providers / synthesis |
| [`ops/`](./ops/) | SQLite/Postgres backup & restore | **No** — production ops (README, integration test for Postgres restore) |
| [`dev/`](./dev/) | Git pre-push gate, shadcn MCP launcher | **No** — opt-in per clone |
| [`smoke/`](./smoke/) | Manual SSO / BOCP Postgres smokes | **No** — local/staging checks |
| [`docs/`](./docs/) | Local `docs/` rename + Semantica SDK capability map | **No** — `docs/` is gitignored; map is optional local doc |
| [`tools/`](./tools/) | Benchmarks, vector index, one-off backfills | **No** — ad hoc / migration helpers |
| [`archive/`](./archive/) | Completed kb→workspace codemods | **No** — history only |

## Commands you use often

```bash
# OpenAPI snapshots (after HTTP route / handler docstring changes)
uv run python scripts/openapi/generate-openapi-v1.py --data-dir /tmp/basis-openapi-gen
cd web && npm run gen:openapi-types
# or: node scripts/openapi/gen-client-types.mjs

# Connector bundles (after provider YAML / synthesis)
uv run python scripts/connectors/build_connector_manifests.py

# CI-style audits locally (subset)
uv run python scripts/audit/audit-test-naming.py
uv run lint-imports --config importlinter.ini

# Backups
./scripts/ops/backup_basis_data.sh
./scripts/ops/backup_basis_postgres.sh

# Pre-push (once: ./scripts/dev/setup-git-hooks.sh)
./scripts/dev/pre-push-check.sh
```

## Archive / optional scripts

- **`archive/kb-rename-migrations/`** — one-time 2024–2025 renames; do not run on current tree.
- **`archive/dev-seeds/seed_workspace_108dd8a0.py`** — fixed workspace id demo seed for local UI.
- **`tools/backfill_route_docstrings.py`** — rare OpenAPI→handler docstring backfill; run only when intentionally bulk-editing routes.
- **`openapi/gen-client-types.mjs`** — thin wrapper around `web` `npm run gen:openapi-types` (prefer npm from `web/`).

## Adding scripts

Place new files under the matching subdirectory. CI references must be updated in `.github/workflows/ci.yml` and, if applicable, `tests/contract/`. Use `Path(__file__).resolve().parents[2]` for repo root from `scripts/<subdir>/`.
