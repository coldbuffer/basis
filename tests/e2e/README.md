# Playwright E2E

End-to-end tests exercise **real browser + API** (`BASIS_DATA_DIR=data/e2e`, `/_e2e/*` seed helpers). They are **not** a full UI regression suite — most behavior is covered by **Vitest** (`web/src/**/*.test.ts`) and **pytest** (`tests/integration`, `tests/contract`, `tests/use_cases`).

Specs: `specs/*.e2e.spec.ts`. Shared helpers: `helpers.ts`, `api-v1-path.ts`, `e2e-admin-session.ts`, …

**Run:** `cd tests/e2e && npm ci && CI=1 npm test` — or from `web/`: `npm run test:e2e` (runs `node global-setup.mjs` then Playwright).

Config: `playwright.config.ts` (starts API + `web/` dev server). **Do not** use Playwright `globalSetup` to wipe `data/e2e` — it can run after the API webServer creates SQLite and cause `disk I/O error`. Wipe only via `global-setup.mjs` before Playwright (`npm test`).

### Ports (parallel to daily dev)

Defaults live in **`../test.yaml`** (`e2e` / `e2e_desktop` when `BASIS_E2E_DESKTOP=1`). Same file as pytest integration tests; see [tests/README.md](../README.md).

| Role | Dev (typical) | E2E (default) | Override |
|------|---------------|---------------|----------|
| API | 8090 | **8091** | YAML `e2e.api_port` or `BASIS_E2E_API_PORT` |
| Web | 5173 | **5174** | YAML `e2e.web_port` or `BASIS_E2E_WEB_PORT` |
| Vite HMR | 24678 | **web+19505** | YAML `e2e.hmr_port` or `BASIS_E2E_HMR_PORT` |

E2E does not use your running `uv run basis` or `5173` dev server; it starts its own stack on the E2E ports above.

## Coverage legend

| Code | Meaning |
|------|---------|
| **—** | No dedicated E2E spec visits this surface |
| **S** | Smoke: route loads, key chrome / `data-testid` / tab visible |
| **P** | Partial: one primary flow, deep link, or redirect |
| **D** | Deeper: multi-step UI and/or API seed + UI assertion |

Many workspace graph routes **skip** when `graph_runtime` is missing (`skipUnlessWorkspaceGraphWrite`, capabilities unavailable UI).

## Route ↔ E2E matrix

Routes follow [`web/src/routes/index.tsx`](../../web/src/routes/index.tsx) (`AppRoutes`) and workspace sidebar [`nav-config.ts`](../../web/src/lib/nav/nav-config.ts).

### Marketing & auth

| Route / surface | E2E | Spec(s) | Notes |
|-----------------|-----|---------|-------|
| `/` (marketing) | P | `home.e2e.spec.ts` | Anchors, register mode |
| `/login` | S | `shell.e2e.spec.ts`, `home.e2e.spec.ts` | Fields / register URL |
| Org SSO on login | P | `org-sso-login.e2e.spec.ts` | SSO entry, hint API, `sso_required` policy |
| `/settings` (org OIDC/SAML) | S | `org-saml-settings.e2e.spec.ts` | Panels visible |

### Product docs

| Route | E2E | Spec(s) |
|-------|-----|---------|
| `/docs/*` | P | `docs.e2e.spec.ts` | Sidebar nav, 404 → index |

### Platform admin (`/admin/*`)

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/admin/connectors` | S | `admin-connectors.e2e.spec.ts` | Catalog search + nav |
| `/admin/workspaces` | S | `platform-admin.e2e.spec.ts` | Workspace table + create |
| `/admin/users` | S | `platform-admin.e2e.spec.ts` | Lists first platform admin (`data/e2e/playwright-admin.json`) |
| `/admin/models` | S | `platform-admin.e2e.spec.ts` | LLM tab + add model |
| `/admin/audit` | S | `platform-admin.e2e.spec.ts` | Workspace filter + refresh |
| `/admin/settings` | S | `platform-admin.e2e.spec.ts`, `desktop-product.e2e.spec.ts` | Login + org SSO (server); desktop redirects away |

### Workspace — Explore

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/workspaces/:id/graph` | P | `graph-at.e2e.spec.ts`, `graph-diff-cross-link.e2e.spec.ts`, `onboarding.e2e.spec.ts` | `?at=` URL; workspace after ingest |
| `/workspaces/:id/search` | P | `search-temporal-url.e2e.spec.ts`, `search-graph-at.e2e.spec.ts`, `governance.e2e.spec.ts` | `as_of`, graph tab, scope |

