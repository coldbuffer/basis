# Basis automated tests (non-unit)

Unit tests stay colocated in application code (`web/src/**/*.test.ts`, optional `desktop/**.test.mjs`). Everything else lives under `tests/`.

## Layout

| Path | Layer | Runner |
|------|--------|--------|
| `integration/` | API / service **integration** | `uv run pytest tests/integration` |
| `use_cases/` | **Acceptance** / vertical-slice flows | `uv run pytest tests/use_cases` — [use_cases/README.md](./use_cases/README.md) |
| `contract/` | **Contract** + audit wrappers | `uv run pytest tests/contract` |
| `e2e/` | Browser **E2E** (`specs/`, Playwright package) | `cd tests/e2e && npm ci && CI=1 npm test` — [e2e/README.md](./e2e/README.md) |
| `support/` | Shared pytest helpers (not collected) | imported by tests |
| `conftest.py` | Global pytest fixtures | — |

Runtime E2E hooks used by the API (`is_playwright_e2e_data_dir`, OAuth stub) remain in `basis/infra/tooling/test_support/` because production HTTP imports them.

Structural audits live in `scripts/audit/`; CI runs them alongside pytest. Contract tests in `contract/` invoke OpenAPI audits under `scripts/audit/` and `scripts/openapi/`. See [scripts/README.md](../scripts/README.md).

## Test case planning

Pick the **layer** first (not “one OpenAPI operation = one integration file”):

| Layer | Plan tests when… | Granularity |
|-------|------------------|-------------|
| `contract/` | OpenAPI/MCP drift, snapshots, schemathesis, web `operationId` audits | Spec-wide or audit scripts |
| `integration/` | A **bounded context** (BC) behavior, edge case, or short HTTP chain must hold in-process | One file ≈ one domain theme; one `test_*` ≈ one assertion focus |
| `use_cases/` | A **product journey** crosses several APIs (release gate, vertical smoke) | One `test_uc_<slug>.py`; document in [use_cases/README.md](./use_cases/README.md) |
| `e2e/` | Browser + real dev stack; route smoke / UX | `*.e2e.spec.ts`; matrix in [e2e/README.md](./e2e/README.md) |

**Integration** files are grouped by **backend domain** (`workspace_*`, `graph_*`, `connector_*`, `ontology_*`, …), aligned loosely with `basis/application/` and `basis/domain/` — not by OpenAPI path or tag. Breadth of “every route exists” lives in **contract**; depth of “this rule is correct” lives in **integration**.

Inside `integration/`, a file may use `TestClient`, domain helpers, stores, or MCP — whatever matches the behavior under test. Use `@pytest.mark.integration` when a real external DB or service is required (`uv run pytest -q -m integration`).

**Do not** add pytest that reads sibling monorepo trees. Synthesis merge against upstream catalogs is a dev/release workflow; CI asserts **in-repo** manifests (`providers/*.yaml`), generators, `batches/`, and `executors-index.json` only. Use `tmp_path` / monkeypatch for `BASIS_SYNTHESIS_*` path logic, not a checkout on disk.

## Git pre-push hook

Repo hook (opt-in per clone): `./scripts/dev/setup-git-hooks.sh` sets `core.hooksPath` to `.githooks/`.  
`pre-push` runs `scripts/dev/pre-push-check.sh` (`uv run pytest -q`, then `web` typecheck + unit tests).  
Skip once: `git push --no-verify` or `BASIS_SKIP_PREPUSH=1`.

## Commands

```bash
# All pytest layers
uv run pytest -q

# Optional external DB / GitHub — see tests/test.yaml
uv run pytest -q -m integration

# Web unit tests
cd web && npm test

# Playwright E2E
cd tests/e2e && CI=1 npm test
```

### Optional `@pytest.mark.integration`

Harness settings live in **`tests/test.yaml`** only (pytest, Playwright E2E, and CI). Override the file path with `BASIS_TEST_CONFIG`. **Secrets** (GitHub PAT, etc.): use shell `export` or CI secrets — env wins over YAML; keep tokens out of the committed file.

| YAML key | Env override (optional) | Exercises |
|----------|-------------------------|-----------|
| `postgres.admin_url` | `BASIS_TEST_POSTGRES_URL` | Postgres integration + BOCP SQL connector tests |
| `postgres.sql_target_url` | `BASIS_TEST_POSTGRES_EXTERNAL_URL` | Fixed writable DB for SQL connector tests |
| `e2e` / `e2e_desktop` | `BASIS_E2E_*_PORT`, `BASIS_DEMO_WORKSPACE` | Playwright only (`BASIS_E2E_DESKTOP=1` → `e2e_desktop`) |

Live GitHub (optional): `BASIS_TEST_GITHUB_*` (pytest), `BASIS_E2E_GITHUB_*` (E2E) — **env only**, not in `test.yaml`.

Default `uv run pytest -q` uses SQLite for app tests; `@pytest.mark.integration` Postgres tests **skip** when the configured server is unreachable (no Docker / no CI service).

## File naming (enforced)

CI runs `uv run python scripts/audit/audit-test-naming.py`. New files must match:

| Layer | Pattern | Example |
|-------|---------|---------|
| Integration | `test_<domain>_<behavior>.py` (≥2 segments after `test_`) | `test_workspace_token_grants.py` |
| Use case | `test_uc_<slug>.py` | `test_uc_release_gate.py` |
| Contract | `test_contract_<topic>.py` | `test_contract_openapi_v1_served.py` |
| Unit (web) | `<kebab>.test.ts` sibling of `<kebab>.ts` or `.tsx` | `graph-url-state.test.ts` |
| E2E | `<kebab>.e2e.spec.ts` under `tests/e2e/specs/` | `home.e2e.spec.ts` |

## Adding tests

Checklist for a **new HTTP surface or behavior**:

1. **Contract** — Does OpenAPI/MCP or a CI audit need updating? → `contract/` or `scripts/audit/` / `scripts/openapi/` / `openapi/*.json`.
2. **Integration** — What BC/domain and behavior name? → new or existing `integration/test_<domain>_<behavior>.py`; prefer extending an existing domain file unless the theme is new.
3. **Use case** — Does it close a named product journey? → `use_cases/test_uc_<slug>.py` + README row.
4. **E2E** — Does the console need a primary-route smoke? → `tests/e2e/specs/<feature>.e2e.spec.ts` + e2e README matrix.

Conventions:

- Integration: one assertion focus per `test_*` function; fixtures from `conftest.py` / `support/demo_workspace.py` or file-local `_client`.
- Playwright-only HTTP (`/_e2e/*`, `data/e2e` gating): `test_*_playwright_*_http.py` in `integration/` — not `test_e2e_*.py`; browser tests only under `tests/e2e/`.
- Web UI logic: colocated `*.test.ts` next to source (see naming table above).
