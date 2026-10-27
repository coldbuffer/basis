# Agent guide (Basis)

Instructions for AI coding agents working in this repository. Humans can skim this for the same conventions.

## What this repo is

**Basis** — self-hosted knowledge platform: FastAPI backend (`basis` Python package) + React console (`web/`). Evidence ledger is canonical; graph and search are projections. See [README.md](./README.md) and [docs/README.md](./docs/README.md).

| Area | Path | Stack |
|------|------|--------|
| API | `basis/` Python package (layered; see [package-layout.md](./docs/architecture/package-layout.md), [directory rollout](./docs/architecture/directory-optimization-implementation-plan.md)) | Python 3.10+, FastAPI, Semantica SDK |
| Web | `web/` | Vite, React, React Router, Tailwind v4, shadcn |
| Workspace console | `web/src/modules/<segment>/` + `app/shared/workspace/` + `lib/workspace/` | Feature modules; layout frame in `app/shared/workspace/` |

## Before you change code

1. **Scope** — Smallest correct diff. Do not refactor or “improve” unrelated files.
2. **Match existing style** — Naming, imports (`.js` suffix in TS paths), i18n keys, console patterns.
3. **Do not hand-edit** `web/src/components/ui/*` — vendor shadcn only via CLI (see [Web UI](#web-ui-shadcn)).
4. **Commits / PRs** — Only when the user explicitly asks. Never force-push `main`, never skip hooks unless asked.
5. **Secrets** — Do not commit `.env` or credentials.

## Web UI (shadcn)

### `components/` — three roots

| Root | Path | Rules |
|------|------|--------|
| **Vendor** | `web/src/components/ui/*` | **Do not hand-edit.** Update only via `npx shadcn add …` (use `-o` to sync). |
| **Admin** | `web/src/components/admin/*` | `/admin/*` UI only (layout, SSO, access, `admin/models/`, …). |
| **App** | `web/src/components/app/*` | `shared/` (layout, page patterns, `workspace/`) + `marketing/`. |

No files at `components/` root. Full map: [web/README.md](./web/README.md).

#### `app/shared/` (cross-product)

| Path | Use for |
|------|---------|
| `app/shared/primitives/` | PublicIcon, DatePicker, editors, … |
| `app/shared/effects/` | Decorative motion. |
| `app/shared/console/` | DataTable, ConsolePageLayout, EmptyState, … |
| `app/shared/shell/` | Global layout — not `app/shared/workspace/frame/`. |

`app/marketing/` is product-specific; modules may import `app/shared/*` and `ui/*`.

### Imports

- Stock shadcn → `@/components/ui/*`
- Primitives / effects → `@/components/app/shared/primitives/…`, `…/effects/…`
- Console patterns → `@/components/app/shared/console`
- Admin-only blocks → `@/components/admin/*`
- Workspace frame / ledger primitives → `@/components/app/shared/workspace/…`
- Workspace feature routes → `@/modules/<segment>/index.js`, `@/modules/<segment>/pages/…`, `@/modules/<segment>/components/…`, `@/modules/<segment>/i18n/…`

**Direction:** `admin/` and `app/` → `ui/` and `app/shared/*`. Never `ui/` → `app/` or `admin/`.

### Card surfaces

Use `resourceCardSurfaceClass` / `cardElevationClass` from `@/lib/ui-classes/card-surface.js` — never add these exports to `ui/card.tsx`.

### Do not (UI)

- Patch `web/src/components/ui/` for Basis branding or app APIs.
- Add styled raw `<select>` / checkbox in `web/src/modules/` or `web/src/components/admin/`.
- Put cross-product patterns under `app/shared/console/` or `app/shared/workspace/` — not inside `modules/`.
- Reintroduce a `basis-ui/` wrapper layer for styling that belongs in project CSS.

### Syncing shadcn

```bash
cd web && npx shadcn@latest add -y -o <component-names>
```

After sync: `npm run typecheck` — fix **primitives**, **shell**, and imports, not `ui/` source.

### Styling policy

- Prefer design tokens (`border-border`, `text-muted-foreground`) over one-off hex.
- **Project-wide control chrome** (field focus without ring, status badges, console outline buttons) lives in **`web/src/styles.css`** — `data-slot`, `[data-basis-app]`, utilities like `badge-status-success`, `native-select--full`.
- Workspace console layout/chrome: `lib/ui-classes/`; Sigma graph UI in `modules/graph/`, not global CSS.

### Routing (`web/src/routes/`)

`AppRoutes` in `routes/index.tsx` (single route table). Feature UI in `modules/` (workspace segments, `admin-*`, `login`, `home`, `docs`, `swagger`).

### Workspace Explorer layering

1. `web/src/routes/index.tsx` — all `/workspaces/*`, `/admin/*`, and related URLs; modules export route entry `index.tsx` (lazy via `routes/lazy-pages.ts`).
2. `web/src/modules/<segment>/` — `index.tsx` (route entry), `pages/` (screen + glue), `i18n/`, `components/` (required); optional `hooks/`, `lib/`; workspace frame from `app/shared/workspace/frame/`.
3. `web/src/lib/workspace/` — shared client (`ws-http`, `graphStore`, …); import `@/lib/workspace/…` ([README](./web/src/lib/workspace/README.md)).

### Forms and console

- Prefer shadcn **`Form`** + React Hook Form + Zod for dialogs and settings (`@/components/ui/form`).
- List pages: `ConsolePageLayout`, `DataPanel`, `DataTable`, `ToolbarSearch` from `@/components/app/shared/console`.
- Breadcrumbs: shadcn `Breadcrumb` via `PageHeader` / `Crumb[]`.

## Web i18n

- Feature copy: `web/src/modules/<segment>/i18n/{en,zh}.ts` (`export default { … }`); barrel `i18n/index.ts` → `{ default as en, default as zh }`. Namespace = segment (`admin-audit` → `admin_audit`), keys `namespace.area.snake_leaf` ([convention](./web/src/modules/i18n-convention.md)). New module: `npx tsx scripts/refresh-module-i18n-index.mjs`. Product-wide shell/nav/runtime: `i18n/core/{en,zh}.ts` (`shell`, `workspace_nav`, `workspace_runtime`, `common`, `dev`). Aggregator: `i18n/en.ts`, `i18n/zh.ts` + generated `i18n/module-locales.ts`. React: `useI18n()`; `fmt()` from `@/i18n/format.js`. Sidebar labels: `lib/workspace-nav-label.ts`.
- **Do not** hardcode UI copy, inline `locale === 'zh' ? …`, or duplicate inspector/helpers keys. API-keyed maps (`apiErrorCodes`, audit actions, status labels, …): keep en/zh in sync.
- Tables: `t.common.emptyCell` (`—`), `t.common.ellipsis` (`…`).
- After new keys: `cd web && npm run audit:locale && npm run typecheck`.

## Verification

From `web/`:

```bash
npm run typecheck
npm test
npm run build   # when touching build-sensitive code
```

From repo root (API):

```bash
uv run pytest -q   # layout + naming: [tests/README.md](./tests/README.md); `uv run python scripts/audit/audit-test-naming.py`
```

Run relevant checks after substantive edits; say if something was not run.

## Python / API

- Package layout: [package-layout.md](./docs/architecture/package-layout.md) — `interface/`, `application/`, `domain/`, `infra/` (CI: `audit-legacy-package-imports.py`, `audit-mcp-http-decouple.py`, `audit-connector-http-duplication.py`, `audit-knowledge-connector-imports.py`, `audit-knowledge-persistence-stubs.py`, `audit-knowledge-persistence-imports.py`, `audit-http-shared-stubs.py`, `audit-http-mount-v1.py`, `audit-http-mount-workspace.py`, `audit-http-mount-platform.py`, `audit-web-module-cross-ui.py`, `lint-imports`). Web modules: `web/src/modules/README.md` + same cross-UI audit.
- **Application layer (`basis/application/`)**: `kernel/` (`WorkspaceCoreContext`, `CoreError`, workspace gates, search limits); `schema_base.py` (`ExtraAllowedModel` for BC tool schemas); `tool_catalog/` (handlers in `catalog.py`, MCP descriptions in `mcp_metadata.py`, list schemas + `run` in `run.py`); each BC may expose `schemas.py` for tool arg/response Pydantic models; domain packages — `connectors/`, `workspace/`, `graph/`, `knowledge/`, `reasoning/`, `review/` (`operations.py` each; connector HTTP may also call `catalog.py` helpers such as `list_catalog_detailed` where the response shape differs from MCP). **HTTP** routes call BC `operations` directly; **MCP** uses `interface/mcp/dispatch.py` over the same handlers (catalog-owned schemas, not HTTP OpenAPI). Workspace **connector HTTP** (`interface/http/workspace/connectors/`) must import `basis.application.connectors` only (not `domain.connector` orchestration). Operation `{error}` → HTTP status: `interface/http/operation_http.py`.
- **Semantica 线 1：** 新后端逻辑放在 `basis/domain/*`（L3）：`knowledge` · `ontology` · `graph`（`projection/` + `session/` / `reads/` / …）· `connector` · `tenancy`。图域见 `basis/domain/graph/README.md`；本体 Hub 见 `basis/domain/ontology/README.md`。分层见 [package-layout.md](./docs/architecture/package-layout.md)。
- CLI entry: `pyproject.toml` (`basis` → `basis.cli:main`); app factory `basis.interface.http.app:create_app`.
- Schema: Alembic (`alembic.ini`, `basis/infra/tooling/db/alembic/`); new DDL via new revisions (`0004+`); baseline SQL in `migrations/0001_schema_baseline.sql` (`0001`); runtime `alembic_upgrade.py`. See `basis/infra/tooling/db/README.md`.
- Layer imports: `uv run lint-imports --config importlinter.ini` — domain ↛ `interface`/`application`; `application` ↛ `interface` (incl. `interface.http`).
- **HTTP modules** (`basis/interface/http/`): `mount_v1.py` delegates to `platform/mount_platform.py` and `workspace/mount_workspace.py`; platform handlers live under `platform/` (`auth/` + `auth_mount.py`, `settings`, `orgs`, …); workspace root aggregators (`graph.py`, `connectors.py`, …) mount handlers from `workspace/<domain>/`. Cross-cutting code is in `shared/` (deps, middleware, health, OpenAPI serve); root `deps.py` et al. are thin re-exports. `platform_auth.py` is a thin re-export; auth routes mount in `platform/auth_mount.py` (`platform/auth/*`). Do not reintroduce `kb_` or `workspace_` filename prefixes on aggregator filenames.
- Application core: `basis/application/` (`WorkspaceCoreContext`, `tool_catalog.run`). **MCP tools** (~37 static core tools; minimal graph loop + ledger/rules/mappings/reasoning/jobs in [openapi-v1.md §6.1](./docs/architecture/openapi-v1.md)): handlers in `tool_catalog/catalog.py`; MCP descriptions in `tool_catalog/mcp_metadata.py`, `inputSchema` from BC `schemas.py` via `tool_catalog/run.py` (`description_for_tool` / `input_schema_for_tool`); wire-up + manifest connector tools in `interface/mcp/dispatch.py` and `interface/contract/mcp/`. HTTP OpenAPI is for HTTP clients only (no `x-basis-mcp-tool` on routes). **New static MCP tool:** implement `op_*` in the BC `operations.py`; register `handler` in `tool_catalog/catalog.py`; add `description` in `tool_catalog/mcp_metadata.py`; add Pydantic input (and optional response) in that BC `schemas.py` (`TOOL_INPUT_MODELS`); add HTTP route separately if needed — CI `audit-mcp-http-decouple.py` requires all four key sets to match.
- OpenAPI: served live from `app.openapi()` via `basis.interface.contract.openapi.v1_export` (`/openapi/v1.json`, `/openapi/v1/workspaces.json`, `/openapi/v1/platform.json`). Handler docstrings → `description`. Snapshots in `openapi/*.json`: `scripts/openapi/generate-openapi-v1.py` (CI drift + `web` typegen).
- Prefer existing patterns in route handlers and services; follow pytest style under `tests/integration`, `tests/use_cases`, and `tests/contract` (see [tests/README.md](./tests/README.md)).

## Docs for specific tasks

The **`docs/`** directory is listed in **`.gitignore`** — local working copies only, **not** in the Git repo. Do not `git add` paths under `docs/`. After bulk renames, refresh local docs with `uv run python scripts/docs/apply-docs-workspace-naming.py`. Normative HTTP contract for CI and clients: **`openapi/basis-v1*.json`**, live **`/openapi/v1.json`**, and in-repo READMEs under `basis/`, `web/`, etc.

| Task | Read |
|------|------|
| Web structure / workspace modules | [web/README.md](./web/README.md) |
| Explorer layout | [web/src/modules/README.md](./web/src/modules/README.md), [web/src/routes/README.md](./web/src/routes/README.md), [web/src/components/app/shared/README.md](./web/src/components/app/shared/README.md), [web/src/lib/workspace/README.md](./web/src/lib/workspace/README.md) |
| Docs (features / progress / architecture) | [docs/README.md](./docs/README.md) |
| OpenAPI v1 (platform + workspace surfaces) | [docs/architecture/openapi-v1.md](./docs/architecture/openapi-v1.md), live `/openapi/v1.json`; snapshots `openapi/basis-v1*.json` |
| Feature list / progress | [docs/features.md](./docs/features.md) (F-* spec), [docs/progress.md](./docs/progress.md) (status: §0.1 done, §0.2 API baseline, §3.1 UX / §3.2 e2e gaps) |
| Connector roadmap (dual-mode → OC → Airbyte) | [docs/connector/ROADMAP.md](./docs/connector/ROADMAP.md); detail under [docs/connector/README.md](./docs/connector/README.md) |
| Web OpenAPI transport | `web/src/lib/openapi/` (`transport.ts` + generated `schema.d.ts`); app helpers in `web/src/lib/openapi/client.ts` |
| Web ↔ operationId audit | [openapi/web-openapi-operation-audit.md](./openapi/web-openapi-operation-audit.md) — `scripts/openapi/audit-web-operation-ids.py` |
| HTTP in web | Typed: `lib/openapi/client.ts` (`openApi*` / `workspaceOpenApi*` / `publicOpenApi*`); stream/multipart: `lib/session/basis-session-fetch.ts`; paths: `lib/workspace/api-path.ts`, `lib/nav/nav-config.ts` (`workspacePath`), `lib/openapi/api-v1-path.ts`; E2E `tests/e2e/api-v1-path.ts` (`e2eWorkspaceApiPath`) |

**Naming:** Normative HTTP = **live export** at `/openapi/v1.json` (same as `app.openapi()` + Basis annotations); committed snapshots in **`openapi/basis-v1.json`**. `basis/application/` = server operations (OpenAPI + MCP call this). **semantica** = in-process runtime. **Application HTTP client** = web `lib/openapi/` transport (OpenAPI-generated types; not a published SDK). Server exposes **only OpenAPI + MCP** to clients.

## Out of scope unless asked

- Mass renames, directory moves, or syncing all shadcn components without a request.
- Committing drive-by README changes unrelated to the task.
- Committing anything under **`docs/`** (gitignored by design).
- Editing generated or vendor trees except through documented sync commands.