### Workspace — Content

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/workspaces/:id/sources` | D | `onboarding.e2e.spec.ts`, `processing-job.e2e.spec.ts`, `governance.e2e.spec.ts` | Paste ingest, library chrome |
| `/workspaces/:id/processing` | P | `processing-job.e2e.spec.ts`, `governance.e2e.spec.ts` | `?job=`, failed filter |
| `/workspaces/:id/entities` | P | `reasoning-derived.e2e.spec.ts` | Derived facts + search (API seed) |

### Workspace — Connectors

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/workspaces/:id/onboarding/data` | D | `connector-mapping-suggest.e2e.spec.ts` | SQL hint → suggest → sync |
| `…/connectors/catalog` | S | `connectors.e2e.spec.ts` | Cards, connection → new mapping |
| `…/connectors/policy` | S | `connectors.e2e.spec.ts` | Save allowlist |
| `…/connectors/mappings` | P | `connectors.e2e.spec.ts`, `connector-mapping-suggest.e2e.spec.ts` | List; REST suggest (mock); cross-stream dialog |
| `…/connectors/mappings/new` | S | `connectors.e2e.spec.ts` | Prefill from connection |
| `…/connectors/mappings/:id/edit` | P | `connector-workspace.e2e.spec.ts` | Save target class + return to list |
| `…/connectors/runs` | S | `connector-workspace.e2e.spec.ts` | After `check`, run row visible |
| `…/connectors/oauth/callback` | D | `connector-workspace.e2e.spec.ts` | Browser mock exchange; API stub exchange (`e2e_playwright_oauth_*`); missing code/state error |
| Review writeback diff (connector) | P | `connectors.e2e.spec.ts` | From review queue UI |
| Mapping **Sync now** (list) | P | `connector-workspace.e2e.spec.ts` | Inbound sync toast |

### Workspace — Schema

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/workspaces/:id/ontology` | P | `governance.e2e.spec.ts`, `ontology-proposal-url.e2e.spec.ts` | Versions tab; proposal deep link |
| `/workspaces/:id/analyze` | P | `analyze-hub.e2e.spec.ts` | Tabs; legacy `/sparql`, `/reasoning` redirects |
| `/workspaces/:id/vocabulary` | S | `schema-surfaces.e2e.spec.ts` | Hub loads |
| `/workspaces/:id/mappings` (statement / extraction) | S | `schema-surfaces.e2e.spec.ts` | Title/subtitle vs connector mappings |
| `/workspaces/:id/ontology-versions` | P | `analyze-hub.e2e.spec.ts` | Via redirect/hub |
| `/workspaces/:id/shacl` | S | `schema-surfaces.e2e.spec.ts` | Legacy route → ontology `?tab=shacl` |
| `/workspaces/:id/alignments` | S | `schema-surfaces.e2e.spec.ts` | Legacy route → ontology `?tab=alignments` |

### Workspace — Govern

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/workspaces/:id/review` | D | `governance.e2e.spec.ts`, `connectors.e2e.spec.ts` | Conflicts, approve narrative, writeback |
| `/workspaces/:id/entity-resolution` | S | `schema-surfaces.e2e.spec.ts` | Dedup scan action |
| `/workspaces/:id/decisions` | P | `decisions-deep-link.e2e.spec.ts`, `governance.e2e.spec.ts` | List + `?decision=` |
| `/workspaces/:id/lineage` | P | `lineage.e2e.spec.ts` | `?node=` deep link |
| `/workspaces/:id/graph-diff` | P | `graph-diff.e2e.spec.ts` | `from` / `to` query |

### Workspace — System & account

