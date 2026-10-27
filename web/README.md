# @basis/web

Vite + React front end for the Basis platform and per-workspace Explorer screens.

## Source layout

| Path | Role |
|------|------|
| `src/routes/` | App route tree — [routes/README.md](src/routes/README.md) |
| `src/modules/` | Feature modules (menu/URL) — [modules/README.md](src/modules/README.md) |
| `src/components/app/shared/` | Layout, page patterns, workspace frame — [README](src/components/app/shared/README.md) |
| `src/components/` | React UI — three roots: **`ui`**, **`admin`**, **`app`** (see below). |
| `src/lib/` | Subdirs: `openapi/`, `session/`, `workspace/`, `nav/`, … + root `utils.ts`; see [lib/README.md](src/lib/README.md). |
| `content/docs/` | **Product docs** (`/docs/*`) — Fumadocs MDX (`en/`, `zh/`). IA: `{locale}/meta.json`; slugs in `src/modules/docs/lib/product-docs-nav.ts`. Long-form pages (`bocp.md`, …) edited directly. **MCP tools index:** `npm run gen:mcp-tools-docs` (CI: `generate-product-docs-mcp-tools.py --check`). |
| `source.config.ts` | Fumadocs MDX config; `postinstall` runs `fumadocs-mdx` → `.source/` (gitignored). |
| `server/` | **Hono web layer** — production static + `/api` reverse proxy (`server/prod.ts`); dev entry `server/dev.ts` (Hono + Vite middleware). Playground LLM config is browser-local. |
| `src/styles/` | Vendor overrides (e.g. Swagger UI); global chrome in root [`src/styles.css`](src/styles.css). |

## `src/components/` — three roots

| Root | Role |
|------|------|
| **`ui/`** | shadcn registry only — update with `npx shadcn add -o`, no hand edits. |
| **`admin/`** | `/admin/*` UI — layout, section nav, org SSO, access settings; `admin/models/` for model catalog. |
| **`app/`** | Marketing site + cross-product shared UI (`app/shared/`). |

**Dependency:** `admin/` and `app/` may import `ui/` and `app/shared/*`; `ui/` must not import `admin/` or `app/`. Feature routes live in `modules/`; workspace frame in `app/shared/workspace/`.

### `app/shared/`

| Path | Role |
|------|------|
| `primitives/` | Non-registry controls (icons, editors, date picker, …). |
| `effects/` | Decorative motion. |
| `console/` | List/data page patterns — used by `modules/*` and admin. |
| `shell/` | Global app chrome — `BasisLayout`, sidebar, account menu. |
| `workspace/` | Per-workspace frame (`frame/`) + `entity-ref-line`. |

`app/marketing/` — login/landing and docs chrome blocks.

Tailwind class bundles: [`src/lib/ui-classes/`](src/lib/ui-classes/README.md).

## Workspace Explorer flow

1. **`routes/index.tsx`** — `AppRoutes` (platform, workspaces, docs, auth); lazy chunks in `routes/lazy-pages.ts`.
2. **`modules/<segment>/`** — `index.tsx` (route entry), `pages/` (`screen.tsx`, glue); Sigma graph in `modules/graph/`.
3. **`app/shared/workspace/`** — workspace frame; entity browser under `modules/entities/`.
4. **`lib/workspace/`** — scoped HTTP, graph store, Sigma theme.

Auth: `modules/login`, `home`; admin/workspace/docs/swagger routes are in the same `routes/index.tsx` table.

## Styling conventions

Product styling: **TS class bundles** in [`src/lib/ui-classes/`](src/lib/ui-classes/README.md); global control chrome (Button under `[data-basis-app]`, fields, badges) in [`src/styles.css`](src/styles.css).

- Prefer design tokens (`border-border`, `text-muted-foreground`) over one-off hex.
- Do not hand-edit `components/ui/*` for Basis; extend `styles.css` or `exWsGhost*` from `@/lib/ui-classes/explorer-ws.js`.

## Scripts

- `npm run dev` — Hono + Vite (port 5173): Hono proxies `/api`, `/openapi`, …; Vite handles SPA/HMR. `npm run dev:vite` — Vite only (no Hono; API calls need `VITE_BASIS_API_URL` or fail).
- `npm run build` — `tsc` + production bundle to `../dist/web`.
- `npm run start` — production Hono server (after `build`; serves `dist/web` + BFF).
- `npm test` / `npm run test:e2e` — Vitest and Playwright.

Run these from the `web/` directory (`cd web` after cloning the repo).

### E2E (Playwright)

E2E specs live under [`tests/e2e/specs/`](../tests/e2e/specs/). Use `CI=1 npm run test:e2e` from `web/` (delegates to `tests/e2e`). See [tests/e2e/README.md](../tests/e2e/README.md).
