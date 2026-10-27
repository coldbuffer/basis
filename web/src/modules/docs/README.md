# Product documentation (`/docs`)

Public marketing docs (Fumadocs MDX). Not the gitignored internal `docs/` architecture tree.

## Layout

| Path | Role |
|------|------|
| `web/content/docs/{en,zh}/` | MDX/Markdown pages + `meta.json` sidebar |
| `web/src/modules/docs/` | Route shell, `DOC_SLUGS`, search |
| `web/src/components/app/marketing/docs/` | Sidebar, search dialog, page chrome |

## Add or rename a page

1. Add `{en,zh}` files under `content/docs/<locale>/` (use `.mdx`; generated pages use JSX comments `{/* */}`, not HTML `<!-- -->`).
2. Register the file in both `meta.json` files (sidebar order).
3. Add the slug to `DOC_SLUGS` in `lib/product-docs-nav.ts` (`index` → route slug `overview`).
4. `cd web && npm run postinstall` (regenerates `.source/`).
5. `npm test -- src/modules/docs/` and `npm run typecheck`.

## Generated pages

| Output | Command | CI |
|--------|---------|-----|
| `mcp-tools.mdx` | `npm run gen:mcp-tools-docs` | `openapi` job: `generate-product-docs-mcp-tools.py --check` |

After changing static MCP tools in `basis/application/tool_catalog/`, regenerate and commit both locales.

Search (⌘K) matches title, description, slug, and plain text extracted from MDX bodies via Vite `import.meta.glob`. Self-host pages live under the **Operations** group in `meta.json`.