| Route | E2E | Spec(s) | Notes |
|-------|-----|---------|-------|
| `/workspaces/:id/alerts` | D | `governance.e2e.spec.ts` | Dismiss, deep links to sources/processing/review/decisions |
| `/workspaces/:id/integration` | S | `mcp-integration.e2e.spec.ts` | Tab visible |
| `/workspaces/:id/settings` | P | `settings-graph-audit.e2e.spec.ts`, `settings-tabs.e2e.spec.ts` | Graph audit; general/members/search tabs |
| `/workspaces/:id/mcp`, `/chat` (legacy) | S | `mcp-integration.e2e.spec.ts` | Redirects to integration |

### Desktop product

| Surface | E2E | Spec(s) |
|---------|-----|---------|
| Desktop nav / admin gate | P | `desktop-product.e2e.spec.ts` (`BASIS_E2E_DESKTOP=1`) |

### Non-UI integration

| Area | E2E | Spec(s) |
|------|-----|---------|
| MCP over HTTP (smoke) | P | `mcp-integration.e2e.spec.ts` |

## Spec file index

| File | Primary intent |
|------|----------------|
| `admin-connectors.e2e.spec.ts` | Platform connector catalog admin |
| `analyze-hub.e2e.spec.ts` | Query & reasoning hub + legacy routes |
| `connector-mapping-suggest.e2e.spec.ts` | Onboarding wizard; SQL/REST suggest API; auto-expand; mappings dialog |
| `connector-workspace.e2e.spec.ts` | Runs, mapping edit, sync now, OAuth callback (mock exchange + error) |
| `settings-tabs.e2e.spec.ts` | Workspace settings general/members/search tabs |
| `platform-admin.e2e.spec.ts` | `/admin/workspaces`, `/admin/users`, `/admin/models`, `/admin/audit`, `/admin/settings` |
| `connectors.e2e.spec.ts` | Workspace connectors zones (catalog/policy/mappings) |
| `decisions-deep-link.e2e.spec.ts` | Decisions list URL state |
| `desktop-product.e2e.spec.ts` | Desktop profile routing |
| `docs.e2e.spec.ts` | In-app product docs |
| `governance.e2e.spec.ts` | Alerts, review, governance trips, cross-links |
| `graph-at.e2e.spec.ts` | Graph temporal `?at=` |
| `graph-diff.e2e.spec.ts` | Graph diff page |
| `graph-diff-cross-link.e2e.spec.ts` | Graph → diff navigation |
| `home.e2e.spec.ts` | Marketing + register entry |
| `lineage.e2e.spec.ts` | Lineage node deep link |
| `mcp-integration.e2e.spec.ts` | Integration / MCP / legacy chat paths |
| `onboarding.e2e.spec.ts` | Register → sources paste → graph |
| `ontology-proposal-url.e2e.spec.ts` | Ontology proposal list highlight |
| `org-saml-settings.e2e.spec.ts` | Org SAML settings panel |
| `org-sso-login.e2e.spec.ts` | Login SSO affordance |
| `processing-job.e2e.spec.ts` | Processing job detail / failed flows |
| `reasoning-derived.e2e.spec.ts` | Reasoning → entities derived facts UI |
| `schema-surfaces.e2e.spec.ts` | Statement mappings, entity resolution, vocabulary, SHACL/alignments redirects |
| `search-graph-at.e2e.spec.ts` | Search graph tab URL |
| `search-temporal-url.e2e.spec.ts` | Search chunk `as_of` URL |
| `settings-graph-audit.e2e.spec.ts` | Workspace settings graph audit tab |
| `shell.e2e.spec.ts` | Login form |

## Optional live GitHub (connector E2E)

Set `BASIS_E2E_GITHUB_TOKEN` (or `BASIS_TEST_GITHUB_TOKEN`) in the environment. Optional `BASIS_E2E_GITHUB_RUN_SYNC=1` for live inbound sync in `connector-mapping-suggest.e2e.spec.ts`.

When adding specs, extend this table and keep naming `*.e2e.spec.ts` (CI: `scripts/audit/audit-test-naming.py`).
